"""
Bot initialisation — called from app.core.events lifespan.
Sets up dispatcher, registers all handlers, and registers the webhook.
"""
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI

from app.core.config import settings

logger = logging.getLogger(__name__)


async def setup_bot(app: FastAPI) -> tuple[Bot, Dispatcher]:
    """
    Create Bot + Dispatcher, register all handlers, set Telegram webhook.
    Returns (bot, dispatcher) to be stored on app.state.
    """
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Attach the FastAPI app to dispatcher storage so handlers can access DB
    dp["app"] = app

    # Register routers (handlers)
    from app.bot.handlers import register_handlers
    register_handlers(dp)

    # Set webhook — Telegram will POST updates to this URL
    await bot.set_webhook(
        url=settings.full_webhook_url,
        secret_token=settings.WEBHOOK_SECRET or None,
        drop_pending_updates=True,
    )
    logger.info("Webhook set: %s", settings.full_webhook_url)
    return bot, dp
