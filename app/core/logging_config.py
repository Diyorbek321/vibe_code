"""
Structured logging setup. Call configure_logging() once at application startup.
Writes JSON-style records to both stderr and a rotating file.
"""
import logging
import logging.handlers
from pathlib import Path

from app.core.config import settings


def configure_logging() -> None:
    log_dir = Path(settings.LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    )
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Root handler → stderr
    logging.basicConfig(level=settings.LOG_LEVEL, format=fmt, datefmt=datefmt)

    # Rotating file handler — 10 MB × 5 backups
    file_handler = logging.handlers.RotatingFileHandler(
        filename=settings.LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    logging.getLogger().addHandler(file_handler)

    # Suppress noisy third-party loggers in production
    if not settings.is_dev:
        for noisy in ("httpx", "httpcore", "aiogram.event", "faster_whisper"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
