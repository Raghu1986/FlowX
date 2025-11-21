from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from app.services.notification_service import subscribe
from app.auth.deps import websocket_user_authorize

router = APIRouter(prefix="/ws", tags=["websocket"])

@router.websocket("/audit/{audit_id}")
async def audit_ws(websocket: WebSocket, audit_id: str, replay: bool = Query(False)):
    # 1. Extract Token
    auth_header = websocket.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        await websocket.close(code=4001)
        return

    token = auth_header.split(" ", 1)[1]

    # 2. Validate token using your existing user validator
    try:
        # Using your existing Azure/Cognito provider:
        user_claims = await websocket_user_authorize(token)

        # OR if you want universal detection:
        # identity = await validate_bearer_token(token)

    except Exception as e:
        await websocket.close(code=4003)
        return
    """
    WebSocket endpoint that streams audit progress & completion messages.
    Uses websocket.app.state.redis instead of a Request object.
    """
    # 3. Accept WebSocket AFTER authentication
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
