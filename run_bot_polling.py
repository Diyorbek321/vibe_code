"""
Local development bot runner using long-polling (no public URL needed).
Use this instead of webhook when testing on localhost.

FSM storage priority:
  1. Redis (if REDIS_URL is set in .env AND redis package is installed)
  2. MemoryStorage fallback (FSM state lost on restart — fine for development)

Usage:
    python run_bot_polling.py
"""
import asyncio
import logging
import os
import socket

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Clear settings cache so .env is re-read fresh
from app.core.config import get_settings
get_settings.cache_clear()

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.services.sync import SSEBroadcaster


def _make_storage():
    """
    Try to create RedisStorage. Fall back to MemoryStorage if:
      - REDIS_URL is not configured, or
      - redis package is not installed, or
      - Redis server is not reachable.
    """
    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        return None, "MemoryStorage (REDIS_URL not set)"

    try:
        from aiogram.fsm.storage.redis import RedisStorage
        storage = RedisStorage.from_url(redis_url)
        return storage, f"RedisStorage ({redis_url})"
    except ModuleNotFoundError:
        return None, "MemoryStorage (redis package not installed — pip install redis)"
    except Exception as exc:
        return None, f"MemoryStorage (Redis unavailable: {exc})"


async def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)

    # Minimal app.state mock so handlers can access broadcaster and whisper_model
    class FakeState:
        broadcaster = SSEBroadcaster()
        whisper_model = "openai"   # use Whisper API (Groq or OpenAI)
        bot = None                  # set after bot is created

    class FakeApp:
        state = FakeState()

    # Reset nlp singleton so it picks up fresh settings (Groq base_url, key)
    import app.services.nlp as _nlp
    _nlp._client = None

    # Patch the module-level _app_ref so handlers can resolve the fake app
    import app.main as main_module
    fake_app = FakeApp()
    main_module._app_ref = fake_app  # type: ignore[assignment]

    # Force IPv4 — system aiohttp tries IPv6 first which is unreachable on this host
    session = AiohttpSession()
    session._connector_init["family"] = socket.AF_INET

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )
    fake_app.state.bot = bot

    # Remove any existing webhook so polling works
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook deleted — polling mode active")

    # FSM storage
    storage, storage_desc = _make_storage()
    logger.info("FSM storage: %s", storage_desc)

    if storage is None:
        from aiogram.fsm.storage.memory import MemoryStorage
        storage = MemoryStorage()

    dp = Dispatcher(storage=storage)
    dp["app"] = fake_app

    from app.bot.handlers import register_handlers
    register_handlers(dp)

    # Start scheduled reports
    try:
        from app.services.scheduler import start_scheduler, stop_scheduler
        scheduler = start_scheduler(bot)
    except Exception as exc:
        logger.warning("Scheduler failed to start: %s — reports disabled", exc)
        scheduler = None

    logger.info("Bot polling started. Press Ctrl+C to stop.")
    try:
        await dp.start_polling(bot)
    finally:
        if scheduler:
            stop_scheduler()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
