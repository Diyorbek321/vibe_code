"""
Receipt / check OCR service using Groq vision API.

Flow:
  User sends photo → download bytes → base64 encode →
  Groq llama-4-scout vision → structured JSON →
  same validation + confirmation flow as text input.

Supported receipt types:
  - Cash register receipts (kassoviy chek)
  - Bank transfer screenshots
  - Handwritten notes with amounts
  - Invoice photos
"""
import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

_SYSTEM_OCR = """Siz moliyaviy hujjatlarni tahlil qiluvchi assistantsiz.
Bugungi sana: {today}

Rasmdan moliyaviy ma'lumotlarni ajratib oling va JSON formatida qaytaring:
{{
  "amount": <son, faqat raqam, UZS da>,
  "type": "<income | expense>",
  "category": "<Savdo | Logistika | Ijara | Maosh | Kommunal | Marketing | Soliq | Boshqa>",
  "date": "<ISO 8601 format>",
  "description": "<do'kon nomi, xizmat nomi yoki qisqacha tavsif>",
  "confidence": <0.0-1.0, qanchalik aniq o'qildi>
}}

Qoidalar:
1. Agar rasm chek yoki to'lov hujjati bo'lmasa: {{"not_receipt": true}}
2. Agar summa aniq ko'rinmasa: {{"ambiguous": true, "question": "Summa aniq ko'rinmayapti, miqdorni kiriting"}}
3. Do'kon yoki kompaniya nomi description ga kiriting
4. Chek xarajat (expense) bo'ladi, agar daromad (savdo tushumi) ekanligini aniq ko'rsatmasa
5. Sana chekda ko'rsatilmagan bo'lsa bugungi sanani ishlatng
6. Faqat JSON qaytaring"""


async def extract_from_receipt(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
    """
    Send receipt image to Groq vision API and return extracted transaction data.

    Returns:
        dict with keys: amount, type, category, date (datetime), description, confidence
        OR {"not_receipt": True} if image is not a financial document
        OR raises AmbiguousInputError if amount is unclear
    """
    from openai import AsyncOpenAI
    from app.services.nlp import AmbiguousInputError

    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # Encode image to base64 data URL
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    image_url = f"data:{mime_type};base64,{b64}"

    try:
        response = await client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": _SYSTEM_OCR.format(today=today),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        },
                    ],
                }
            ],
            max_tokens=300,
            temperature=0,
        )
    except Exception as exc:
        logger.error("Groq vision API error: %s", exc)
        raise RuntimeError(f"OCR API xatosi: {exc}") from exc

    raw = response.choices[0].message.content or "{}"
    logger.debug("OCR raw response: %s", raw)

    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("OCR returned invalid JSON: %s", raw)
        raise AmbiguousInputError("Rasmdan ma'lumot o'qib bo'lmadi. Aniqroq rasm yuboring.")

    if data.get("not_receipt"):
        return {"not_receipt": True}

    if data.get("ambiguous"):
        raise AmbiguousInputError(
            data.get("question", "Rasmdan summa aniqlanmadi. Miqdorni yozing:")
        )

    # Parse and validate
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

        confidence = float(data.get("confidence", 0.8))

        return {
            "amount": amount,
            "type": data.get("type", "expense"),
            "category": data.get("category") or "Boshqa",
            "date": tx_date,
            "description": data.get("description") or "Chek orqali kiritildi",
            "confidence": confidence,
        }

    except AmbiguousInputError:
        raise
    except Exception as exc:
        logger.error("OCR parse error: %s | raw=%s", exc, raw)
        raise AmbiguousInputError("Rasmdan ma'lumot ajratib bo'lmadi. Qaytadan urinib ko'ring.")
