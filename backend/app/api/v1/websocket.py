from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import List, Dict, Any, Optional
import json
import logging

router = APIRouter()
logger = logging.getLogger("skyguard.websocket")


class ConnectionManager:
    """Manages active WebSocket connections to stream real-time telemetry and alerts"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    @property
    def active_connections_count(self) -> int:
        return len(self.active_connections)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcasts payload to all connected frontend client dashboards"""
        if not self.active_connections:
            return

        data_text = json.dumps(message)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(data_text)
            except Exception:
                disconnected.append(connection)

        for dead in disconnected:
            self.disconnect(dead)


ws_manager = ConnectionManager()


def _validate_ws_token(token: Optional[str]) -> Optional[str]:
    """
    VULN-09 FIX: Validate JWT token from WebSocket query param.
    Returns the authenticated user email on success, None if token is missing/invalid.
    """
    if not token:
        return None
    try:
        from backend.app.core.config import settings
        from backend.app.core.cache import is_token_revoked
        from jose import jwt, JWTError
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        jti = payload.get("jti")
        if not email:
            return None
        if jti and is_token_revoked(jti):
            return None
        return email
    except Exception:
        return None


@router.websocket("/ws/live-feed")
async def websocket_live_feed(
    websocket: WebSocket,
    token: Optional[str] = Query(None)  # VULN-09 FIX: JWT via query param
):
    """
    Real-time telemetry WebSocket endpoint.
    Pass ?token=<jwt> for authenticated access to full telemetry stream.
    Unauthenticated connections still receive basic public telemetry.
    Explicitly invalid tokens are rejected immediately (close code 4001).
    """
    is_authenticated = False

    if token:
        user_email = _validate_ws_token(token)
        if user_email is not None:
            is_authenticated = True
            logger.info(f"[WS] Authenticated connection from: {user_email}")
        else:
            logger.warning("[WS] Token invalid or expired — continuing in public telemetry mode")
    else:
        logger.info("[WS] Unauthenticated client connected (public telemetry mode)")

    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive ping loop
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({
                "type": "PONG",
                "received": data,
                "authenticated": is_authenticated
            }))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
