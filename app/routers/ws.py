from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.notification_service import subscribe

router = APIRouter(prefix="/ws", tags=["websocket"])

@router.websocket("/audit/{audit_id}")
async def audit_ws(websocket: WebSocket, audit_id: str, replay: bool = Query(False)):
    """
    WebSocket endpoint that streams audit progress & completion messages.
    Uses websocket.app.state.redis instead of a Request object.
    """
    await websocket.accept()
    app = websocket.app  # ✅ Access FastAPI app instance
    last_id = "0" if replay else "$"

    try:
        async for msg in subscribe(app, audit_id, last_id=last_id):
            await websocket.send_text(msg)
    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected for audit {audit_id}")
    except Exception as e:
        print(f"⚠️ WebSocket error: {e}")
    finally:
        await websocket.close()
