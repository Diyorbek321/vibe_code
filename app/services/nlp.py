"""
NLP / LLM service — intent extraction and response generation via GPT-4o-mini.

Flow:
  1. User sends text (raw or STT-transcribed from voice)
  2. classify_intent()  → one of: income, expense, query, report, edit_last,
                           delete_last, help, unknown
  3. extract_transaction() → structured dict or raises AmbiguousInputError
  4. generate_reply()   → natural-language Uzbek response

All prompts are designed to work in Uzbek; English field names are used inside
JSON payloads so GPT parses them reliably.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        # Supports OpenAI and any OpenAI-compatible provider (Groq, Together, etc.)
        # Set OPENAI_BASE_URL in .env to switch providers.
        _client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,  # None = use OpenAI default
        )
    return _client


# ── Intent labels ─────────────────────────────────────────────────────────────

INTENT_INCOME = "income"
INTENT_EXPENSE = "expense"
INTENT_QUERY = "query"
INTENT_REPORT = "report"
INTENT_EDIT_LAST = "edit_last"
INTENT_DELETE_LAST = "delete_last"
INTENT_HELP = "help"
INTENT_UNKNOWN = "unknown"

VALID_INTENTS = {
    INTENT_INCOME, INTENT_EXPENSE, INTENT_QUERY, INTENT_REPORT,
    INTENT_EDIT_LAST, INTENT_DELETE_LAST, INTENT_HELP, INTENT_UNKNOWN,
}

# ── Exceptions ────────────────────────────────────────────────────────────────

class AmbiguousInputError(Exception):
    """Raised when the LLM cannot extract a complete transaction from the text."""
    def __init__(self, follow_up_question: str) -> None:
        self.follow_up_question = follow_up_question
        super().__init__(follow_up_question)


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_INTENT = """Siz moliyaviy bot assistantsiz. Foydalanuvchi xabarining niyatini aniqlang.

Faqat quyidagi niyat nomlaridan birini qaytaring (JSON formatida):
{"intent": "<nom>"}

Niyatlar:
- income: daromad kiritish (pul keldi, tushum, sotuv, ...)
- expense: xarajat kiritish (pul ketdi, harajat, to'lov, ...)
- query: ma'lumot so'rash (qancha, necha, ...)
- report: hisobot so'rash (haftalik, oylik, ...)
- edit_last: oxirgi yozuvni tahrirlash
- delete_last: oxirgi yozuvni o'chirish
- help: yordam so'rash
- unknown: boshqa yoki tushunarsiz

Faqat JSON qaytaring, hech qanday izoh yozmang."""

_SYSTEM_EXTRACT = """Siz moliyaviy operatsiyalarni tahlil qiluvchi assistantsiz.
Bugungi sana: {today}

Foydalanuvchi xabaridan quyidagi ma'lumotlarni ajratib oling va JSON formatida qaytaring:
{{
  "amount": <son, faqat raqam, UZS da>,
  "type": "<income | expense>",
  "category": "<toifa nomi uzbekcha>",
  "date": "<ISO 8601 format, masalan 2024-11-15T00:00:00>",
  "description": "<qisqacha tavsif yoki null>"
}}

Qoidalar:
1. amount musbat son bo'lishi kerak
2. type faqat "income" yoki "expense" bo'lishi mumkin
3. category quyidagilardan biri bo'lishi kerak: Savdo, Logistika, Ijara, Maosh, Kommunal, Marketing, Soliq, Boshqa
4. Agar sana aniq ko'rsatilmagan bo'lsa, bugungi sanani ishlating
5. Agar biror maydon tushunarsiz bo'lsa, "ambiguous" deb qaytaring:
   {{"ambiguous": true, "question": "<aniqlashtiruvchi savol uzbekcha>"}}

Faqat JSON qaytaring."""

_SYSTEM_COMBINED = """Siz moliyaviy bot assistantsiz.
Bugungi sana: {today}

Foydalanuvchi xabarini tahlil qiling va BITTA JSON qaytaring:

{{
  "intent": "<income|expense|query|report|edit_last|delete_last|help|unknown>",
  "amount": <son yoki null>,
  "type": "<income|expense|null>",
  "category": "<Savdo|Logistika|Ijara|Maosh|Kommunal|Marketing|Soliq|Boshqa|null>",
  "date": "<ISO 8601 yoki null>",
  "description": "<tavsif yoki null>",
  "ambiguous": false,
  "question": null,
  "period_label": "<davr nomi yoki null>",
  "start_date": "<YYYY-MM-DD yoki null>",
  "end_date": "<YYYY-MM-DD yoki null>"
}}

Qoidalar:
- intent har doim to'ldiriladi
- income/expense bo'lsa amount, type, category, date to'ldiriladi
- query/report bo'lsa period_label, start_date, end_date to'ldiriladi (bugungi sanaga nisbatan)
  Misollar: "bu hafta" → dushanba–bugun, "o'tgan oy" → o'tgan oyning 1–oxiri, "bugun" → bugun
- Agar ma'lumot yetarli bo'lmasa: ambiguous=true, question=<savol>
- Boshqa intentlar uchun tegishli bo'lmagan maydonlar null
- Sana ko'rsatilmasa bugungi sanani ishlating
- Faqat JSON qaytaring, izoh yozmang"""

_SYSTEM_QUERY = """Siz moliyaviy ma'lumotlarni tahlil qiluvchi assistantsiz.
Quyidagi ma'lumotlar asosida foydalanuvchiga o'zbek tilida aniq javob bering.
Summalarni raqam formatida ko'rsating (masalan: 5,250,000 so'm).
Taqqoslash bo'lsa, foiz o'zgarishini ham ko'rsating.

