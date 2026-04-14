import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TransactionCreate(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Positive amount in UZS")
    type: Literal["income", "expense"]
    category_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=1000)
    date: datetime
    source: Literal["telegram", "web"] = "web"

    @field_validator("amount")
    @classmethod
    def round_amount(cls, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"))


class TransactionUpdate(BaseModel):
    """All fields optional — partial update (PATCH semantics)."""
    amount: Decimal | None = Field(None, gt=0)
    type: Literal["income", "expense"] | None = None
    category_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=1000)
    date: datetime | None = None
    # version must be sent to detect conflicts (optimistic lock)
    version: int = Field(..., description="Current version number for optimistic locking")

    @field_validator("amount")
    @classmethod
    def round_amount(cls, v: Decimal | None) -> Decimal | None:
        return v.quantize(Decimal("0.01")) if v is not None else None


class TransactionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    company_id: uuid.UUID
    user_id: uuid.UUID | None
    category_id: uuid.UUID | None
    amount: Decimal
    type: str
    description: str | None
    source: str
    date: datetime
    version: int
    created_at: datetime
    updated_at: datetime


class TransactionList(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    limit: int
