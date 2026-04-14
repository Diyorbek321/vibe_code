"""
Full bot simulation test — runs the complete pipeline without Telegram.
Tests: intent classification → extraction → DB save → query → delete.

Usage:
    python test_bot_full.py
"""
import asyncio
import os
import sys
import json
from datetime import datetime, timezone

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Clear the lru_cache so settings are re-read fresh from .env
from app.core.config import get_settings
get_settings.cache_clear()

# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = failed = 0


def ok(label, detail=""):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {label}" + (f"  {YELLOW}{detail}{RESET}" if detail else ""))


def fail(label, detail=""):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {label}" + (f"  {RED}{detail}{RESET}" if detail else ""))


def section(title):
    print(f"\n{BOLD}{CYAN}{'─'*55}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*55}{RESET}")


# ── Test helpers ───────────────────────────────────────────────────────────────

async def test_intent(text: str, expected: str):
    from app.services.nlp import classify_intent
    intent = await classify_intent(text)
    if intent == expected:
        ok(f"Intent '{text[:40]}'", f"→ {intent}")
    else:
        fail(f"Intent '{text[:40]}'", f"expected={expected} got={intent}")
    return intent


async def test_extraction(text: str):
    from app.services.nlp import extract_transaction, AmbiguousInputError
    try:
        data = await extract_transaction(text)
        ok(
            f"Extract '{text[:40]}'",
            f"amount={data['amount']:,.0f} type={data['type']} cat={data['category']}"
        )
        return data
    except AmbiguousInputError as e:
        fail(f"Extract '{text[:40]}'", f"Ambiguous: {e.follow_up_question}")
        return None


async def test_query_period(text: str):
    from app.services.nlp import parse_query_period
    try:
        period = await parse_query_period(text)
        ok(
            f"Period '{text[:40]}'",
            f"{period.get('period_label')} {period.get('start_date')}→{period.get('end_date')}"
        )
        return period
    except Exception as e:
        fail(f"Period '{text[:40]}'", str(e))
        return None


# ── Main test suite ────────────────────────────────────────────────────────────

