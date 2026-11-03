from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.broadcaster import manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/table/{table_id}")
async def table_ws(websocket: WebSocket, table_id: str):
    await manager.connect(table_id, websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        manager.disconnect(table_id, websocket)
