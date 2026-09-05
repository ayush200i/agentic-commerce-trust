import asyncio
import hashlib
import hmac
import os
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from backend.models import StartSession
from backend.providers import Agents, ProviderError, RazorpayMCP, safe_payment_fields
from backend.store import GENESIS, Store, digest, now, verify_entries


class State(TypedDict, total=False):
    session_id: str
    selected_id: str
    discount: int
    include_mat: bool


def quote_hash(session: dict) -> str:
    return digest(
        {
            "session_id": session["id"],
            "quote": session["quote"],
            "policy": session["policy"],
            "payment_mode": session["payment_mode"],
        }
    )


def policy_checks(session: dict) -> list[dict]:
    quote = session["quote"]
    policy = session["policy"]
    return [
        {
            "rule": "Spend cap",
            "passed": quote["amount"] + session["spend_so_far"] <= policy["spend_cap"],
            "actual": quote["amount"] + session["spend_so_far"],
            "limit": policy["spend_cap"],
        },
        {
            "rule": "Category allowlist",
            "passed": all(p["category"] in policy["categories"] for p in quote["lines"]),
            "actual": sorted({p["category"] for p in quote["lines"]}),
            "limit": policy["categories"],
        },
    ]


class Commerce:
    def __init__(self, store: Store, agents=None, payments=None, delay: float = 0.35):
        self.store = store
        self.agents = agents or Agents()
        self.payments = payments or RazorpayMCP()
        self.delay = delay
        self.lock = asyncio.Lock()  # One local operator / one worker; payment transitions serialize.
        graph = StateGraph(State)
        graph.add_node("buyer", self.buyer)
        graph.add_node("seller", self.seller)
        graph.add_node("stock_recovery", self.recover)
        graph.add_node("policy", self.evaluate)
        graph.add_edge(START, "buyer")
        graph.add_edge("buyer", "seller")
        graph.add_edge("seller", "stock_recovery")
        graph.add_edge("stock_recovery", "policy")
        graph.add_edge("policy", END)
        self.graph = graph.compile()

    def new(self, request: StartSession):
        session = {
            "id": uuid4().hex,
            "created_at": now(),
            "status": "negotiating",
            "goal": request.goal,
            "policy": request.policy.model_dump(),
            "agent_mode": request.agent_mode,
            "payment_mode": request.payment_mode,
            "inject_stock_failure": request.inject_stock_failure,
            "spend_so_far": 0,
            "quote": None,
            "approval": None,
            "checks": [],
            "transaction": None,
            "recovered": False,
            "audit_head": GENESIS,
            "error": None,
        }
        self.store.save(session)
        self.store.append(
            session,
            "system",
            "session_started",
            "Purchase mandate recorded. No money has moved.",
            {
                "goal": session["goal"],
                "policy": session["policy"],
                "agent_mode": session["agent_mode"],
                "payment_mode": session["payment_mode"],
                "stock_failure_enabled": request.inject_stock_failure,
            },
        )
        return session

    async def event(self, session, actor, action, summary, evidence=None):
        self.store.append(session, actor, action, summary, evidence)
        await asyncio.sleep(self.delay)

    async def run(self, session_id):
        try:
            await self.graph.ainvoke({"session_id": session_id})
        except Exception as error:
            session = self.store.get(session_id)
            session["status"] = "failed"
            session["error"] = (
                str(error)
                if isinstance(error, ProviderError)
                else "The workflow stopped safely. No payment was attempted."
            )
            self.store.append(session, "system", "workflow_stopped", session["error"])

    def eligible(self, session, excluded=None):
        return [
            p
            for p in self.store.catalog()
            if p["stock"] > 0
            and p["id"] != excluded
            and p["category"] in session["policy"]["categories"]
            and p["price"] <= session["policy"]["spend_cap"]
        ]

    async def buyer(self, state):
        session = self.store.get(state["session_id"])
        products = self.eligible(session)
        if not products:
            raise ProviderError(
                "No in-stock product fits the category rules and spend cap. Adjust the mandate."
            )
        decision = await self.agents.choose(
            session["agent_mode"], session["goal"], products, session["policy"]
        )
        if decision.product_id not in {p["id"] for p in products}:
            raise ProviderError("The buyer proposed an ineligible product. The policy engine blocked it.")
        product = next(p for p in products if p["id"] == decision.product_id)
        await self.event(
            session,
            "buyer",
            "product_selected",
            decision.summary,
            {"product": product, "eligible_products": [p["id"] for p in products]},
        )
        return {"selected_id": decision.product_id}

    async def seller(self, state):
        session = self.store.get(state["session_id"])
        product = next(p for p in self.store.catalog() if p["id"] == state["selected_id"])
        mat = next(
            (p for p in self.eligible(session) if p["id"] == "felt-mat" and p["id"] != product["id"]), None
        )
        offer = await self.agents.offer(
            session["agent_mode"], session["goal"], product, session["policy"], mat
        )
        await self.event(
            session,
            "seller",
            "offer_proposed",
            offer.summary,
            {"discount_percent": offer.discount_percent, "include_mat": offer.include_mat},
        )
        return {"discount": offer.discount_percent, "include_mat": offer.include_mat and mat is not None}

    async def recover(self, state):
        session = self.store.get(state["session_id"])
        if not session["inject_stock_failure"]:
            return {}
        original = next(p for p in self.store.catalog() if p["id"] == state["selected_id"])
        await self.event(
            session,
            "seller",
            "stock_failure",
            f"Simulated stock change: {original['name']} is no longer "
            "available for this session. Looking for a policy-compliant replacement.",
            {"simulated": True, "unavailable_product_id": original["id"]},
        )
        candidates = [
            p for p in self.eligible(session, original["id"]) if p["category"] == original["category"]
        ]
        if not candidates:
            raise ProviderError("No eligible replacement is available. Purchase stopped before payment.")
        decision = await self.agents.choose(
            session["agent_mode"], session["goal"], candidates, session["policy"]
        )
        if decision.product_id not in {p["id"] for p in candidates}:
            raise ProviderError("The proposed replacement failed eligibility checks. Purchase stopped.")
        replacement = next(p for p in candidates if p["id"] == decision.product_id)
        session["recovered"] = True
        await self.event(
            session,
            "buyer",
            "replacement_selected",
            f"Switching to {replacement['name']}. " + decision.summary,
            {"replaced": original["id"], "replacement": replacement, "simulated_stock_change": True},
        )
        return {"selected_id": replacement["id"]}

    async def evaluate(self, state):
        session = self.store.get(state["session_id"])
        catalog = self.store.catalog()
        product = next(p for p in catalog if p["id"] == state["selected_id"])
        lines = [product]
        mat = next(p for p in catalog if p["id"] == "felt-mat")
        if state["include_mat"] and product["id"] != mat["id"]:
            proposed = (product["price"] + mat["price"]) * (100 - state["discount"]) // 100
            if (
                mat["stock"] > 0
                and mat["category"] in session["policy"]["categories"]
                and proposed <= session["policy"]["spend_cap"]
            ):
                lines.append(mat)
            else:
                await self.event(
                    session,
                    "policy",
                    "bundle_removed",
                    "The optional mat would violate policy or stock rules. Keeping only the primary item.",
                )
        subtotal = sum(p["price"] for p in lines)
        amount = subtotal * (100 - state["discount"]) // 100
        session["quote"] = {
            "lines": [{k: p[k] for k in ("id", "name", "price", "category")} for p in lines],
            "subtotal": subtotal,
            "discount_percent": state["discount"],
            "amount": amount,
            "currency": "INR",
            "savings": subtotal - amount,
        }
        session["quote_hash"] = quote_hash(session)
        await self.event(
            session,
            "buyer",
            "quote_accepted",
            "The proposed basket fits the purchase mandate and "
            "the seller's published discount bounds. Requesting policy clearance before checkout.",
            {
                "quote_hash": session["quote_hash"],
                "amount": amount,
                "currency": "INR",
                "decision_source": "application eligibility checks",
            },
        )
        session["checks"] = policy_checks(session)
        if not all(check["passed"] for check in session["checks"]):
            raise ProviderError("The quote violates policy. Payment is blocked.")
        needs_approval = amount > session["policy"]["approval_threshold"]
        session["status"] = "awaiting_approval" if needs_approval else "ready"
        await self.event(
            session,
            "policy",
            "policy_evaluated",
            "Spend and category checks passed. "
            + (
                "Human approval is required for this quote."
                if needs_approval
                else "The quote is within the automatic approval threshold."
            ),
            {
                "checks": session["checks"],
                "quote": session["quote"],
                "quote_hash": session["quote_hash"],
                "approval_required": needs_approval,
            },
        )
        return {}

    def assert_integrity(self, session):
        if not verify_entries(self.store.entries(session["id"]), session["audit_head"])["valid"]:
            raise ProviderError("Audit verification failed. Payment is blocked.")
        if session.get("quote_hash") != quote_hash(session):
            raise ProviderError("The quote changed. A new session and approval are required.")
        if not all(c["passed"] for c in policy_checks(session)):
            raise ProviderError("Policy no longer permits this purchase.")
        if session["quote"]["amount"] > session["policy"]["approval_threshold"]:
            if (session.get("approval") or {}).get("quote_hash") != session["quote_hash"]:
                raise ProviderError("Human approval is required for this exact quote.")

    async def approve(self, sid, approved, expected_hash):
        async with self.lock:
            session = self.store.get(sid)
            if session["status"] != "awaiting_approval" or session["quote_hash"] != expected_hash:
                raise ProviderError("This approval is stale or the session is not awaiting approval.")
            if (
                not verify_entries(self.store.entries(sid), session["audit_head"])["valid"]
                or quote_hash(session) != expected_hash
            ):
                raise ProviderError("Quote or audit integrity check failed.")
            session["status"] = "ready" if approved else "rejected"
            session["approval"] = {"approved": approved, "quote_hash": expected_hash, "timestamp": now()}
            self.store.append(
                session,
                "human",
                "quote_approved" if approved else "quote_rejected",
                "Operator approved the exact quote."
                if approved
                else "Operator rejected the quote. No money moved.",
                session["approval"],
            )
            return session

    async def checkout(self, sid):
        async with self.lock:
            session = self.store.get(sid)
            if session["status"] in {"awaiting_payment", "completed"}:
                return session
            if session["status"] != "ready":
                raise ProviderError("The session is not approved and ready for checkout.")
            self.assert_integrity(session)
            session["stock_reserved"] = True
            session["status"] = "creating_order"
            arguments = {"amount": session["quote"]["amount"], "currency": "INR", "receipt": sid}
            reserved = self.store.append(
                session,
                "payment",
                "order_requested",
                "Approved quote locked; creating one order.",
                {"tool": "create_order", "arguments": arguments, "mode": session["payment_mode"]},
                reserve_lines=session["quote"]["lines"],
            )
            if reserved is None:
                session["status"] = "failed"
                session["stock_reserved"] = False
                session["error"] = (
                    "Stock changed after approval. Start a new session to negotiate a replacement."
                )
                self.store.append(session, "policy", "stock_reservation_failed", session["error"])
                return session
            try:
                if session["payment_mode"] == "simulated":
                    order = {
                        "id": "sim_order_" + sid[:16],
                        "amount": arguments["amount"],
                        "currency": "INR",
                        "status": "created",
                    }
                else:
                    order = await self.payments.call("create_order", arguments)
                if (
                    not isinstance(order.get("id"), str)
                    or order.get("amount") != arguments["amount"]
                    or order.get("currency") != "INR"
                ):
                    raise ProviderError(
                        "Provider order does not match the approved quote. Reconciliation required."
                    )
                if session["payment_mode"] == "razorpay" and not order["id"].startswith("order_"):
                    raise ProviderError("Unexpected Razorpay order identifier. Reconciliation required.")
                session["transaction"] = {
                    "order_id": order["id"],
                    "payment_id": None,
                    "amount": order["amount"],
                    "currency": "INR",
                    "status": "created",
                    "mode": session["payment_mode"],
                }
                session["status"] = "awaiting_payment"
                self.store.append(
                    session,
                    "payment",
                    "order_created",
                    "Order recorded. Payment has not been captured.",
                    {
                        "tool": "create_order",
                        "response": safe_payment_fields(order),
                        "mode": session["payment_mode"],
                    },
                )
            except ProviderError as error:
                # An order request may succeed upstream even if its response is lost. Never retry automatically.
                session["status"] = "reconciliation_required"
                session["error"] = str(error)
                self.store.append(session, "payment", "reconciliation_required", str(error), {"receipt": sid})
            return session

    async def simulate_capture(self, sid):
        async with self.lock:
            session = self.store.get(sid)
            if session["payment_mode"] != "simulated":
                raise ProviderError("Simulation cannot complete a Razorpay transaction.")
            if session["status"] == "completed":
                return session
            if session["status"] != "awaiting_payment":
                raise ProviderError("Create an approved simulated order first.")
            self.assert_integrity(session)
            self.finish(session, "sim_pay_" + sid[:16])
            return session

    def finish(self, session, payment_id):
        session["status"] = "completed"
        session["spend_so_far"] = session["quote"]["amount"]
        session["transaction"].update(status="captured", payment_id=payment_id)
        simulated = session["payment_mode"] == "simulated"
        self.store.append(
            session,
            "payment",
            "payment_captured",
            "Simulated payment captured. No real money moved."
            if simulated
            else "Razorpay test payment verified and captured.",
            {"transaction": session["transaction"], "simulated": simulated},
        )

    async def confirm(self, sid, confirmation):
        async with self.lock:
            session = self.store.get(sid)
            if session["payment_mode"] != "razorpay" or not session["transaction"]:
                raise ProviderError("No Razorpay order exists for this session.")
            order_id = session["transaction"]["order_id"]
            message = f"{order_id}|{confirmation.razorpay_payment_id}"
            expected = hmac.new(
                os.getenv("RAZORPAY_KEY_SECRET", "").encode(), message.encode(), hashlib.sha256
            ).hexdigest()
            if confirmation.razorpay_order_id != order_id or not hmac.compare_digest(
                expected, confirmation.razorpay_signature
            ):
                raise ProviderError("Checkout signature verification failed.")
            if session["status"] == "completed":
                if session["transaction"]["payment_id"] != confirmation.razorpay_payment_id:
                    raise ProviderError("The session already completed with a different payment.")
                return session
            if session["status"] != "awaiting_payment":
                raise ProviderError("Payment cannot be confirmed in the current state.")
            self.assert_integrity(session)
            session["status"] = "verifying_payment"
            self.store.append(
                session,
                "payment",
                "payment_verification_requested",
                "Checkout signature verified; checking payment through Razorpay MCP.",
                {"tool": "fetch_payment", "payment_id": confirmation.razorpay_payment_id},
            )
            try:
                payment = await self.payments.call(
                    "fetch_payment", {"payment_id": confirmation.razorpay_payment_id}
                )
                self.validate_payment(session, payment, confirmation.razorpay_payment_id)
                self.store.append(
                    session,
                    "payment",
                    "payment_fetched",
                    "Provider payment details checked against the approved order.",
                    {"tool": "fetch_payment", "response": safe_payment_fields(payment)},
                )
                if payment["status"] == "authorized":
                    args = {
                        "payment_id": confirmation.razorpay_payment_id,
                        "amount": session["quote"]["amount"],
                        "currency": "INR",
                    }
                    self.store.append(
                        session,
                        "payment",
                        "capture_requested",
                        "Authorized payment matches policy; requesting capture.",
                        {"tool": "capture_payment", "arguments": args},
                    )
                    payment = await self.payments.call("capture_payment", args)
                    self.validate_payment(session, payment, confirmation.razorpay_payment_id)
                    self.store.append(
                        session,
                        "payment",
                        "capture_response",
                        "Capture response received.",
                        {"tool": "capture_payment", "response": safe_payment_fields(payment)},
                    )
                if payment["status"] != "captured":
                    raise ProviderError(
                        "Payment is not captured. Check the Razorpay dashboard before any retry."
                    )
                self.finish(session, confirmation.razorpay_payment_id)
            except ProviderError as error:
                session["status"] = "reconciliation_required"
                session["error"] = str(error)
                self.store.append(
                    session, "payment", "reconciliation_required", str(error), {"order_id": order_id}
                )
            return session

    @staticmethod
    def validate_payment(session, payment, payment_id):
        if (
            payment.get("id") != payment_id
            or payment.get("order_id") != session["transaction"]["order_id"]
            or payment.get("amount") != session["quote"]["amount"]
            or payment.get("currency") != "INR"
        ):
            raise ProviderError(
                "Provider payment differs from the approved order or amount. Capture blocked."
            )

    def snapshot(self, sid):
        session = self.store.get(sid)
        session["events"] = self.store.entries(sid)
        session["verification"] = verify_entries(session["events"], session["audit_head"])
        return session

    def recover_interrupted(self):
        for session in self.store.sessions():
            if session["status"] in {"creating_order", "verifying_payment"}:
                session["status"] = "reconciliation_required"
                session["error"] = (
                    "The process restarted during a payment action. Reconcile with Razorpay; automatic retry is blocked."
                )
                self.store.append(session, "system", "restart_reconciliation", session["error"])
            elif session["status"] == "negotiating":
                session["status"] = "failed"
                session["error"] = (
                    "Negotiation was interrupted by a restart. Start a new session; no payment was attempted."
                )
                self.store.append(session, "system", "restart_interrupted", session["error"])
