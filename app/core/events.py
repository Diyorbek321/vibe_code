"""
FastAPI lifespan handler.
Initialises shared resources (Whisper model, bot webhook) on startup
and cleans up gracefully on shutdown.
"""
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from app.core.config import settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Everything before `yield` runs on startup.
    Everything after `yield` runs on shutdown.
    Resources are stored on app.state so services can access them.
    """
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Starting up FinanceBot API...")

    # 1. Configure logging (idempotent)
    from app.core.logging_config import configure_logging
    configure_logging()

    # 2. Pre-load Whisper model into app.state (avoid cold-start on first request).
    # Non-fatal: if faster-whisper isn't installed or fails to load, the app still
    # starts — voice messages will return a friendly error to the user.
    try:
        from app.services.stt import load_whisper_model
        app.state.whisper_model = await load_whisper_model()
        logger.info("STT engine initialised (backend=%s)", app.state.whisper_model)
    except Exception as exc:
        logger.warning("STT engine failed to load (%s) — voice messages disabled", exc)
        app.state.whisper_model = None

    # 3. SSE broadcaster — shared async queue manager
    from app.services.sync import SSEBroadcaster
    app.state.broadcaster = SSEBroadcaster()

    # 4. Set up Telegram bot webhook (production only)
    # In development use run_bot_polling.py — polling and webhook cannot run
    # simultaneously on the same bot token.
    if settings.APP_ENV == "production":
        try:
            from app.bot import setup_bot
            bot, dispatcher = await setup_bot(app)
            app.state.bot = bot
            app.state.dispatcher = dispatcher
            logger.info("Telegram bot webhook registered")
        except Exception as exc:
            logger.error("Bot setup failed: %s", exc)
            app.state.bot = None
            app.state.dispatcher = None
    else:
        logger.info("Development mode — bot webhook skipped (use run_bot_polling.py)")
        app.state.bot = None
        app.state.dispatcher = None

    # 5. Start scheduled reports (only if bot is available)
    app.state.scheduler = None
    if app.state.bot:
        try:
            from app.services.scheduler import start_scheduler
            app.state.scheduler = start_scheduler(app.state.bot)
        except Exception as exc:
            logger.warning("Scheduler failed to start: %s", exc)

    logger.info("Application startup complete")

    yield  # ─── Application runs ───────────────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutting down...")

    if getattr(app.state, "scheduler", None):
        from app.services.scheduler import stop_scheduler
        stop_scheduler()

    if app.state.bot:
        await app.state.bot.session.close()

    from app.core.db import get_engine
    await get_engine().dispose()

    logger.info("Shutdown complete")
