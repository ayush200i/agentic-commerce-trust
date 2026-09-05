import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.local")


def razorpay_ready() -> bool:
    return os.getenv("RAZORPAY_KEY_ID", "").startswith("rzp_test_") and bool(os.getenv("RAZORPAY_KEY_SECRET"))


def capabilities() -> dict:
    return {
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "razorpay_configured": razorpay_ready(),
        "razorpay_endpoint": "https://mcp.razorpay.com/mcp",
        "payment_environment": "test only",
        "default_agent_mode": "rehearsal",
    }
