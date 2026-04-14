from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CategoryBreakdown(BaseModel):
    category_id: str | None
    category_name: str | None
    total: Decimal
    count: int


class AnalyticsSummary(BaseModel):
    period_start: datetime
    period_end: datetime
    total_income: Decimal
    total_expense: Decimal
    net: Decimal                       # income - expense
    transaction_count: int
    by_category: list[CategoryBreakdown]


class PeriodComparison(BaseModel):
    current: AnalyticsSummary
    previous: AnalyticsSummary
    income_change_pct: float | None    # None if previous was 0
    expense_change_pct: float | None
