"""
SSE (Server-Sent Events) broadcaster.

Design:
  - SSEBroadcaster is a singleton stored on app.state
  - Each dashboard client opens GET /api/sse/stream and gets its own asyncio.Queue
  - When a transaction is created/updated/deleted, `broadcast()` pushes a JSON
    event to ALL connected queues for the affected company
  - The SSE endpoint reads from the queue and yields formatted event strings

Company isolation: each connection registers its company_id. Broadcasts only
reach connections belonging to the same company.
"""
import asyncio
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """
    Thread-safe asyncio-based pub/sub broadcaster.
    Queues are keyed by (company_id, connection_id).
    """

    def __init__(self) -> None:
        # company_id (str) → {conn_id: asyncio.Queue}
        self._connections: dict[str, dict[str, asyncio.Queue]] = defaultdict(dict)

    def subscribe(self, company_id: uuid.UUID) -> tuple[str, asyncio.Queue]:
        """
        Register a new SSE connection.
        Returns (connection_id, queue).
        The caller must call unsubscribe() when the client disconnects.
        """
        conn_id = str(uuid.uuid4())
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._connections[str(company_id)][conn_id] = q
        logger.debug("SSE subscribed: company=%s conn=%s", company_id, conn_id)
        return conn_id, q

    def unsubscribe(self, company_id: uuid.UUID, conn_id: str) -> None:
        company_map = self._connections.get(str(company_id), {})
        company_map.pop(conn_id, None)
        logger.debug("SSE unsubscribed: company=%s conn=%s", company_id, conn_id)

    async def broadcast(
        self,
        company_id: uuid.UUID,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """
        Push an event to all connections belonging to company_id.
        Slow/full queues are dropped (non-blocking put_nowait).
        """
        company_map = self._connections.get(str(company_id), {})
        if not company_map:
            return  # no one is listening

        payload = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        payload_str = json.dumps(payload, default=str)

        for conn_id, q in list(company_map.items()):
            try:
                q.put_nowait(payload_str)
            except asyncio.QueueFull:
                logger.warning("SSE queue full for conn=%s — dropping event", conn_id)

    @property
    def connection_count(self) -> int:
        return sum(len(v) for v in self._connections.values())


# ── SSE stream generator ───────────────────────────────────────────────────────

async def sse_event_generator(
    company_id: uuid.UUID,
    broadcaster: SSEBroadcaster,
) -> AsyncGenerator[dict, None]:
    """
    Async generator consumed by sse-starlette's EventSourceResponse.
    Yields dicts with 'event' and 'data' keys.
    Sends a heartbeat every 30 s to keep the connection alive through proxies.
    """
    conn_id, queue = broadcaster.subscribe(company_id)
    try:
        while True:
            try:
                # Wait for a message or timeout (heartbeat)
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield {"event": "message", "data": message}
            except asyncio.TimeoutError:
                # Heartbeat — keeps nginx/CDN from closing the connection
                yield {"event": "ping", "data": "keep-alive"}
    except asyncio.CancelledError:
        # Client disconnected
        logger.debug("SSE stream cancelled: company=%s conn=%s", company_id, conn_id)
    finally:
        broadcaster.unsubscribe(company_id, conn_id)
