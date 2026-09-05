from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Policy(StrictModel):
    spend_cap: int = Field(default=500000, ge=100, le=10000000, strict=True)
    approval_threshold: int = Field(default=300000, ge=0, le=10000000, strict=True)
    categories: list[Literal["keyboards", "accessories", "audio"]] = Field(
        default_factory=lambda: ["keyboards", "accessories"], min_length=1, max_length=3
    )


class StartSession(StrictModel):
    goal: str = Field(min_length=5, max_length=600)
    policy: Policy = Field(default_factory=Policy)
    agent_mode: Literal["rehearsal", "openai"] = "rehearsal"
    payment_mode: Literal["simulated", "razorpay"] = "simulated"
    inject_stock_failure: bool = True


class Decision(StrictModel):
    product_id: str
    summary: str = Field(max_length=500)


class Offer(StrictModel):
    discount_percent: Literal[0, 5, 8]
    include_mat: bool
    summary: str = Field(max_length=500)


class Approval(StrictModel):
    approved: bool
    quote_hash: str = Field(min_length=64, max_length=64)


class PaymentConfirmation(StrictModel):
    razorpay_payment_id: str = Field(pattern=r"^pay_[A-Za-z0-9]+$", max_length=80)
    razorpay_order_id: str = Field(pattern=r"^order_[A-Za-z0-9]+$", max_length=80)
    razorpay_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
