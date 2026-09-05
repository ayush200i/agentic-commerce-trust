import asyncio
import copy
import hashlib
import hmac
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.commerce import Commerce
from backend.main import create_app
from backend.models import PaymentConfirmation, StartSession
from backend.providers import ProviderError, RazorpayMCP
from backend.store import Store, verify_entries
from scripts.verify_audit import verify


@pytest.fixture
def commerce(tmp_path):
    return Commerce(Store(tmp_path / "test.db"), delay=0)


async def negotiated(commerce, **kwargs):
    request = StartSession(goal="Find a quiet keyboard with a desk mat", **kwargs)
    session = commerce.new(request)
    await commerce.run(session["id"])
    return commerce.snapshot(session["id"])


async def approved(commerce, **kwargs):
    session = await negotiated(commerce, **kwargs)
    if session["status"] == "awaiting_approval":
        await commerce.approve(session["id"], True, session["quote_hash"])
    return commerce.snapshot(session["id"])


async def test_stock_recovery_approval_and_capture(commerce):
    session = await negotiated(commerce)
    assert session["status"] == "awaiting_approval"
    assert session["recovered"]
    assert session["quote"]["lines"][0]["id"] == "forma-75"
    assert session["quote"]["amount"] == 386216
    with pytest.raises(ProviderError, match="not approved"):
        await commerce.checkout(session["id"])
    await commerce.approve(session["id"], True, session["quote_hash"])
    await commerce.checkout(session["id"])
    result = await commerce.simulate_capture(session["id"])
    assert result["status"] == "completed"
    assert result["spend_so_far"] == 386216
    assert result["transaction"]["payment_id"].startswith("sim_pay_")
    assert commerce.snapshot(session["id"])["verification"]["valid"]


async def test_replayed_concurrent_checkout_and_capture_move_money_once(commerce):
    session = await approved(commerce)
    await asyncio.gather(*(commerce.checkout(session["id"]) for _ in range(6)))
    await asyncio.gather(*(commerce.simulate_capture(session["id"]) for _ in range(6)))
    result = commerce.snapshot(session["id"])
    assert sum(e["action"] == "order_requested" for e in result["events"]) == 1
    assert sum(e["action"] == "payment_captured" for e in result["events"]) == 1
    assert next(p for p in commerce.store.catalog() if p["id"] == "forma-75")["stock"] == 11


async def test_rejection_prevents_money_action(commerce):
    session = await negotiated(commerce)
    await commerce.approve(session["id"], False, session["quote_hash"])
    with pytest.raises(ProviderError):
        await commerce.checkout(session["id"])
    assert commerce.snapshot(session["id"])["transaction"] is None


async def test_stale_approval_and_quote_tamper_are_blocked(commerce):
    session = await negotiated(commerce)
    with pytest.raises(ProviderError, match="stale"):
        await commerce.approve(session["id"], True, "a" * 64)
    await commerce.approve(session["id"], True, session["quote_hash"])
    stored = commerce.store.get(session["id"])
    stored["quote"]["amount"] -= 100
    commerce.store.save(stored)
    with pytest.raises(ProviderError, match="quote changed"):
        await commerce.checkout(session["id"])


async def test_no_eligible_product_stops_before_payment(commerce):
    session = await negotiated(
        commerce, policy={"spend_cap": 100, "approval_threshold": 100, "categories": ["keyboards"]}
    )
    assert session["status"] == "failed"
    assert session["transaction"] is None
    assert "No in-stock product" in session["error"]


async def test_optional_bundle_cannot_breach_cap(commerce):
    session = await negotiated(
        commerce,
        policy={
            "spend_cap": 350000,
            "approval_threshold": 350000,
            "categories": ["keyboards", "accessories"],
        },
    )
    assert session["status"] == "ready"
    assert len(session["quote"]["lines"]) == 1
    assert session["quote"]["amount"] <= 350000


async def test_category_allowlist_excludes_mat(commerce):
    session = await negotiated(
        commerce, policy={"spend_cap": 500000, "approval_threshold": 500000, "categories": ["keyboards"]}
    )
    assert all(p["category"] == "keyboards" for p in session["quote"]["lines"])


async def test_audit_detects_edit_reorder_delete_and_tail_truncation(commerce):
    session = await approved(commerce)
    entries = session["events"]
    assert verify_entries(entries, session["audit_head"])["valid"]
    edited = copy.deepcopy(entries)
    edited[1]["summary"] = "changed"
    assert not verify_entries(edited, session["audit_head"])["valid"]
    reordered = copy.deepcopy(entries)
    reordered[1], reordered[2] = reordered[2], reordered[1]
    assert not verify_entries(reordered, session["audit_head"])["valid"]
    assert not verify_entries(entries[1:], session["audit_head"])["valid"]
    assert not verify_entries(entries[:-1], session["audit_head"])["valid"]
    doc = {"session_id": session["id"], "head": session["audit_head"], "entries": entries}
    assert verify(doc, session["audit_head"])[0]
    doc["entries"] = entries[:-1]
    doc["head"] = entries[-2]["hash"]
    assert not verify(doc, session["audit_head"])[0]


