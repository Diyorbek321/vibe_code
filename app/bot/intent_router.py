"""
Intent routing: maps NLP-extracted intent to the correct handler function.
Each handler receives the full message context and the FastAPI app for DB access.
"""
import logging
from datetime import datetime, timezone

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder

from app.bot.fsm import TransactionFSM
from app.bot.keyboards import confirm_transaction_kb, edit_field_kb
from app.bot.validation import validate_extracted_transaction, ValidationError
from app.core.db import get_session_factory
from app.services import nlp, transactions as tx_service
from app.services.budgets import check_budget_alert
from app.services.categories import resolve_category_by_name
from app.services.nlp import AmbiguousInputError
from app.schemas.transaction import TransactionCreate

logger = logging.getLogger(__name__)


async def _get_user_from_telegram(telegram_user_id: str, db) -> "User | None":
    """Look up a User by their Telegram user_id for company resolution."""
    from sqlalchemy import select
    from app.models.user import User
    result = await db.execute(
        select(User).where(User.telegram_user_id == telegram_user_id)
    )
    return result.scalar_one_or_none()


# ── Income / Expense ──────────────────────────────────────────────────────────

async def handle_income_expense(
    intent: str,
    text: str,
    message: Message,
    app: FastAPI,
    state: FSMContext,
    pre_extracted: dict | None = None,
) -> str:
    """
    Full pipeline for income/expense with confirmation step:
    1. LLM extraction (skipped when pre_extracted is provided — saves one API call)
    2. Strict validation
    3. Show confirmation keyboard — actual DB write happens in callback handler
    """
    if pre_extracted is not None:
        extracted = pre_extracted
    else:
        try:
            extracted = await nlp.extract_transaction(text)
        except AmbiguousInputError:
            raise  # re-raise so handler can ask follow-up

    try:
        validated = validate_extracted_transaction(extracted)
    except ValidationError as exc:
        return f"❌ Ma'lumot noto'g'ri:\n{exc.user_message}"

    # Store pending transaction in FSM — saved on confirmation
    await state.set_state(TransactionFSM.confirming)
    await state.update_data(pending_tx=validated)

    sign = "+" if validated["type"] == "income" else "-"
    amount_fmt = f"{float(validated['amount']):,.0f}"
    preview = (
        f"{'📈 Daromad' if validated['type'] == 'income' else '📉 Xarajat'}: "
        f"<b>{sign}{amount_fmt} so'm</b>\n"
        f"📂 Toifa: {validated.get('category', 'Boshqa')}\n"
        f"📅 Sana: {validated['date'].strftime('%d.%m.%Y')}\n"
    )
    if validated.get("description"):
        preview += f"📝 Izoh: {validated['description']}\n"

    await message.answer(
        f"Quyidagi ma'lumotni saqlaysizmi?\n\n{preview}",
        reply_markup=confirm_transaction_kb(),
    )
    return ""  # answer already sent with keyboard


async def _notify_dashboard(company_id, event_type: str, data: dict) -> None:
    """
    Push an SSE event to the FastAPI app's broadcaster via internal HTTP.
    This bridges the process gap between polling-mode bot and the API server.
    Falls back silently — a failed notification never blocks a transaction save.
    """
    import httpx
    from app.core.config import settings

    url = f"{settings.INTERNAL_API_URL.rstrip('/')}/api/sse/internal/broadcast"
    headers = {"X-Internal-Secret": settings.INTERNAL_SECRET} if settings.INTERNAL_SECRET else {}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                url,
                json={
                    "company_id": str(company_id),
                    "event_type": event_type,
                    "data": data,
                },
                headers=headers,
            )
    except Exception as exc:
        logger.debug("Internal broadcast HTTP call failed (non-fatal): %s", exc)


