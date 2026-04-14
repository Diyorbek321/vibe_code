"""
Scheduled report service — sends automatic Telegram reports to all linked users.

Schedule (Tashkent time, Asia/Tashkent = UTC+5):
  Daily   — every day at 09:00, yesterday's summary
  Weekly  — every Monday at 09:00, last week's summary
  Monthly — 1st of every month at 09:00, last month's full report

Only users with telegram_user_id set receive reports.
Each user gets their own company's data (full isolation preserved).
"""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

# Tashkent is UTC+5
TASHKENT_TZ = "Asia/Tashkent"


# ── Report generators ──────────────────────────────────────────────────────────

async def _send_daily_reports(bot) -> None:
    """Send yesterday's income/expense summary to every linked user."""
    from app.core.db import get_session_factory
    from app.models.user import User
    from app.routers.analytics import _summary_for_period
    from sqlalchemy import select

    now = datetime.now(timezone.utc)
    yesterday_start = (now - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    yesterday_end = yesterday_start.replace(
        hour=23, minute=59, second=59
    )
    date_label = yesterday_start.strftime("%d.%m.%Y")

    async with get_session_factory()() as db:
        result = await db.execute(
            select(User).where(User.telegram_user_id.isnot(None), User.is_active == True)
        )
        users = result.scalars().all()

        for user in users:
            try:
                summary = await _summary_for_period(
                    user.company_id, yesterday_start, yesterday_end, db
                )
                if summary.transaction_count == 0:
                    continue  # No transactions yesterday — skip silently

                net = float(summary.net)
                net_sign = "+" if net >= 0 else ""
                net_emoji = "📈" if net >= 0 else "📉"

                text = (
                    f"☀️ <b>{date_label} kungi hisobot</b>\n\n"
                    f"📈 Daromad: <b>{float(summary.total_income):,.0f} so'm</b>\n"
                    f"📉 Xarajat: <b>{float(summary.total_expense):,.0f} so'm</b>\n"
                    f"{'─' * 28}\n"
                    f"{net_emoji} Sof: <b>{net_sign}{net:,.0f} so'm</b>\n"
                    f"📋 Operatsiyalar: {summary.transaction_count} ta\n"
                )

                if summary.by_category:
                    top = summary.by_category[:3]
                    text += "\n<b>Top toifalar:</b>\n"
                    for cat in top:
                        name = cat.category_name or "Noma'lum"
                        text += f"  • {name}: {float(cat.total):,.0f} so'm\n"

                await bot.send_message(
                    chat_id=int(user.telegram_user_id),
                    text=text,
                    parse_mode="HTML",
                )
                logger.debug("Daily report sent to user %s", user.id)

            except Exception as exc:
                logger.warning("Failed to send daily report to user %s: %s", user.id, exc)


async def _send_weekly_reports(bot) -> None:
    """Send last week's summary every Monday morning."""
    from app.core.db import get_session_factory
    from app.models.user import User
    from app.routers.analytics import _summary_for_period
    from sqlalchemy import select

    now = datetime.now(timezone.utc)
    # Last week: Monday 00:00 → Sunday 23:59
    week_start = (now - timedelta(days=now.weekday() + 7)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    label = f"{week_start.strftime('%d.%m')} – {week_end.strftime('%d.%m.%Y')}"

    async with get_session_factory()() as db:
        result = await db.execute(
            select(User).where(User.telegram_user_id.isnot(None), User.is_active == True)
        )
        users = result.scalars().all()

        for user in users:
            try:
                summary = await _summary_for_period(
                    user.company_id, week_start, week_end, db
                )
                if summary.transaction_count == 0:
                    continue

                net = float(summary.net)
                net_sign = "+" if net >= 0 else ""

                text = (
                    f"📅 <b>Haftalik hisobot ({label})</b>\n\n"
                    f"📈 Jami daromad: <b>{float(summary.total_income):,.0f} so'm</b>\n"
                    f"📉 Jami xarajat: <b>{float(summary.total_expense):,.0f} so'm</b>\n"
                    f"{'─' * 28}\n"
                    f"💰 Sof foyda: <b>{net_sign}{net:,.0f} so'm</b>\n"
                    f"📋 Jami operatsiyalar: {summary.transaction_count} ta\n"
                )

                if summary.by_category:
                    text += "\n<b>📂 Toifalar bo'yicha:</b>\n"
                    for cat in summary.by_category[:5]:
                        name = cat.category_name or "Noma'lum"
                        text += f"  • {name}: {cat.total:,.0f} so'm ({cat.count} ta)\n"

                await bot.send_message(
                    chat_id=int(user.telegram_user_id),
                    text=text,
                    parse_mode="HTML",
                )
                logger.debug("Weekly report sent to user %s", user.id)

            except Exception as exc:
                logger.warning("Failed to send weekly report to user %s: %s", user.id, exc)


async def _send_monthly_reports(bot) -> None:
    """Send last month's full report on the 1st of each month."""
    from app.core.db import get_session_factory
    from app.models.user import User
    from app.routers.analytics import _summary_for_period
    from sqlalchemy import select

    now = datetime.now(timezone.utc)
    # Last month
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = first_of_this_month - timedelta(seconds=1)
    last_month_start = last_month_end.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    month_name = last_month_start.strftime("%B %Y")

    async with get_session_factory()() as db:
        result = await db.execute(
            select(User).where(User.telegram_user_id.isnot(None), User.is_active == True)
        )
        users = result.scalars().all()

        for user in users:
            try:
                summary = await _summary_for_period(
                    user.company_id, last_month_start, last_month_end, db
                )
                if summary.transaction_count == 0:
                    continue

                net = float(summary.net)
                net_sign = "+" if net >= 0 else ""
                net_emoji = "✅" if net >= 0 else "⚠️"

                text = (
                    f"📊 <b>{month_name} — Oylik hisobot</b>\n\n"
                    f"📈 Jami daromad:  <b>{float(summary.total_income):,.0f} so'm</b>\n"
                    f"📉 Jami xarajat:  <b>{float(summary.total_expense):,.0f} so'm</b>\n"
                    f"{'─' * 30}\n"
                    f"{net_emoji} Sof foyda: <b>{net_sign}{net:,.0f} so'm</b>\n"
                    f"📋 Operatsiyalar: {summary.transaction_count} ta\n"
                )

                if summary.by_category:
                    income_cats = [c for c in summary.by_category
                                   if float(summary.total_income) > 0]
                    expense_cats = [c for c in summary.by_category
                                    if float(summary.total_expense) > 0]

                    text += "\n<b>📂 Toifalar bo'yicha:</b>\n"
                    for cat in summary.by_category[:8]:
                        name = cat.category_name or "Noma'lum"
                        pct = (float(cat.total) / max(
                            float(summary.total_income) + float(summary.total_expense), 1
                        ) * 100)
                        text += f"  • {name}: {float(cat.total):,.0f} so'm ({pct:.0f}%)\n"

                text += f"\n/report — batafsil ma'lumot"

                await bot.send_message(
                    chat_id=int(user.telegram_user_id),
                    text=text,
                    parse_mode="HTML",
                )
                logger.info("Monthly report sent to user %s", user.id)

            except Exception as exc:
                logger.warning("Failed to send monthly report to user %s: %s", user.id, exc)


# ── Scheduler lifecycle ────────────────────────────────────────────────────────

def create_scheduler(bot) -> AsyncIOScheduler:
    """Create and configure the scheduler with all report jobs."""
    scheduler = AsyncIOScheduler(timezone=TASHKENT_TZ)

    # Daily at 09:00 Tashkent time
    scheduler.add_job(
        _send_daily_reports,
        trigger=CronTrigger(hour=9, minute=0, timezone=TASHKENT_TZ),
        args=[bot],
        id="daily_report",
        name="Daily summary report",
        replace_existing=True,
        misfire_grace_time=300,  # allow up to 5 min late start
    )

    # Weekly: every Monday at 09:00
    scheduler.add_job(
        _send_weekly_reports,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=TASHKENT_TZ),
        args=[bot],
        id="weekly_report",
        name="Weekly summary report",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Monthly: 1st of each month at 09:00
    scheduler.add_job(
        _send_monthly_reports,
        trigger=CronTrigger(day=1, hour=9, minute=0, timezone=TASHKENT_TZ),
        args=[bot],
        id="monthly_report",
        name="Monthly full report",
        replace_existing=True,
        misfire_grace_time=3600,  # 1 hour grace for monthly
    )

    return scheduler


def start_scheduler(bot) -> AsyncIOScheduler:
    global _scheduler
    _scheduler = create_scheduler(bot)
    _scheduler.start()
    logger.info(
        "Scheduler started — daily@09:00, weekly(Mon)@09:00, monthly(1st)@09:00 [%s]",
        TASHKENT_TZ,
    )
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None
