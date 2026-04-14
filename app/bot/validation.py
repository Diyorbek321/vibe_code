"""
Post-LLM validation helpers for the bot layer.
These run after NLP extraction to catch any data issues before DB writes.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

# Maximum reasonable transaction amount in UZS (100 billion)
MAX_AMOUNT_UZS = 100_000_000_000


class ValidationError(Exception):
    """Raised when extracted transaction data fails validation."""
    def __init__(self, user_message: str) -> None:
        self.user_message = user_message
        super().__init__(user_message)


def validate_extracted_transaction(data: dict[str, Any]) -> dict[str, Any]:
    """
    Strict validation of LLM-extracted transaction data.
    Returns validated (and coerced) data dict or raises ValidationError.

    This is the final gate before any DB write — never persist unverified data.
    """
    errors: list[str] = []

    # ── Amount ───────────────────────────────────────────────────────────────
    try:
        amount = Decimal(str(data.get("amount", 0)))
        if amount <= 0:
            errors.append("Summa musbat son bo'lishi kerak")
        elif amount > MAX_AMOUNT_UZS:
            errors.append(f"Summa juda katta (maksimum {MAX_AMOUNT_UZS:,} so'm)")
        else:
            data["amount"] = amount.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        errors.append("Summa noto'g'ri formatda")

    # ── Type ─────────────────────────────────────────────────────────────────
    tx_type = str(data.get("type", "")).lower()
    if tx_type not in ("income", "expense"):
        errors.append("Operatsiya turi noto'g'ri (income yoki expense bo'lishi kerak)")
    else:
        data["type"] = tx_type

    # ── Date ─────────────────────────────────────────────────────────────────
    date_val = data.get("date")
    if isinstance(date_val, datetime):
        # Ensure timezone-aware
        if date_val.tzinfo is None:
            date_val = date_val.replace(tzinfo=timezone.utc)
        # Future transactions beyond 1 day are suspicious
        now = datetime.now(timezone.utc)
        if date_val > now.replace(day=now.day + 1):
            errors.append("Kelajakdagi sana kiritib bo'lmaydi")
        data["date"] = date_val
    else:
        errors.append("Sana noto'g'ri formatda")

    if errors:
        raise ValidationError("\n".join(f"• {e}" for e in errors))

    return data