async def _save_confirmed_transaction(
    validated: dict,
    telegram_user_id: str,
    app: FastAPI,
) -> str:
    """Persist a validated transaction after user confirmation."""
    async with get_session_factory()() as db:
        user = await _get_user_from_telegram(telegram_user_id, db)
        if not user:
            return (
                "❌ Siz tizimda ro'yxatdan o'tmagansiz. "
                "Iltimos, veb-saytda ro'yxatdan o'ting va /link buyrug'ini ishlating."
            )

        category_id = await resolve_category_by_name(
            user.company_id, validated.get("category", "Boshqa"), db
        )

        tx_data = TransactionCreate(
            amount=validated["amount"],
            type=validated["type"],
            category_id=category_id,
            description=validated.get("description"),
            date=validated["date"],
            source="telegram",
        )
        tx_out = await tx_service.create_transaction(
            user.company_id, user.id, tx_data, db
        )

        await check_budget_alert(
            user.company_id, category_id, db, bot=app.state.bot
        )

        # Commit first — data must be in DB before dashboard fetches it
        await db.commit()

    # Notify dashboard via internal HTTP (bridges bot process ↔ FastAPI process)
    event_data = jsonable_encoder(tx_out)
    await _notify_dashboard(tx_out.company_id, "transaction.created", event_data)

    sign = "+" if validated["type"] == "income" else "-"
    amount_fmt = f"{float(validated['amount']):,.0f}"
    return (
        f"✅ Saqlandi!\n\n"
        f"{'📈 Daromad' if validated['type'] == 'income' else '📉 Xarajat'}: "
        f"<b>{sign}{amount_fmt} so'm</b>\n"
        f"📂 Toifa: {validated.get('category', 'Boshqa')}\n"
        f"📅 Sana: {validated['date'].strftime('%d.%m.%Y')}\n"
        + (f"📝 Izoh: {validated['description']}" if validated.get("description") else "")
    )


# ── Query / Report ────────────────────────────────────────────────────────────

async def handle_query(
    text: str,
    message: Message,
    app: FastAPI,
    pre_parsed_period: dict | None = None,
) -> str:
    """
    Parse a natural-language query, run aggregated SQL, return formatted answer.
    Example: "Bu hafta qancha xarajat bo'ldi?"

    pre_parsed_period: if provided (from classify_and_extract), skips the
    second LLM call to parse_query_period — halves latency for query intents.
    """
    telegram_user_id = str(message.from_user.id)

    async with get_session_factory()() as db:
        user = await _get_user_from_telegram(telegram_user_id, db)
        if not user:
            return "❌ Tizimda ro'yxatdan o'tmagansiz."

        # Use pre-parsed period if available; otherwise fall back to LLM call
        if pre_parsed_period and pre_parsed_period.get("start_date"):
            period = pre_parsed_period
        else:
            try:
                period = await nlp.parse_query_period(text)
            except Exception:
                return "Savol tushunarli bo'lmadi. Iltimos, aniqroq yozing."

        from app.routers.analytics import _summary_for_period

        try:
            start = datetime.fromisoformat(period["start_date"]).replace(tzinfo=timezone.utc)
            end = datetime.fromisoformat(period["end_date"]).replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except (KeyError, ValueError):
            return "Sana formatini tushunmadim. Iltimos, qaytadan yozing."

        summary = await _summary_for_period(user.company_id, start, end, db)

    period_label = period.get("period_label", "")

    lines = [
        f"📊 <b>{period_label} hisoboti</b>\n",
        f"📈 Daromad: <b>{float(summary.total_income):,.0f} so'm</b>",
        f"📉 Xarajat: <b>{float(summary.total_expense):,.0f} so'm</b>",
        f"💰 Sof: <b>{float(summary.net):,.0f} so'm</b>",
        f"📋 Jami operatsiyalar: {summary.transaction_count} ta",
    ]

    if summary.by_category:
        lines.append("\n<b>Toifalar bo'yicha:</b>")
        for cat in summary.by_category[:5]:  # top 5
            name = cat.category_name or "Noma'lum"
            lines.append(f"  • {name}: {cat.total:,.0f} so'm ({cat.count} ta)")

    return "\n".join(lines)


async def handle_balance(message: Message, app: FastAPI) -> str:
    """Show current month income, expense, and net balance."""
    telegram_user_id = str(message.from_user.id)
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = now

    async with get_session_factory()() as db:
        user = await _get_user_from_telegram(telegram_user_id, db)
        if not user:
            return "❌ Tizimda ro'yxatdan o'tmagansiz."

        from app.routers.analytics import _summary_for_period
        summary = await _summary_for_period(user.company_id, start, end, db)

    month_name = now.strftime("%B %Y")
    net = float(summary.net)
    net_sign = "+" if net >= 0 else ""
    return (
        f"💼 <b>Joriy oy balansi ({month_name})</b>\n\n"
        f"📈 Daromad: <b>{float(summary.total_income):,.0f} so'm</b>\n"
        f"📉 Xarajat: <b>{float(summary.total_expense):,.0f} so'm</b>\n"
        f"{'─' * 28}\n"
        f"💰 Sof: <b>{net_sign}{net:,.0f} so'm</b>\n\n"
        f"📋 Jami: {summary.transaction_count} ta operatsiya"
    )


