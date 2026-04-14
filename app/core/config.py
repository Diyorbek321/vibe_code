"""
Central settings loaded from environment variables via pydantic-settings.
All modules import `settings` from here — never read os.environ directly.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    DB_URL: str = Field(..., description="Async PostgreSQL DSN (asyncpg driver)")
    DB_URL_SYNC: str = Field(..., description="Sync DSN used by Alembic")
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Telegram ──────────────────────────────────────────────────────────────
    BOT_TOKEN: str = Field(...)
    WEBHOOK_URL: str = Field(...)          # public base URL, e.g. https://api.myapp.com
    WEBHOOK_SECRET: str = Field(default="")

    # ── Internal service communication ────────────────────────────────────────
    # Bot → FastAPI broadcast channel (dev: polling bot notifies the API server)
    INTERNAL_API_URL: str = "http://localhost:8000"
    INTERNAL_SECRET: str = ""             # shared secret for /api/internal/* endpoints

    # ── OpenAI ───────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(...)
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str | None = None   # set to https://api.groq.com/openai/v1 for Groq

    # ── Whisper / STT ─────────────────────────────────────────────────────────
    WHISPER_BACKEND: Literal["local", "openai"] = "local"
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_MODEL: str = "whisper-1"       # model name for OpenAI-compatible API
    WHISPER_LANGUAGE: str | None = "uz"   # None = auto-detect

    # ── Application ───────────────────────────────────────────────────────────
    APP_ENV: Literal["development", "production"] = "production"
    TZ: str = "Asia/Tashkent"
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed frontend origins.
    # Dev default covers Vite's default port.
    # Example prod value: https://dashboard.myapp.com,https://www.myapp.com
    FRONTEND_URLS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def allowed_origins(self) -> list[str]:
        return [u.strip() for u in self.FRONTEND_URLS.split(",") if u.strip()]

    # Derived — set automatically after validation
    WEBHOOK_PATH: str = "/api/bot/webhook"

    @field_validator("WEBHOOK_URL")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def full_webhook_url(self) -> str:
        return f"{self.WEBHOOK_URL}{self.WEBHOOK_PATH}"

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — call this everywhere instead of instantiating directly."""
    return Settings()  # type: ignore[call-arg]


settings: Settings = get_settings()
