"""
aiogram 3.x message handlers.

Entry points:
  - /start      → welcome + link Telegram user to DB account
  - /help       → command list
  - /balance    → current month balance
  - /report     → current month full report
  - /link       → associate Telegram account with web account
  - voice       → download OGG → STT → same pipeline as text
  - text        → classify intent → route to intent_router handlers
  - callback    → inline keyboard responses (confirm/cancel, edit field)

FSM clarification flow:
  If NLP returns AmbiguousInputError, bot stores the partial context in FSM
  and asks the follow-up question.  The next message from the user in
  `waiting_clarification` state is used to retry extraction with combined text.

Confirmation flow:
  After extraction succeeds the bot shows a confirm/cancel keyboard.
  The transaction is only written to DB after the user taps "✅ Saqlash".

Edit flow:
  /oxirgi yozuvni tahrirlash → field-picker keyboard → value input → PATCH
"""
import logging
import uuid

from aiogram import Dispatcher, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.fsm import TransactionFSM, RegistrationFSM
from app.bot.intent_router import (
    _get_user_from_telegram,
    _save_confirmed_transaction,
    handle_balance,
    handle_delete_last,
    handle_edit_last,
    handle_income_expense,
    handle_monthly_report,
    handle_query,
)
from app.bot.keyboards import DEFAULT_CATEGORIES, category_kb
from app.services import nlp
from app.services.nlp import (
    AmbiguousInputError,
    INTENT_DELETE_LAST,
    INTENT_EDIT_LAST,
    INTENT_EXPENSE,
    INTENT_HELP,
    INTENT_INCOME,
    INTENT_QUERY,
    INTENT_REPORT,
    classify_intent,
    classify_and_extract,
)
from app.services.stt import transcribe_audio

logger = logging.getLogger(__name__)

router = Router(name="main")

HELP_TEXT = """
🤖 <b>Moliyaviy Bot</b>

📝 <b>Matn orqali kiritish:</b>
<i>Bugun 500,000 so'm savdo tushdi</i>
<i>Kecha 120,000 so'm kommunal to'lovim ketdi</i>

🎤 <b>Ovozli xabar:</b> Mikrofon tugmasini bosib gapiring

🧾 <b>Chek rasmi:</b> Chek yoki kvitansiya rasmini yuboring — bot avtomatik o'qiydi

📊 <b>Hisobot va statistika:</b>
<i>Bu hafta qancha xarajat bo'ldi?</i>
<i>Shu oy daromad hisobotini ko'rsat</i>

<b>Buyruqlar:</b>
💼 /balance    — joriy oy balansi
📋 /report     — joriy oy to'liq hisoboti
📈 /stats      — haftalik taqqoslama
📂 /categories — toifalar ro'yxati

✏️ <b>Tahrirlash:</b> <i>Oxirgi yozuvni o'zgartir</i>
🗑 <b>O'chirish:</b>  <i>Oxirgi yozuvni o'chir</i>

🔔 <b>Avtomatik hisobotlar:</b>
  • Har kuni 09:00 — kechagi xulosa
  • Har dushanba  — haftalik hisobot
  • Har oyning 1-si — oylik hisobot

🔗 /link — veb-akkauntni ulash
❓ /help — ushbu yordam xabarini ko'rsatish
"""


def register_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)


