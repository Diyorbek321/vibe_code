"""
SSE streaming endpoint.

Dashboard connects to GET /api/sse/stream with a valid JWT.
Events are pushed by transaction writes on the same company.

Auth: Bearer token in Authorization header (API clients)
      OR ?token=<jwt> query param (browser EventSource — cannot set headers)

Event format (text/event-stream):
  event: message
  data: {"event":"transaction.created","data":{...},"timestamp":"..."}

  event: ping
  data: keep-alive
"""
import uuid
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.deps import CompanyID
from app.core.security import decode_access_token
from app.core.db import get_db
from app.services.sync import sse_event_generator

router = APIRouter(prefix="/sse", tags=["sse"])
logger = logging.getLogger(__name__)


# <<< INTEGRATION START: query-param token auth for browser EventSource >>>
async def _company_id_from_token(token: str) -> uuid.UUID:
    """
    Validate a raw JWT string and return the company_id.
    Used by the ?token= fallback path for EventSource connections.
    Raises HTTP 401 on any failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Load user from DB to get company_id and confirm account is active
    from app.models.user import User
    async for db in get_db():
        result = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise credentials_exception
        return user.company_id
# <<< INTEGRATION END >>>


@router.get("/stream")
async def sse_stream(
    request: Request,
    # <<< INTEGRATION: optional ?token= for EventSource (browser cannot set headers) >>>
    token: str | None = Query(default=None),
    # Standard Bearer-header auth (used by non-browser API clients)
    company_id: CompanyID | None = None,
) -> EventSourceResponse:
    """
    Establish a persistent SSE connection.

    Auth priority:
      1. Bearer token in Authorization header (standard, used by API clients)
      2. ?token=<jwt> query param (EventSource fallback for browsers)
    """
    # <<< INTEGRATION: resolve company_id from whichever auth path is present >>>
    resolved_company_id: uuid.UUID | None = company_id

    if resolved_company_id is None:
        if token:
            resolved_company_id = await _company_id_from_token(token)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Provide Authorization: Bearer <token> header or ?token= query param",
            )
    # <<< INTEGRATION END >>>

    broadcaster = request.app.state.broadcaster

    async def _generator():
        async for event in sse_event_generator(resolved_company_id, broadcaster):
            if await request.is_disconnected():
                break
            yield event

    return EventSourceResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Internal broadcast endpoint ───────────────────────────────────────────────

class BroadcastPayload(BaseModel):
    company_id: uuid.UUID
    event_type: str
    data: dict[str, Any]


@router.post("/internal/broadcast", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
async def internal_broadcast(
    payload: BroadcastPayload,
    request: Request,
    x_internal_secret: str | None = Header(default=None),
) -> None:
    """
    Internal-only endpoint: allows the Telegram bot (running as a separate process
    in dev/polling mode) to push SSE events into the FastAPI broadcaster.

    Protected by X-Internal-Secret header (must match INTERNAL_SECRET setting).
    When INTERNAL_SECRET is empty (default dev config), any request is accepted —
    the endpoint is not exposed in API docs so it is not discoverable.
    """
    if settings.INTERNAL_SECRET:
        if x_internal_secret != settings.INTERNAL_SECRET:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal secret")

    broadcaster = request.app.state.broadcaster
    await broadcaster.broadcast(
        payload.company_id,
        event_type=payload.event_type,
        data=payload.data,
    )
