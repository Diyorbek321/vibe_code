import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class BudgetCreate(BaseModel):
    category_id: uuid.UUID
    month: date = Field(..., description="First day of the target month (YYYY-MM-01)")
    limit_amount: Decimal = Field(..., gt=0)
    alert_threshold: float = Field(default=0.8, ge=0.1, le=1.0)


class BudgetOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    company_id: uuid.UUID
    category_id: uuid.UUID
    month: date
    limit_amount: Decimal
    alert_threshold: float
    alert_sent: bool
    created_at: datetime


class BudgetStatus(BaseModel):
    """Real-time budget consumption status returned alongside budget info."""
    budget: BudgetOut
    spent: Decimal
    remaining: Decimal
    usage_pct: float          # 0.0 – 1.0
    over_budget: bool
    alert_triggered: bool     # True if usage_pct >= alert_threshold