async def handle_monthly_report(message: Message, app: FastAPI) -> str:
    """Full monthly breakdown with category split."""
    telegram_user_id = str(message.from_user.id)
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = now

    async with get_session_factory()() as db:
        user = await _get_user_from_telegram(telegram_user_id, db)
        if not user:
            return "❌ Tizimda ro'yxatdan o'tmagansiz."

        from app.routers.analytics import _summary_for_period
        summary = await _summary_for_period(user.company_id, start, end, db)

    month_name = now.strftime("%B %Y")
    net = float(summary.net)
    net_sign = "+" if net >= 0 else ""

    lines = [
        f"📊 <b>{month_name} to'liq hisoboti</b>\n",
        f"📈 Jami daromad: <b>{float(summary.total_income):,.0f} so'm</b>",
        f"📉 Jami xarajat: <b>{float(summary.total_expense):,.0f} so'm</b>",
        f"💰 Sof foyda: <b>{net_sign}{net:,.0f} so'm</b>",
        f"📋 Operatsiyalar: {summary.transaction_count} ta\n",
    ]

    if summary.by_category:
        income_cats = [c for c in summary.by_category if c.total > 0]
        lines.append("<b>📂 Toifalar bo'yicha:</b>")
        for cat in income_cats[:8]:
            name = cat.category_name or "Noma'lum"
            pct = (float(cat.total) / (float(summary.total_income) + float(summary.total_expense)) * 100) if (
                float(summary.total_income) + float(summary.total_expense)
            ) > 0 else 0
            lines.append(f"  • {name}: {cat.total:,.0f} so'm ({pct:.0f}%)")

    return "\n".join(lines)


# ── Edit last ─────────────────────────────────────────────────────────────────

async def handle_edit_last(text: str, message: Message, app: FastAPI, state: FSMContext) -> str:
    """Show last transaction and present field-edit keyboard."""
    telegram_user_id = str(message.from_user.id)

    async with get_session_factory()() as db:
        user = await _get_user_from_telegram(telegram_user_id, db)
        if not user:
            return "❌ Tizimda ro'yxatdan o'tmagansiz."
        last = await tx_service.get_last_transaction(user.company_id, user.id, db)

    if not last:
        return "Tahrirlash uchun yozuv topilmadi."

    # Store in FSM
    await state.set_state(TransactionFSM.editing_field)
    await state.update_data(editing_tx_id=str(last.id))

    sign = "+" if last.type == "income" else "-"
    await message.answer(
        f"Oxirgi yozuv:\n"
        f"{'📈' if last.type == 'income' else '📉'} "
        f"<b>{sign}{float(last.amount):,.0f} so'm</b> "
        f"({last.date.strftime('%d.%m.%Y')})\n"
        f"📂 Toifa: {getattr(last, 'category_name', 'Boshqa')}\n\n"
        f"Qaysi maydonni o'zgartirmoqchisiz?",
        reply_markup=edit_field_kb(),
    )
    return ""  # keyboard already sent


# ── Delete last ───────────────────────────────────────────────────────────────

async def handle_delete_last(text: str, message: Message, app: FastAPI) -> str:
    """Soft-delete the last transaction and broadcast the event."""
    telegram_user_id = str(message.from_user.id)

    async with get_session_factory()() as db:
        user = await _get_user_from_telegram(telegram_user_id, db)
        if not user:
            return "❌ Tizimda ro'yxatdan o'tmagansiz."

        last = await tx_service.get_last_transaction(user.company_id, user.id, db)
        if not last:
            return "O'chirish uchun yozuv topilmadi."

        await tx_service.soft_delete_transaction(user.company_id, last.id, db)
        await db.commit()

    await _notify_dashboard(last.company_id, "transaction.deleted", {"id": str(last.id)})

    return (
        f"🗑 O'chirildi: "
        f"{'📈' if last.type == 'income' else '📉'} "
        f"{float(last.amount):,.0f} so'm ({last.date.strftime('%d.%m.%Y')})"
    )