# ── /start command ────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """
    If the user already has a linked account → show balance.
    If not → start the inline registration flow (no need for /link).
    """
    from app.core.db import get_session_factory

    telegram_user_id = str(message.from_user.id)

    async with get_session_factory()() as db:
        user = await _get_user_from_telegram(telegram_user_id, db)

    if user:
        # Already registered — just greet and show help
        await message.answer(
            f"Assalomu alaykum, <b>{user.full_name}</b>! 👋\n\n"
            f"Xush kelibsiz! Moliya botingiz tayyor.\n"
            + HELP_TEXT
        )
        return

    # New user — start registration
    await state.set_state(RegistrationFSM.waiting_full_name)
    await message.answer(
        f"Assalomu alaykum, <b>{message.from_user.full_name}</b>! 👋\n\n"
        "Men moliyaviy yordamchingizman. Ro'yxatdan o'tish uchun "
        "bir necha savollarga javob bering.\n\n"
        "👤 <b>Ismingiz va familiyangizni</b> kiriting:\n"
        "<i>Misol: Jasur Toshmatov</i>"
    )


# ── /help command ─────────────────────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


# ── /balance command ──────────────────────────────────────────────────────────

@router.message(Command("balance"))
async def cmd_balance(message: Message) -> None:
    from app.main import _app_ref
    reply = await handle_balance(message, _app_ref)
    await message.answer(reply)


# ── /report command ───────────────────────────────────────────────────────────

@router.message(Command("report"))
async def cmd_report(message: Message) -> None:
    from app.main import _app_ref
    reply = await handle_monthly_report(message, _app_ref)
    await message.answer(reply)


# ── /stats command ───────────────────────────────────────────────────────────

@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """Week-over-week comparison."""
    from datetime import timedelta
    from app.main import _app_ref
    from app.bot.intent_router import _get_user_from_telegram
    from app.core.db import get_session_factory
    from app.routers.analytics import _summary_for_period
    from datetime import datetime, timezone

    telegram_user_id = str(message.from_user.id)
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    prev_start = week_start - timedelta(weeks=1)
    prev_end = week_start - timedelta(seconds=1)

    async with get_session_factory()() as db:
        user = await _get_user_from_telegram(telegram_user_id, db)
        if not user:
            await message.answer("❌ Tizimda ro'yxatdan o'tmagansiz.")
            return
        current = await _summary_for_period(user.company_id, week_start, now, db)
        previous = await _summary_for_period(user.company_id, prev_start, prev_end, db)

    def _pct(new: float, old: float) -> str:
        if old == 0:
            return "—"
        pct = (new - old) / old * 100
        return f"{'+' if pct >= 0 else ''}{pct:.0f}%"

    cur_inc = float(current.total_income)
    cur_exp = float(current.total_expense)
    prv_inc = float(previous.total_income)
    prv_exp = float(previous.total_expense)

    await message.answer(
        f"📈 <b>Haftalik taqqoslama</b>\n\n"
        f"<b>Bu hafta:</b>\n"
        f"  Daromad: {cur_inc:,.0f} so'm\n"
        f"  Xarajat: {cur_exp:,.0f} so'm\n"
        f"  Sof: {float(current.net):,.0f} so'm\n\n"
        f"<b>O'tgan hafta:</b>\n"
        f"  Daromad: {prv_inc:,.0f} so'm\n"
        f"  Xarajat: {prv_exp:,.0f} so'm\n"
        f"  Sof: {float(previous.net):,.0f} so'm\n\n"
        f"<b>O'zgarish:</b>\n"
        f"  Daromad: {_pct(cur_inc, prv_inc)}\n"
        f"  Xarajat: {_pct(cur_exp, prv_exp)}"
    )


# ── /categories command ───────────────────────────────────────────────────────

@router.message(Command("categories"))
async def cmd_categories(message: Message) -> None:
    """List all categories for this company."""
    from app.main import _app_ref
    from app.bot.intent_router import _get_user_from_telegram
    from app.core.db import get_session_factory
    from app.services.categories import list_categories

    telegram_user_id = str(message.from_user.id)

    async with get_session_factory()() as db:
        user = await _get_user_from_telegram(telegram_user_id, db)
        if not user:
            await message.answer("❌ Tizimda ro'yxatdan o'tmagansiz.")
            return
        cats = await list_categories(user.company_id, db)

    income_cats = [c for c in cats if c.type == "income"]
    expense_cats = [c for c in cats if c.type == "expense"]

    lines = ["📂 <b>Toifalar ro'yxati</b>\n"]
    if income_cats:
        lines.append("📈 <b>Daromad:</b>")
        lines.extend(f"  • {c.name}" for c in income_cats)
    if expense_cats:
        lines.append("\n📉 <b>Xarajat:</b>")
        lines.extend(f"  • {c.name}" for c in expense_cats)

    await message.answer("\n".join(lines))


# ── Registration FSM steps ────────────────────────────────────────────────────

@router.message(RegistrationFSM.waiting_full_name)
async def reg_full_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("❌ Ism kamida 2 ta belgi bo'lishi kerak. Qaytadan kiriting:")
        return
    await state.update_data(full_name=name)
    await state.set_state(RegistrationFSM.waiting_company_name)
    await message.answer(
        f"✅ Yaxshi, <b>{name}</b>!\n\n"
        "🏢 <b>Kompaniyangiz nomini</b> kiriting:\n"
        "<i>Misol: Toshmatov Savdo MChJ</i>"
    )


@router.message(RegistrationFSM.waiting_company_name)
async def reg_company_name(message: Message, state: FSMContext) -> None:
    company = (message.text or "").strip()
    if len(company) < 2:
        await message.answer("❌ Kompaniya nomi kamida 2 ta belgi. Qaytadan kiriting:")
        return
    await state.update_data(company_name=company)
    await state.set_state(RegistrationFSM.waiting_email)
    await message.answer(
        "📧 <b>Email manzilingizni</b> kiriting:\n"
        "<i>Misol: jasur@toshmatov.uz</i>"
    )


@router.message(RegistrationFSM.waiting_email)
async def reg_email(message: Message, state: FSMContext) -> None:
    import re
    email = (message.text or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        await message.answer("❌ Email manzil noto'g'ri formatda. Qaytadan kiriting:")
        return
    await state.update_data(email=email)
    await state.set_state(RegistrationFSM.waiting_password)
    await message.answer(
        "🔐 <b>Parol</b> kiriting (kamida 8 ta belgi):\n\n"
        "⚠️ <i>Bu xabar yuborilgandan so'ng bot uni darhol o'chiradi.</i>"
    )


@router.message(RegistrationFSM.waiting_password)
async def handle_password(message: Message, state: FSMContext) -> None:
    """
    Single handler for the password step — works for both registration and /link.
    Branches on the 'linking' flag stored in FSM data.
    """
    password = (message.text or "").strip()

    # Delete the password message immediately for security
    try:
        await message.delete()
    except Exception:
        pass

    if len(password) < 8:
        await message.answer("❌ Parol kamida 8 ta belgi bo'lishi kerak. Qaytadan kiriting:")
        return

    data = await state.get_data()
    await state.clear()

    email = data.get("email", "")
    telegram_user_id = str(message.from_user.id)

    # ── Link mode: verify credentials and attach Telegram ID ──────────────────
    if data.get("linking"):
        from app.core.db import get_session_factory
        from app.core.security import verify_password
        from sqlalchemy import select
        from app.models.user import User

        processing = await message.answer("⏳ Tekshirilmoqda...")

        async with get_session_factory()() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if not user or not verify_password(password, user.hashed_password):
                await processing.edit_text("❌ Email yoki parol noto'g'ri.")
                return
            if not user.is_active:
                await processing.edit_text("❌ Akkaunt faol emas. Admin bilan bog'laning.")
                return

            user.telegram_user_id = telegram_user_id
            await db.commit()

        await processing.edit_text(
            f"✅ <b>Akkaunt ulandi!</b>\n\n"
            f"👤 {user.full_name}\n"
            f"🏢 Kompaniyangiz tayyor.\n\n"
            f"Endi daromad va xarajatlarni yozishingiz mumkin!\n\n"
            + HELP_TEXT
        )
        return

    # ── Registration mode: create company + user ───────────────────────────────
    full_name = data.get("full_name", "")
    company_name = data.get("company_name", "")

    if not full_name or not company_name:
        await message.answer(
            "❌ Ma'lumotlar topilmadi. Iltimos, /start dan qaytadan boshlang."
        )
        return

    from app.core.db import get_session_factory
    from app.services.auth import register_user
    from app.schemas.auth import UserCreate
    from sqlalchemy import select
    from app.models.user import User

    processing = await message.answer("⏳ Akkaunt yaratilmoqda...")

    try:
        async with get_session_factory()() as db:
            user_data = UserCreate(
                email=email,
                password=password,
                full_name=full_name,
                company_name=company_name,
            )
            await register_user(user_data, db)

            # Link Telegram ID immediately after registration
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user:
                user.telegram_user_id = telegram_user_id
            await db.commit()

        await processing.edit_text(
            f"✅ <b>Ro'yxatdan o'tdingiz!</b>\n\n"
            f"👤 {full_name}\n"
            f"🏢 {company_name}\n"
            f"📧 {email}\n\n"
            f"Endi daromad va xarajatlarni yozishingiz mumkin!\n\n"
            + HELP_TEXT
        )

    except Exception as exc:
        err = str(exc)
        if "already registered" in err.lower() or "409" in err:
            await processing.edit_text(
                f"⚠️ <b>{email}</b> allaqachon ro'yxatdan o'tgan.\n\n"
                "Mavjud akkauntni ulash uchun /link ni bosing."
            )
        else:
            logger.error("Registration failed for %s: %s", email, exc)
            await processing.edit_text(
                "❌ Ro'yxatdan o'tishda xatolik yuz berdi.\n"
                "Iltimos, qaytadan /start ni bosing."
            )


# ── /link command ─────────────────────────────────────────────────────────────

@router.message(Command("link"))
async def cmd_link(message: Message, state: FSMContext) -> None:
    """
    Securely link an existing web account to this Telegram account.
    Password is requested via FSM and deleted immediately after entry.
    """
    from app.core.db import get_session_factory

    telegram_user_id = str(message.from_user.id)

    async with get_session_factory()() as db:
        user = await _get_user_from_telegram(telegram_user_id, db)

    if user:
        await message.answer(
            f"✅ Akkaunt allaqachon ulangan: <b>{user.full_name}</b>\n"
            "Yangi akkaunt ulash uchun avval /unlink yozing."
        )
        return

    await state.set_state(RegistrationFSM.waiting_email)
    await state.update_data(linking=True)
    await message.answer(
        "🔗 <b>Akkauntni ulash</b>\n\n"
        "📧 Veb-saytda ro'yxatdan o'tgan <b>email manzilingizni</b> kiriting:"
    )


# ── Photo / receipt OCR handler ───────────────────────────────────────────────

@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext) -> None:
    """
    Receipt OCR pipeline:
      1. Download highest-resolution photo from Telegram
      2. Send to Groq vision API for structured extraction
      3. Show confirmation keyboard — same flow as text/voice entry
    """
    from app.bot.intent_router import _get_user_from_telegram
    from app.core.db import get_session_factory
    from app.services.ocr import extract_from_receipt
    from app.services.nlp import AmbiguousInputError
    from app.bot.validation import validate_extracted_transaction

    telegram_user_id = str(message.from_user.id)

    # Check user is linked
    async with get_session_factory()() as db:
        user = await _get_user_from_telegram(telegram_user_id, db)

    if not user:
        await message.answer(
            "❌ Tizimda ro'yxatdan o'tmagansiz.\n"
            "Ro'yxatdan o'tish uchun /start ni bosing."
        )
        return

    processing = await message.answer("🧾 Chek tahlil qilyapman...")

    try:
        bot = message.bot
        # Use the largest available photo size
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes_io = await bot.download_file(file.file_path)
        image_bytes = file_bytes_io.read() if hasattr(file_bytes_io, "read") else bytes(file_bytes_io)

        # Detect MIME type from file extension
        mime = "image/jpeg"
        if file.file_path and file.file_path.endswith(".png"):
            mime = "image/png"

        extracted = await extract_from_receipt(image_bytes, mime_type=mime)

    except AmbiguousInputError as exc:
        await processing.edit_text(
            f"🧾 Chek o'qildi, lekin bir savol bor:\n\n{exc.follow_up_question}"
        )
        await state.set_state(TransactionFSM.waiting_clarification)
        await state.update_data(original_text="chek orqali kiritildi")
        return

    except Exception as exc:
        logger.error("OCR failed: %s", exc)
        await processing.edit_text(
            "❌ Chekni o'qib bo'lmadi.\n\n"
            "💡 Maslahat:\n"
            "• Rasmni to'g'ri burchakda oling\n"
            "• Yaxshi yorug'likda oling\n"
            "• Summa va sana aniq ko'rinsin"
        )
        return

    if extracted.get("not_receipt"):
        await processing.edit_text(
            "🤔 Bu rasm moliyaviy hujjatga o'xshamaydi.\n"
            "Chek, to'lov kvitansiyasi yoki bank skrinshoti yuboring."
        )
        return

    try:
        from app.bot.validation import validate_extracted_transaction, ValidationError
        validated = validate_extracted_transaction(extracted)
    except Exception as exc:
        await processing.edit_text(f"❌ Ma'lumot noto'g'ri: {exc}")
        return

    # Store in FSM and show confirmation
    await state.set_state(TransactionFSM.confirming)
    await state.update_data(pending_tx=validated)

    confidence = extracted.get("confidence", 0.8)
    confidence_bar = "🟢" if confidence >= 0.85 else "🟡" if confidence >= 0.6 else "🔴"
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

    from app.bot.keyboards import confirm_transaction_kb
    await processing.edit_text(
        f"🧾 Chek o'qildi {confidence_bar}\n\n"
        f"{preview}\n"
        f"Saqlaysizmi?",
        reply_markup=confirm_transaction_kb(),
    )


# ── Voice message handler ─────────────────────────────────────────────────────

@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext) -> None:
    """
    Pipeline:
      1. Download OGG audio from Telegram servers
      2. Transcribe via STT service (local or OpenAI)
      3. Feed transcribed text to the same text pipeline
    """
    processing_msg = await message.answer("🎤 Ovoz qabul qilindi, eshitilyapman...")

    from app.main import _app_ref
    whisper_model = _app_ref.state.whisper_model if _app_ref else None

    if whisper_model is None:
        await processing_msg.edit_text("⚠️ Ovoz xizmati ishlamayapti. Iltimos, matn yozing.")
        return

    try:
        bot = message.bot
        voice_file = await bot.get_file(message.voice.file_id)
        audio_bytes_io = await bot.download_file(voice_file.file_path)
        raw_bytes = audio_bytes_io.read() if hasattr(audio_bytes_io, "read") else bytes(audio_bytes_io)

        text = await transcribe_audio(raw_bytes, whisper_model)

    except RuntimeError as exc:
        err = str(exc)
        logger.error("STT RuntimeError: %s", exc)
        if "whisper_quota" in err:
            await processing_msg.edit_text("⚠️ Ovoz API limiti tugadi. Iltimos, matn yozing.")
        elif "whisper_auth" in err:
            await processing_msg.edit_text("⚠️ Ovoz API kaliti noto'g'ri. Admin bilan bog'laning.")
        elif "not supported" in err or "whisper-large" in err.lower():
            await processing_msg.edit_text(
                "⚠️ Ovoz modeli topilmadi. Admin .env faylida WHISPER_MODEL ni tekshirsin."
            )
        else:
            await processing_msg.edit_text("❌ Ovozni tushunolmadim. Iltimos, matn yozing.")
        return

    except Exception as exc:
        logger.error("STT unexpected error: %s", exc)
        await processing_msg.edit_text("❌ Ovoz yuklab olishda xatolik. Qaytadan urinib ko'ring.")
        return

    if not text.strip():
        await processing_msg.edit_text(
            "❌ Ovozdan matn ajratib bo'lmadi.\n"
            "💡 Aniqroq, sekinroq gapirib ko'ring yoki matn yozing."
        )
        return

    await processing_msg.edit_text(f"🔤 Eshitildi: <i>{text}</i>")
    await _process_text(text, message, state)


# ── Text message handler ──────────────────────────────────────────────────────

@router.message(
    F.text,
    ~StateFilter(
        TransactionFSM.waiting_clarification,
        TransactionFSM.confirming,
        TransactionFSM.editing_field,
        TransactionFSM.editing_value,
    )
)
async def handle_text(message: Message, state: FSMContext) -> None:
    """Main text entry point — classify intent then dispatch."""
    text = message.text.strip()
    if not text:
        return
    # Show "typing..." indicator immediately — user sees feedback before LLM responds
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    await _process_text(text, message, state)


# ── Clarification follow-up ───────────────────────────────────────────────────

@router.message(TransactionFSM.waiting_clarification)
async def handle_clarification(message: Message, state: FSMContext) -> None:
    """
    User replied to a follow-up question.
    Combine with the original partial text and retry extraction.
    """
    fsm_data = await state.get_data()
    original_text = fsm_data.get("original_text", "")
    combined_text = f"{original_text}. {message.text.strip()}"
    await state.clear()
    await _process_text(combined_text, message, state, is_retry=True)


# ── Confirmation callback handlers ────────────────────────────────────────────

async def _safe_answer(call: CallbackQuery, text: str = "") -> None:
    """Answer a callback query, silently ignoring expired query errors.

    Telegram invalidates callback query IDs after 30 s. The business logic
    (DB write, message edit) has already completed by the time this is called,
    so a stale query ID is harmless — we just skip the toast notification.
    """
    try:
        await call.answer(text)
    except Exception:
        pass  # query expired or already answered — not a real error


@router.callback_query(TransactionFSM.confirming, F.data == "tx:confirm")
async def callback_confirm(call: CallbackQuery, state: FSMContext) -> None:
    """User confirmed — save the pending transaction."""
    fsm_data = await state.get_data()
    pending = fsm_data.get("pending_tx")
    await state.clear()

    if not pending:
        await _safe_answer(call, "Xatolik: ma'lumot topilmadi.")
        await call.message.edit_text("❌ Xatolik yuz berdi. Qaytadan kiriting.")
        return

    from app.main import _app_ref
    telegram_user_id = str(call.from_user.id)
    reply = await _save_confirmed_transaction(pending, telegram_user_id, _app_ref)

    await _safe_answer(call, "Saqlandi!")
    await call.message.edit_text(reply)


@router.callback_query(TransactionFSM.confirming, F.data == "tx:cancel")
async def callback_cancel(call: CallbackQuery, state: FSMContext) -> None:
    """User cancelled — discard the pending transaction."""
    await state.clear()
    await _safe_answer(call, "Bekor qilindi.")
    await call.message.edit_text("❌ Operatsiya bekor qilindi.")


# ── Edit flow callback handlers ───────────────────────────────────────────────

@router.callback_query(TransactionFSM.editing_field, F.data.startswith("edit:"))
async def callback_edit_field(call: CallbackQuery, state: FSMContext) -> None:
    """User picked which field to edit."""
    field = call.data.split(":")[1]

    if field == "cancel":
        await state.clear()
        await _safe_answer(call, "Bekor qilindi.")
        await call.message.edit_text("✅ Tahrirlash bekor qilindi.")
        return

    await state.update_data(editing_field=field)
    await state.set_state(TransactionFSM.editing_value)
    await _safe_answer(call)

    if field == "category":
        await call.message.edit_text(
            "Yangi toifani tanlang:",
            reply_markup=category_kb(DEFAULT_CATEGORIES),
        )
    elif field == "amount":
        await call.message.edit_text("Yangi summani kiriting (faqat raqam):")
    elif field == "description":
        await call.message.edit_text("Yangi izohni kiriting:")
    else:
        await call.message.edit_text(f"'{field}' maydonining yangi qiymatini kiriting:")


@router.callback_query(TransactionFSM.editing_value, F.data.startswith("cat:"))
async def callback_edit_category(call: CallbackQuery, state: FSMContext) -> None:
    """User selected a category from the picker."""
    cat_name = call.data.split(":", 1)[1]

    if cat_name == "cancel":
        await state.clear()
        await _safe_answer(call, "Bekor qilindi.")
        await call.message.edit_text("✅ Tahrirlash bekor qilindi.")
        return

    fsm_data = await state.get_data()
    tx_id_str = fsm_data.get("editing_tx_id")
    await state.clear()

    result = await _apply_edit(tx_id_str, "category", cat_name, call.from_user.id)
    await _safe_answer(call, "Saqlandi!")
    await call.message.edit_text(result)


@router.message(TransactionFSM.editing_value)
async def handle_edit_value(message: Message, state: FSMContext) -> None:
    """User typed a new value for the field being edited."""
    fsm_data = await state.get_data()
    tx_id_str = fsm_data.get("editing_tx_id")
    field = fsm_data.get("editing_field")
    value = message.text.strip()
    await state.clear()

    result = await _apply_edit(tx_id_str, field, value, message.from_user.id)
    await message.answer(result)


async def _apply_edit(tx_id_str: str, field: str, value: str, telegram_user_id_int: int) -> str:
    """Apply the field edit to the transaction in DB."""
    from app.core.db import get_session_factory
    from app.schemas.transaction import TransactionUpdate
    from app.services import transactions as tx_service
    from sqlalchemy import select
    from app.models.transaction import Transaction

    telegram_user_id = str(telegram_user_id_int)

    try:
        tx_id = uuid.UUID(tx_id_str)
    except (ValueError, TypeError):
        return "❌ Xatolik: yozuv topilmadi."

    async with get_session_factory()() as db:
        user = await _get_user_from_telegram(telegram_user_id, db)
        if not user:
            return "❌ Tizimda ro'yxatdan o'tmagansiz."

        # Fetch current version for optimistic lock
        result = await db.execute(
            select(Transaction).where(
                Transaction.id == tx_id,
                Transaction.company_id == user.company_id,
                Transaction.is_deleted == False,  # noqa: E712
            )
        )
        tx = result.scalar_one_or_none()
        if not tx:
            return "❌ Yozuv topilmadi."

        current_version = tx.version
        update_data: dict = {"version": current_version}

        if field == "amount":
            try:
                clean = value.replace(",", "").replace(" ", "").replace("'", "")
                amount = float(clean)
                if amount <= 0:
                    return "❌ Summa musbat son bo'lishi kerak."
                update_data["amount"] = amount
            except ValueError:
                return "❌ Noto'g'ri summa formati. Faqat raqam kiriting."
        elif field == "category":
            from app.services.categories import resolve_category_by_name
            cat_id = await resolve_category_by_name(user.company_id, value, db)
            update_data["category_id"] = cat_id
        elif field == "description":
            update_data["description"] = value
        else:
            return f"❌ Noma'lum maydon: {field}"

        tx_update = TransactionUpdate(**update_data)
        tx_out = await tx_service.update_transaction(user.company_id, tx_id, tx_update, db)
        await db.commit()

    return (
        f"✅ Yangilandi!\n\n"
        f"{'📈 Daromad' if tx_out.type == 'income' else '📉 Xarajat'}: "
        f"<b>{float(tx_out.amount):,.0f} so'm</b>\n"
        f"📅 Sana: {tx_out.date.strftime('%d.%m.%Y')}"
    )


# ── Core text processing pipeline ────────────────────────────────────────────

async def _process_text(
    text: str,
    message: Message,
    state: FSMContext,
    is_retry: bool = False,
) -> None:
    from app.main import _app_ref
    app = _app_ref

    try:
        # Single LLM call for income/expense — returns both intent and extracted data.
        # For other intents (query, report, etc.) extracted_data will be None and
        # those handlers make their own LLM calls as needed.
        intent, extracted_data = await classify_and_extract(text)
    except AmbiguousInputError:
        # Combined call signalled ambiguity — fall through to the ambiguous handler below
        intent, extracted_data = INTENT_INCOME, None
    except RuntimeError as exc:
        await _handle_llm_error(exc, message, state)
        return

    logger.debug("Intent='%s' for user=%s text='%.60s'", intent, message.from_user.id, text)

    try:
        if intent in (INTENT_INCOME, INTENT_EXPENSE):
            reply = await handle_income_expense(intent, text, message, app, state,
                                                pre_extracted=extracted_data)

        elif intent in (INTENT_QUERY, INTENT_REPORT):
            # extracted_data carries pre-parsed period — skips a second LLM call
            reply = await handle_query(text, message, app, pre_parsed_period=extracted_data)

        elif intent == INTENT_EDIT_LAST:
            reply = await handle_edit_last(text, message, app, state)

        elif intent == INTENT_DELETE_LAST:
            reply = await handle_delete_last(text, message, app)

        elif intent == INTENT_HELP:
            reply = HELP_TEXT

        else:
            reply = (
                "🤔 Sizning so'rovingizni tushunmadim.\n"
                "Iltimos, aniqroq yozing yoki /help buyrug'ini ishlatib ko'ring."
            )

        if reply:
            await message.answer(reply)

    except RuntimeError as exc:
        await _handle_llm_error(exc, message, state)

    except AmbiguousInputError as exc:
        if is_retry:
            await message.answer(
                "❌ Kechirasiz, ma'lumotni tushunolmadim. "
                "Iltimos, summani va turini aniq ko'rsating.\n"
                "Misol: <i>Bugun 500,000 so'm savdo tushdi</i>"
            )
            await state.clear()
        else:
            await state.set_state(TransactionFSM.waiting_clarification)
            await state.update_data(original_text=text)
            await message.answer(f"❓ {exc.follow_up_question}")

    except Exception as exc:
        logger.exception("Unhandled error in bot handler: %s", exc)
        await message.answer("⚠️ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")
        await state.clear()


async def _handle_llm_error(exc: RuntimeError, message: Message, state: FSMContext) -> None:
    msg = str(exc)
    if msg == "openai_quota":
        await message.answer(
            "⚠️ AI xizmat vaqtinchalik ishlamayapti (kredit tugagan).\n"
            "Iltimos, keyinroq urinib ko'ring."
        )
    elif msg == "openai_auth":
        await message.answer("⚠️ AI xizmat sozlamalarida xatolik bor.")
    else:
        await message.answer("⚠️ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")
    await state.clear()