class FakePayments:
    def __init__(self, amount=386216, status="authorized", fail_create=False):
        self.calls = []
        self.amount = amount
        self.status = status
        self.fail_create = fail_create

    async def call(self, tool, args):
        self.calls.append((tool, args))
        if tool == "create_order":
            if self.fail_create:
                raise ProviderError("Response lost; reconcile provider state.")
            return {"id": "order_abc", "amount": args["amount"], "currency": "INR", "status": "created"}
        return {
            "id": "pay_abc",
            "order_id": "order_abc",
            "amount": self.amount,
            "currency": "INR",
            "status": "captured" if tool == "capture_payment" else self.status,
        }


def confirmation(secret="test-secret"):
    return PaymentConfirmation(
        razorpay_payment_id="pay_abc",
        razorpay_order_id="order_abc",
        razorpay_signature=hmac.new(secret.encode(), b"order_abc|pay_abc", hashlib.sha256).hexdigest(),
    )


async def test_razorpay_path_uses_tools_and_validates_signature(commerce, monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test-secret")
    commerce.payments = FakePayments()
    session = await approved(commerce, payment_mode="razorpay")
    await commerce.checkout(session["id"])
    with pytest.raises(ProviderError, match="signature"):
        await commerce.confirm(session["id"], confirmation("wrong-secret"))
    assert [c[0] for c in commerce.payments.calls] == ["create_order"]
    result = await commerce.confirm(session["id"], confirmation())
    assert result["status"] == "completed"
    assert [c[0] for c in commerce.payments.calls] == ["create_order", "fetch_payment", "capture_payment"]
    await commerce.confirm(session["id"], confirmation())
    assert len(commerce.payments.calls) == 3


async def test_mismatched_provider_amount_blocks_capture(commerce, monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test-secret")
    commerce.payments = FakePayments(amount=1)
    session = await approved(commerce, payment_mode="razorpay")
    await commerce.checkout(session["id"])
    result = await commerce.confirm(session["id"], confirmation())
    assert result["status"] == "reconciliation_required"
    assert "capture_payment" not in [c[0] for c in commerce.payments.calls]
    assert result["spend_so_far"] == 0


async def test_unknown_order_result_is_not_retried(commerce):
    commerce.payments = FakePayments(fail_create=True)
    session = await approved(commerce, payment_mode="razorpay")
    result = await commerce.checkout(session["id"])
    assert result["status"] == "reconciliation_required"
    with pytest.raises(ProviderError):
        await commerce.checkout(session["id"])
    assert len(commerce.payments.calls) == 1


async def test_simulation_cannot_complete_real_provider_session(commerce):
    session = await approved(commerce, payment_mode="razorpay")
    with pytest.raises(ProviderError, match="Simulation cannot"):
        await commerce.simulate_capture(session["id"])


def test_live_razorpay_keys_rejected(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_live_abc")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "unused")
    with pytest.raises(ProviderError, match="Live keys"):
        RazorpayMCP().headers()


async def test_restart_does_not_repeat_external_action(commerce):
    session = await approved(commerce)
    session["status"] = "creating_order"
    commerce.store.save(session)
    commerce.recover_interrupted()
    assert commerce.store.get(session["id"])["status"] == "reconciliation_required"
    with pytest.raises(ProviderError):
        await commerce.checkout(session["id"])


def test_api_rejects_cross_origin_writes_and_noninteger_money(tmp_path):
    with TestClient(create_app(tmp_path / "api.db", delay=0)) as client:
        body = {"goal": "Find a keyboard"}
        assert client.post("/api/sessions", json=body).status_code == 403
        assert (
            client.post(
                "/api/sessions",
                json=body,
                headers={"X-Trust-Control": "local-operator", "Origin": "https://evil.example"},
            ).status_code
            == 403
        )
        body["policy"] = {"spend_cap": 100.5}
        assert (
            client.post("/api/sessions", json=body, headers={"X-Trust-Control": "local-operator"}).status_code
            == 422
        )
        assert client.get("/api/sessions/not-found").status_code == 404
        assert "key_secret" not in client.get("/api/health").text


async def test_stock_and_checkpoint_roll_back_when_audit_write_fails(commerce):
    session = await approved(commerce)
    before = commerce.store.catalog()
    with commerce.store.connect() as db:
        db.execute(
            "CREATE TRIGGER fail_checkout BEFORE INSERT ON audit "
            "WHEN json_extract(NEW.entry, '$.action') = 'order_requested' "
            "BEGIN SELECT RAISE(ABORT, 'test disk failure'); END;"
        )
    with pytest.raises(sqlite3.IntegrityError):
        await commerce.checkout(session["id"])
    assert commerce.store.catalog() == before
    assert commerce.store.get(session["id"])["status"] == "ready"
    assert commerce.snapshot(session["id"])["verification"]["valid"]


async def test_stock_exhausted_after_quote_prevents_order_without_partial_reservation(commerce):
    session = await approved(commerce)
    catalog = commerce.store.catalog()
    mat = next(p for p in catalog if p["id"] == "felt-mat")
    mat["stock"] = 0
    with commerce.store.connect() as db:
        db.execute("UPDATE products SET document=? WHERE id=?", (json.dumps(mat), mat["id"]))
    result = await commerce.checkout(session["id"])
    assert result["status"] == "failed"
    assert result["transaction"] is None
    assert next(p for p in commerce.store.catalog() if p["id"] == "forma-75")["stock"] == 12
    assert not any(e["action"] == "order_requested" for e in commerce.store.entries(session["id"]))
