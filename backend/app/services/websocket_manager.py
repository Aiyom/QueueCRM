"""WebSocket connection manager for realtime queue updates."""
import uuid
from typing import Optional

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections per tenant."""

    def __init__(self) -> None:
        # tenant_id -> list of WebSocket connections
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, tenant_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        key = str(tenant_id)
        self._connections.setdefault(key, []).append(websocket)
        logger.info("WebSocket connected", tenant_id=key, total=len(self._connections[key]))

    def disconnect(self, tenant_id: uuid.UUID, websocket: WebSocket) -> None:
        key = str(tenant_id)
        conns = self._connections.get(key, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._connections.pop(key, None)
        logger.info("WebSocket disconnected", tenant_id=key)

    async def broadcast(self, tenant_id: uuid.UUID, message: dict) -> None:
        """Send a JSON message to all connections of a tenant."""
        key = str(tenant_id)
        conns = self._connections.get(key, [])[:]
        dead = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(tenant_id, ws)


# Global singleton
ws_manager = ConnectionManager()
