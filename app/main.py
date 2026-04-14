"""
FastAPI application factory.

Key design decisions:
  - Single process: aiogram bot runs via webhook inside FastAPI (no separate worker)
  - Lifespan: Whisper model, SSE broadcaster, and bot webhook are initialised once
  - Company isolation: enforced at the dependency level (see core/deps.py)
  - Global exception handler: converts any unhandled exception to a JSON response
"""
import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.config import settings
from app.core.events import lifespan
from app.core.logging_config import configure_logging

# Configure logging before anything else
configure_logging()
logger = logging.getLogger(__name__)

# ── Module-level app reference ─────────────────────────────────────────────────
# Stored here so aiogram handlers (which don't have Request context) can access
# app.state (broadcaster, whisper_model, bot).
_app_ref: FastAPI | None = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="FinanceBot API",
        version="1.0.0",
        description="Telegram Finance Bot + Web Dashboard sync API",
        docs_url="/api/docs" if settings.is_dev else None,
        redoc_url="/api/redoc" if settings.is_dev else None,
        openapi_url="/api/openapi.json" if settings.is_dev else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    # <<< INTEGRATION: use FRONTEND_URLS from settings (configurable per env) >>>
    # Dev: defaults to localhost:3000 + localhost:5173 (Vite)
    # Prod: set FRONTEND_URLS=https://your-dashboard.com in .env
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    from app.routers import auth, transactions, categories, analytics, budgets, sse, bot_webhook

    api_prefix = "/api"
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(transactions.router, prefix=api_prefix)
    app.include_router(categories.router, prefix=api_prefix)
    app.include_router(analytics.router, prefix=api_prefix)
    app.include_router(budgets.router, prefix=api_prefix)
    app.include_router(sse.router, prefix=api_prefix)
    app.include_router(bot_webhook.router, prefix=api_prefix)

    # ── Static frontend (production) ──────────────────────────────────────────
    # In production the React build is copied to /app/static by the Dockerfile.
    # We mount it AFTER all API routes so /api/* is never shadowed.
    # The SPA catch-all serves index.html for all non-API, non-asset paths so
    # React Router's client-side navigation works correctly.
    _mount_frontend(app)

    # ── Exception handlers ────────────────────────────────────────────────────
    _register_exception_handlers(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """
    Serve the built React app from /app/static.
    Falls back gracefully when the directory doesn't exist (local dev without build).
    """
    import os
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    static_dir = Path(__file__).parent.parent / "static"
    if not static_dir.exists():
        return  # dev mode — frontend runs separately on Vite dev server

    # Serve /assets/*, *.js, *.css etc.
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    # SPA catch-all — everything that isn't /api/* or a static asset gets index.html
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = static_dir / "index.html"
        return FileResponse(str(index))


def _register_exception_handlers(app: FastAPI) -> None:
    """
    Global handlers — convert any unhandled exception to a structured JSON response.
    Never let stack traces leak to clients in production.
    """

    @app.exception_handler(ValidationError)
    async def pydantic_validation_error(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        logger.warning("Validation error on %s: %s", request.url, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": "Validation failed",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception on %s: %s", request.url, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Internal server error",
                "detail": str(exc) if settings.is_dev else "An unexpected error occurred",
            },
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Any) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Not found"},
        )


# ── Create the singleton app ───────────────────────────────────────────────────
app = create_app()
_app_ref = app  # expose for aiogram handlers


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Simple liveness probe used by Docker/k8s health checks."""
    return {"status": "ok", "version": "1.0.0"}
