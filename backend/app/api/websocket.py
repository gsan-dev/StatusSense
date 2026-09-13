from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..websocket_manager import manager

router = APIRouter()


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # No esperamos mensajes del cliente; solo mantenemos la conexion viva.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