async def main():
    print(f"\n{BOLD}FinanceBot — Full Pipeline Test{RESET}")

    # ── 1. Config check ────────────────────────────────────────────────────────
    section("1. Config & connectivity")
    from app.core.config import settings
    if "groq" in (settings.OPENAI_API_KEY or "").lower() or \
       (os.getenv("OPENAI_BASE_URL") and "groq" in os.getenv("OPENAI_BASE_URL","")):
        ok("Provider", "Groq")
    elif settings.OPENAI_API_KEY.startswith("sk-proj"):
        ok("Provider", "OpenAI (check credits!)")
    else:
        ok("Provider", settings.OPENAI_MODEL)

    # Quick ping
    # Reset nlp singleton so it picks up fresh settings (base_url, key)
    import app.services.nlp as _nlp
    _nlp._client = None

    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,   # from settings, not os.getenv
    )
    try:
        r = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role":"user","content":"Reply with word OK only"}],
            max_tokens=5,
        )
        ok("API ping", r.choices[0].message.content.strip())
    except Exception as e:
        fail("API ping", str(e)[:80])
        print(f"\n{RED}Cannot reach LLM API. Fix the API key and retry.{RESET}\n")
        sys.exit(1)

    # ── 2. Intent classification ───────────────────────────────────────────────
    section("2. Intent classification (Uzbek)")
    await test_intent("Bugun 500,000 so'm savdo tushdi",          "income")
    await test_intent("Kecha 120,000 so'm kommunal to'lovim ketdi","expense")
    await test_intent("Bu hafta qancha xarajat bo'ldi?",           "query")
    await test_intent("Shu oy hisobotini ko'rsat",                 "report")
    await test_intent("Oxirgi yozuvni o'chir",                     "delete_last")
    await test_intent("Oxirgi yozuvni tahrirlash",                 "edit_last")
    await test_intent("/help",                                     "help")

    # ── 3. Transaction extraction ──────────────────────────────────────────────
    section("3. Transaction extraction (Uzbek → structured JSON)")
    cases = [
        "Bugun 2,500,000 so'm savdo tushdi",
        "Kecha 350,000 so'm logistika xarajati ketdi",
        "5 million so'm ijara to'lovim bor edi",
        "Marketing uchun 800 ming so'm ketdi",
        "Soliq to'lovi 1.2 million so'm",
    ]
    extracted = []
    for text in cases:
        data = await test_extraction(text)
        if data:
            extracted.append(data)

    # ── 4. Ambiguous input ─────────────────────────────────────────────────────
    section("4. Ambiguous input (should ask follow-up)")
    from app.services.nlp import extract_transaction, AmbiguousInputError
    for text in ["pul tushdi", "xarajat bor"]:
        try:
            await extract_transaction(text)
            fail(f"'{text}' should be ambiguous", "but extraction succeeded")
        except AmbiguousInputError as e:
            ok(f"Ambiguous: '{text}'", f"follow-up: {e.follow_up_question[:60]}")

    # ── 5. Period parsing ──────────────────────────────────────────────────────
    section("5. Period query parsing")
    await test_query_period("Bu hafta qancha daromad bo'ldi?")
    await test_query_period("O'tgan oy xarajatlar")
    await test_query_period("Bugun necha pul tushdi?")

    # ── 6. Validation layer ────────────────────────────────────────────────────
    section("6. Post-LLM validation")
    from app.bot.validation import validate_extracted_transaction, ValidationError

    good = {"amount": 500000, "type": "income", "category": "Savdo",
            "date": datetime.now(timezone.utc), "description": "Test"}
    try:
        validate_extracted_transaction(dict(good))
        ok("Valid transaction passes")
    except ValidationError as e:
        fail("Valid transaction passes", e.user_message)

    for bad, label in [
        ({**good, "amount": -100},         "negative amount"),
        ({**good, "type": "invalid"},       "bad type"),
        ({**good, "date": "not-a-date"},    "bad date"),
    ]:
        try:
            validate_extracted_transaction(dict(bad))
            fail(f"Rejects {label}")
        except (ValidationError, Exception):
            ok(f"Rejects {label}")

    # ── 7. DB — full transaction pipeline ─────────────────────────────────────
    section("7. Database — full transaction pipeline")
    from app.core.db import get_session_factory
    from sqlalchemy import select
    from app.models.user import User
    from app.models.category import Category
    from app.services.transactions import (
        create_transaction, get_last_transaction,
        soft_delete_transaction, list_transactions,
    )
    from app.schemas.transaction import TransactionCreate

    async with get_session_factory()() as db:
        # Find test user
        r = await db.execute(select(User).where(User.email == "test@financebot.uz"))
        user = r.scalar_one_or_none()
        if not user:
            fail("Test user exists — run register first")
            return
        ok("Test user found", user.email)

        # Find Savdo category
        r = await db.execute(
            select(Category).where(
                Category.company_id == user.company_id,
                Category.name == "Savdo",
            )
        )
        cat = r.scalar_one_or_none()
        ok("Category found", cat.name if cat else "MISSING")

        # Create
        tx_data = TransactionCreate(
            amount=999000,
            type="income",
            category_id=cat.id if cat else None,
            description="Bot test savdo",
            date=datetime.now(timezone.utc),
            source="telegram",
        )
        tx = await create_transaction(user.company_id, user.id, tx_data, db)
        ok("Transaction created", f"id={str(tx.id)[:8]}… amount={tx.amount}")

        # get_last
        last = await get_last_transaction(user.company_id, user.id, db)
        if last and last.id == tx.id:
            ok("get_last_transaction", f"matches created tx")
        else:
            fail("get_last_transaction", "mismatch")

        # list
        listing = await list_transactions(user.company_id, db, page=1, limit=5)
        ok("list_transactions", f"total={listing.total} items={len(listing.items)}")

        # soft delete
        await soft_delete_transaction(user.company_id, tx.id, db)
        ok("soft_delete_transaction")

        await db.commit()

    # ── 8. Analytics ──────────────────────────────────────────────────────────
    section("8. Analytics aggregation")
    from app.routers.analytics import _summary_for_period
    async with get_session_factory()() as db:
        r = await db.execute(select(User).where(User.email == "test@financebot.uz"))
        user = r.scalar_one_or_none()
        start = datetime(2026, 4, 1, tzinfo=timezone.utc)
        end   = datetime(2026, 4, 30, 23, 59, 59, tzinfo=timezone.utc)
        summary = await _summary_for_period(user.company_id, start, end, db)
        ok("Analytics summary",
           f"income={float(summary.total_income):,.0f} "
           f"expense={float(summary.total_expense):,.0f} "
           f"net={float(summary.net):,.0f}")

    # ── Final report ───────────────────────────────────────────────────────────
    total = passed + failed
    print(f"\n{'─'*55}")
    print(f"  Results: {GREEN}{passed} passed{RESET}  {RED}{failed} failed{RESET}  / {total} total")
    if failed == 0:
        print(f"  {GREEN}{BOLD}All tests passed ✓{RESET}")
    else:
        print(f"  {RED}{BOLD}{failed} test(s) failed ✗{RESET}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
