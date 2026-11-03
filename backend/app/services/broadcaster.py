"""Simple in-memory WebSocket connection manager, keyed by tableId.
Sufficient for a single-process local demo; would need a pub/sub layer
(Redis, Kafka) for multi-process deployment."""

from __future__ import annotations

import json
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, table_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[table_id].add(ws)
        logger.info("WS connected: table=%s total=%d", table_id, len(self._connections[table_id]))

    def disconnect(self, table_id: str, ws: WebSocket) -> None:
        self._connections[table_id].discard(ws)
        logger.info("WS disconnected: table=%s total=%d", table_id, len(self._connections[table_id]))

    async def broadcast(self, table_id: str, message: dict) -> int:
        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        count = 0
        for ws in list(self._connections.get(table_id, set())):
            try:
                await ws.send_text(payload)
                count += 1
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(table_id, ws)
        return count


manager = ConnectionManager()
