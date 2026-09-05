import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.commerce import Commerce
from backend.config import ROOT, capabilities, razorpay_ready
from backend.models import Approval, PaymentConfirmation, StartSession
from backend.providers import ProviderError
from backend.store import Store


def create_app(database=None, delay=0.35):
    store = Store(database or os.getenv("TRUST_DB_PATH", str(ROOT / "data" / "trust.db")))
    commerce = Commerce(store, delay=delay)
    tasks = set()

    @asynccontextmanager
    async def lifespan(app):
        commerce.recover_interrupted()
        yield
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="Counterseal commerce API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    app.state.commerce = commerce

    @app.middleware("http")
    async def local_operator_boundary(request: Request, call_next):
        # Browser writes require a custom header and an explicitly local origin.
        # This is a local, single-operator prototype, not hosted multi-user auth.
        allowed = {
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "http://testserver",
        }
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("X-Trust-Control") != "local-operator":
                return JSONResponse(
                    {"detail": "A local operator request header is required."}, status_code=403
                )
            origin = request.headers.get("origin")
            if origin and origin not in allowed:
                return JSONResponse(
                    {"detail": "This origin cannot control the local checkout."}, status_code=403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ProviderError)
    async def provider_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing_session(request, error):
        return JSONResponse({"detail": "Session not found."}, status_code=404)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", **capabilities()}

    @app.get("/api/catalog")
    async def catalog():
        return store.catalog()

    @app.get("/api/sessions")
    async def sessions():
        return [
            {k: s[k] for k in ("id", "created_at", "status", "goal", "payment_mode", "spend_so_far")}
            for s in store.sessions()
        ]

    @app.post("/api/sessions", status_code=201)
    async def start(request: StartSession):
        if request.payment_mode == "razorpay" and not razorpay_ready():
            raise HTTPException(
                422, "Configure Razorpay test key ID and secret before choosing Razorpay mode."
            )
        if request.agent_mode == "openai" and not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(422, "Configure OpenAI before choosing OpenAI mode.")
        if len(tasks) >= 4:
            raise HTTPException(429, "Four negotiations are already running. Wait for one to finish.")
        session = commerce.new(request)
        task = asyncio.create_task(commerce.run(session["id"]))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return commerce.snapshot(session["id"])

    @app.get("/api/sessions/{sid}")
    async def session(sid: str):
        return commerce.snapshot(sid)

    @app.get("/api/sessions/{sid}/events")
    async def events(sid: str, request: Request):
        store.get(sid)

        async def stream():
            previous = ""
            while not await request.is_disconnected():
                data = json.dumps(commerce.snapshot(sid), ensure_ascii=False)
                if data != previous:
                    yield f"data: {data}\n\n"
                    previous = data
                else:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(0.7)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
        )

    @app.post("/api/sessions/{sid}/approval")
    async def approval(sid: str, body: Approval):
        await commerce.approve(sid, body.approved, body.quote_hash)
        return commerce.snapshot(sid)

    @app.post("/api/sessions/{sid}/checkout")
    async def checkout(sid: str):
        await commerce.checkout(sid)
        return commerce.snapshot(sid)

    @app.post("/api/sessions/{sid}/simulate-capture")
    async def simulate_capture(sid: str):
        await commerce.simulate_capture(sid)
        return commerce.snapshot(sid)

    @app.get("/api/sessions/{sid}/checkout-config")
    async def checkout_config(sid: str):
        session = store.get(sid)
        if session["payment_mode"] != "razorpay" or session["status"] != "awaiting_payment":
            raise HTTPException(409, "No test checkout is ready.")
        return {
            "key": os.getenv("RAZORPAY_KEY_ID"),
            "order_id": session["transaction"]["order_id"],
            "amount": session["quote"]["amount"],
            "currency": "INR",
            "name": "Counterseal test merchant",
            "description": "Razorpay hackathon test checkout",
        }

    @app.post("/api/sessions/{sid}/confirm-payment")
    async def confirm_payment(sid: str, body: PaymentConfirmation):
        await commerce.confirm(sid, body)
        return commerce.snapshot(sid)

    @app.get("/api/sessions/{sid}/audit")
    async def audit(sid: str):
        session = commerce.snapshot(sid)
        return JSONResponse(
            {
                "format": "counterseal.audit.v1",
                "algorithm": "SHA-256",
                "canonicalization": "UTF-8 JSON, sorted keys, no whitespace, unescaped Unicode; hash covers every entry field except hash",
                "session_id": sid,
                "head": session["audit_head"],
                "entries": session["events"],
                "verification": session["verification"],
                "note": "This chain is not independently anchored. Save the head separately to detect tail truncation or a full rewrite.",
            },
            headers={"Content-Disposition": f'attachment; filename="counterseal-{sid[:8]}.json"'},
        )

    @app.post("/api/integrations/razorpay/check")
    async def check_razorpay():
        return await commerce.payments.discover()

    return app


app = create_app()
