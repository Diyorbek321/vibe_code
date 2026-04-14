"""
Analytics router — aggregated summaries and period comparisons.
All queries use raw SQL aggregations for performance (no N+1 loading).
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CompanyID, DB
from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.analytics import AnalyticsSummary, CategoryBreakdown, PeriodComparison

router = APIRouter(prefix="/analytics", tags=["analytics"])


async def _summary_for_period(
    company_id,
    start: datetime,
    end: datetime,
    db: AsyncSession,
) -> AnalyticsSummary:
    """
    Build an AnalyticsSummary for [start, end] using two aggregation queries.
    """
    # 1. Totals query
    totals = await db.execute(
        select(
            Transaction.type,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count(Transaction.id).label("cnt"),
        )
        .where(
            Transaction.company_id == company_id,
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(Transaction.type)
    )

    income = 0
    expense = 0
    tx_count = 0
    for row in totals.all():
        if row.type == "income":
            income = float(row.total)
        else:
            expense = float(row.total)
        tx_count += row.cnt

    # 2. Category breakdown query (expense + income separately)
    breakdown_rows = await db.execute(
        select(
            Transaction.category_id,
            Category.name.label("cat_name"),
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .join(Category, Transaction.category_id == Category.id, isouter=True)
        .where(
            Transaction.company_id == company_id,
            Transaction.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(Transaction.category_id, Category.name)
        .order_by(func.sum(Transaction.amount).desc())
    )

    by_category = [
        CategoryBreakdown(
            category_id=str(row.category_id) if row.category_id else None,
            category_name=row.cat_name,
            total=float(row.total),
            count=row.count,
        )
        for row in breakdown_rows.all()
    ]

    return AnalyticsSummary(
        period_start=start,
        period_end=end,
        total_income=income,
        total_expense=expense,
        net=income - expense,
        transaction_count=tx_count,
        by_category=by_category,
    )


@router.get("/summary", response_model=AnalyticsSummary)
async def summary(
    company_id: CompanyID,
    db: DB,
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
) -> AnalyticsSummary:
    """Return aggregated income/expense summary for the given period."""
    return await _summary_for_period(company_id, date_from, date_to, db)


@router.get("/comparison", response_model=PeriodComparison)
async def period_comparison(
    company_id: CompanyID,
    db: DB,
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
) -> PeriodComparison:
    """
    Compare current period vs equivalent previous period.
    E.g. this week vs last week.
    """
    duration = date_to - date_from
    prev_start = date_from - duration - timedelta(seconds=1)
    prev_end = date_from - timedelta(seconds=1)

    current, previous = (
        await _summary_for_period(company_id, date_from, date_to, db),
        await _summary_for_period(company_id, prev_start, prev_end, db),
    )

    def _pct_change(new: float, old: float) -> float | None:
        if old == 0:
            return None
        return round((new - old) / old * 100, 2)

    return PeriodComparison(
        current=current,
        previous=previous,
        income_change_pct=_pct_change(float(current.total_income), float(previous.total_income)),
        expense_change_pct=_pct_change(float(current.total_expense), float(previous.total_expense)),
    )
