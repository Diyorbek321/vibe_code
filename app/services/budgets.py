"""
Budget service — monthly limits per category + Telegram alerts.

Alert logic:
  After every transaction write, check_budget_alert() is called.
  If (spent / limit) >= alert_threshold AND alert not yet sent this month:
    → send Telegram message to company.telegram_chat_id
    → set budget.alert_sent = True (prevents repeat messages)
"""
import logging
import uuid
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget
from app.models.category import Category
from app.models.company import Company
from app.models.transaction import Transaction
from app.schemas.budget import BudgetCreate, BudgetOut, BudgetStatus

logger = logging.getLogger(__name__)


async def create_budget(
    company_id: uuid.UUID, data: BudgetCreate, db: AsyncSession
) -> BudgetOut:
    # Enforce one budget per category per month
    existing = await db.execute(
        select(Budget).where(
            Budget.company_id == company_id,
            Budget.category_id == data.category_id,
            Budget.month == data.month,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Budget for this category and month already exists",
        )

    budget = Budget(
        company_id=company_id,
        category_id=data.category_id,
        month=data.month,
        limit_amount=data.limit_amount,
        alert_threshold=data.alert_threshold,
    )
    db.add(budget)
    await db.flush()
    return BudgetOut.model_validate(budget)


async def list_budgets(company_id: uuid.UUID, db: AsyncSession) -> list[BudgetOut]:
    result = await db.execute(
        select(Budget)
        .where(Budget.company_id == company_id)
        .order_by(Budget.month.desc(), Budget.created_at)
    )
    return [BudgetOut.model_validate(b) for b in result.scalars().all()]


async def get_budget_status(
    company_id: uuid.UUID, budget_id: uuid.UUID, db: AsyncSession
) -> BudgetStatus:
    result = await db.execute(
        select(Budget).where(
            Budget.id == budget_id,
            Budget.company_id == company_id,
        )
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    spent = await _get_monthly_spend(company_id, budget.category_id, budget.month, db)
    limit = Decimal(str(budget.limit_amount))
    remaining = max(limit - spent, Decimal("0"))
    usage_pct = float(spent / limit) if limit > 0 else 0.0

    return BudgetStatus(
        budget=BudgetOut.model_validate(budget),
        spent=spent,
        remaining=remaining,
        usage_pct=usage_pct,
        over_budget=spent > limit,
        alert_triggered=usage_pct >= budget.alert_threshold,
    )


async def check_budget_alert(
    company_id: uuid.UUID,
    category_id: uuid.UUID | None,
    db: AsyncSession,
    bot=None,  # aiogram Bot instance — optional
) -> None:
    """
    Called after every transaction save.
    If any budget threshold is crossed for this category this month,
    sends a Telegram alert (if bot is provided) and marks alert_sent.
    """
    if category_id is None:
        return

    today = date.today()
    month_start = today.replace(day=1)

    result = await db.execute(
        select(Budget).where(
            Budget.company_id == company_id,
            Budget.category_id == category_id,
            Budget.month == month_start,
            Budget.alert_sent == False,  # noqa: E712
        )
    )
    budget = result.scalar_one_or_none()
    if not budget:
        return  # No active budget or alert already sent

    spent = await _get_monthly_spend(company_id, category_id, month_start, db)
    limit = Decimal(str(budget.limit_amount))
    usage_pct = float(spent / limit) if limit > 0 else 0.0

    if usage_pct >= budget.alert_threshold:
        budget.alert_sent = True
        await db.flush()
        logger.info(
            "Budget alert triggered: company=%s category=%s pct=%.1f%%",
            company_id, category_id, usage_pct * 100,
        )

        if bot:
            await _send_budget_alert(company_id, budget, spent, limit, usage_pct, db, bot)


async def _get_monthly_spend(
    company_id: uuid.UUID,
    category_id: uuid.UUID,
    month_start: date,
    db: AsyncSession,
) -> Decimal:
    """Sum all non-deleted expense transactions for this category in the given month."""
    from calendar import monthrange

    year, month = month_start.year, month_start.month
    last_day = monthrange(year, month)[1]
    month_end = date(year, month, last_day)

    result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.company_id == company_id,
            Transaction.category_id == category_id,
            Transaction.type == "expense",
            Transaction.is_deleted == False,  # noqa: E712
            func.date(Transaction.date) >= month_start,
            func.date(Transaction.date) <= month_end,
        )
    )
    return Decimal(str(result.scalar_one() or 0))


async def _send_budget_alert(
    company_id: uuid.UUID,
    budget: Budget,
    spent: Decimal,
    limit: Decimal,
    usage_pct: float,
    db: AsyncSession,
    bot,
) -> None:
    """Format and send the Telegram budget alert message."""
    # Fetch company chat_id
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company or not company.telegram_chat_id:
        logger.warning("No telegram_chat_id for company %s — skipping alert", company_id)
        return

    # Fetch category name
    cat_result = await db.execute(
        select(Category).where(Category.id == budget.category_id)
    )
    category = cat_result.scalar_one_or_none()
    cat_name = category.name if category else "Noma'lum"

    message = (
        f"⚠️ <b>Byudjet ogohlantirish!</b>\n\n"
        f"📂 Toifa: <b>{cat_name}</b>\n"
        f"📅 Oy: <b>{budget.month.strftime('%Y-%m')}</b>\n"
        f"💸 Sarflangan: <b>{spent:,.0f} so'm</b>\n"
        f"🎯 Chegara: <b>{limit:,.0f} so'm</b>\n"
        f"📊 Foydalanish: <b>{usage_pct:.0%}</b>\n\n"
        f"{'🔴 Byudjet oshib ketdi!' if spent > limit else '🟡 Chegara yaqinlashdi!'}"
    )

    try:
        await bot.send_message(
            chat_id=company.telegram_chat_id,
            text=message,
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.error("Failed to send budget alert: %s", exc)
