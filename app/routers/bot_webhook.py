"""
Telegram webhook receiver.

Telegram sends an HTTPS POST to /api/bot/webhook for every incoming update.
This router validates the secret header and passes the update to aiogram's dispatcher.
"""
import hashlib
import hmac
import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings

router = APIRouter(prefix="/bot", tags=["bot"])
logger = logging.getLogger(__name__)


@router.post("/webhook", include_in_schema=False)
async def telegram_webhook(request: Request) -> JSONResponse:
    """
    Verify the webhook secret header, then feed the raw update to aiogram.
    Returns 200 immediately — processing is async inside aiogram.
    """
    # ── Security: verify Telegram's X-Telegram-Bot-Api-Secret-Token header ──
    if settings.WEBHOOK_SECRET:
        secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(secret_header, settings.WEBHOOK_SECRET):
            logger.warning("Webhook secret mismatch from %s", request.client)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook secret",
            )

    dispatcher = request.app.state.dispatcher
    bot = request.app.state.bot
    if dispatcher is None:
        logger.error("Dispatcher not initialised — dropping update")
        return JSONResponse(content={"ok": True})

    # Parse the raw JSON body into an aiogram Update object
    from aiogram.types import Update

    body = await request.json()
    update = Update.model_validate(body)

    # Feed update to dispatcher (non-blocking — aiogram handles it internally)
    await dispatcher.feed_update(bot, update)
    return JSONResponse(content={"ok": True})