Ma'lumotlar: {data}
Savol: {question}"""


# ── Public functions ───────────────────────────────────────────────────────────

async def classify_intent(text: str) -> str:
    """
    Classify user message into one of VALID_INTENTS.
    Uses a cheap, single-token-ish JSON response.
    """
    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_INTENT},
                {"role": "user", "content": text},
            ],
            max_tokens=30,
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        intent = data.get("intent", INTENT_UNKNOWN)
        return intent if intent in VALID_INTENTS else INTENT_UNKNOWN
    except Exception as exc:
        logger.error("Intent classification failed: %s", exc)
        # Surface quota/auth errors so the bot can inform the user
        err = str(exc).lower()
        if "quota" in err or "billing" in err or "insufficient" in err:
            raise RuntimeError("openai_quota") from exc
        if "auth" in err or "api key" in err or "unauthorized" in err:
            raise RuntimeError("openai_auth") from exc
        return INTENT_UNKNOWN


async def classify_and_extract(text: str) -> tuple[str, dict[str, Any] | None]:
    """
    Single LLM call that returns both intent and extracted transaction data.

    Returns:
        (intent, data) where data is None for non-transaction intents,
        and raises AmbiguousInputError if the message needs clarification.

    Use this instead of calling classify_intent() + extract_transaction()
    separately — halves the number of API round-trips for income/expense messages.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    client = _get_client()

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_COMBINED.format(today=today)},
                {"role": "user", "content": text},
            ],
            max_tokens=200,
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.error("Combined classify+extract failed: %s", exc)
        err = str(exc).lower()
        if "quota" in err or "billing" in err or "insufficient" in err:
            raise RuntimeError("openai_quota") from exc
        if "auth" in err or "api key" in err or "unauthorized" in err:
            raise RuntimeError("openai_auth") from exc
        return INTENT_UNKNOWN, None

    raw = response.choices[0].message.content or "{}"
    logger.debug("Combined LLM raw: %s", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("LLM returned invalid JSON: %s", raw)
        return INTENT_UNKNOWN, None

    intent = data.get("intent", INTENT_UNKNOWN)
    if intent not in VALID_INTENTS:
        intent = INTENT_UNKNOWN

    # Query/report — return period data so handle_query() skips a second LLM call
    if intent in (INTENT_QUERY, INTENT_REPORT):
        period: dict[str, Any] | None = None
        if data.get("start_date") and data.get("end_date"):
            period = {
                "period_label": data.get("period_label") or "",
                "start_date": data["start_date"],
                "end_date": data["end_date"],
            }
        return intent, period

    # All other non-transaction intents
    if intent not in (INTENT_INCOME, INTENT_EXPENSE):
        return intent, None

    # Ambiguous transaction
    if data.get("ambiguous"):
        question = data.get("question", "Iltimos, aniqroq ma'lumot bering.")
        raise AmbiguousInputError(question)

    # Validate required fields
    missing = [f for f in ("amount", "type", "category", "date") if not data.get(f)]
    if missing:
        raise AmbiguousInputError(
            f"Quyidagi ma'lumotlar yetishmayapti: {', '.join(missing)}. Iltimos, to'liq yozing."
        )

    # Parse types — same logic as extract_transaction()
    try:
        amount = float(data["amount"])
        if amount <= 0:
            raise AmbiguousInputError("Summa musbat son bo'lishi kerak.")

        raw_date = data.get("date") or today
        if isinstance(raw_date, str):
            raw_date = raw_date.rstrip("Z").split("+")[0]
            tx_date = datetime.fromisoformat(raw_date).replace(tzinfo=timezone.utc)
        else:
            tx_date = datetime.now(timezone.utc)

        return intent, {
            "amount": amount,
            "type": data["type"],
            "category": data.get("category") or "Boshqa",
            "date": tx_date,
            "description": data.get("description"),
        }
    except AmbiguousInputError:
        raise
    except Exception as exc:
        logger.error("Combined extract parse error: %s | raw=%s", exc, raw)
        raise AmbiguousInputError("Ma'lumotni tahlil qilishda xatolik. Iltimos, qaytadan yozing.")


async def extract_transaction(text: str) -> dict[str, Any]:
    """
    Parse a free-form Uzbek message into a structured transaction dict.

    Returns dict with keys: amount, type, category, date (datetime), description.
    Raises AmbiguousInputError if the LLM signals ambiguity — the error carries
    a natural-language follow-up question to send back to the user.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    client = _get_client()

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": _SYSTEM_EXTRACT.format(today=today),
            },
            {"role": "user", "content": text},
        ],
        max_tokens=200,
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    logger.debug("LLM extraction raw: %s", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON: %s", raw)
        raise AmbiguousInputError(
            "Kechirasiz, ma'lumotni tushunmadim. Iltimos, aniqroq yozing."
        ) from exc

    # LLM signals ambiguity
    if data.get("ambiguous"):
        question = data.get("question", "Iltimos, aniqroq ma'lumot bering.")
        raise AmbiguousInputError(question)

    # Validate required fields
    missing = [f for f in ("amount", "type", "category", "date") if f not in data]
    if missing:
        raise AmbiguousInputError(
            f"Quyidagi ma'lumotlar yetishmayapti: {', '.join(missing)}. Iltimos, to'liq yozing."
        )

    # Parse and coerce types
    try:
        amount = float(data["amount"])
        if amount <= 0:
            raise ValueError("amount must be positive")

        tx_type = str(data["type"]).lower()
        if tx_type not in ("income", "expense"):
            raise ValueError(f"Invalid type: {tx_type}")

        date_str = data["date"]
        tx_date = datetime.fromisoformat(date_str)

        return {
            "amount": amount,
            "type": tx_type,
            "category": str(data["category"]),
            "date": tx_date,
            "description": data.get("description"),
        }
    except (ValueError, TypeError, KeyError) as exc:
        logger.warning("Failed to coerce LLM fields: %s | raw=%s", exc, raw)
        raise AmbiguousInputError(
            "Ma'lumotlarni to'g'ri formatda kiritolmadim. Iltimos, summani va turini aniq yozing."
        ) from exc


async def parse_query_period(text: str) -> dict[str, Any]:
    """
    Parse a natural-language period query like "bu hafta" or "o'tgan oy" into
    a date range dict: {period_label, start_date, end_date}.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    client = _get_client()

    system = f"""Bugungi sana: {today}
Foydalanuvchining savoli asosida davr oralig'ini JSON formatida aniqlang:
{{"period_label": "<davr nomi>", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}}
Faqat JSON qaytaring."""

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        max_tokens=80,
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)


async def generate_reply(
    intent: str,
    data: dict[str, Any],
    original_text: str,
) -> str:
    """
    Generate a natural Uzbek reply based on intent and structured data.
    Used after a transaction is saved or a query is answered.
    """
    client = _get_client()
    data_str = json.dumps(data, ensure_ascii=False, default=str)

    prompt = _SYSTEM_QUERY.format(data=data_str, question=original_text)

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": prompt},
        ],
        max_tokens=300,
        temperature=0.3,
    )
    return (response.choices[0].message.content or "").strip()
