# app/routers/auth.py
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from app.auth.factory import get_user_provider, get_client_provider
from app.core.config import settings
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

class RefreshRequest(BaseModel):
    refresh_token: str

@router.get("/user/login")
async def user_login():
    scope_raw = "e9fbab47-841c-4029-80d3-342e8154931b/.default email profile offline_access openid"

    import urllib.parse

    params = {
        "client_id": settings.AZURE_CLIENT_ID,
        "scope": urllib.parse.quote(scope_raw, safe=""),
        "response_type": "code",
        "response_mode": "query",
        "redirect_uri": settings.AZURE_REDIRECT_URI,

        "prompt": "select_account",
        "state": "secure-random-state",
    }

    # Build URL WITHOUT urlencode() messing with spaces
    base = settings.AZURE_AUTHORITY + "/oauth2/v2.0/authorize"

    # encode everything except scope
    param_str = "&".join(
        f"{k}={urllib.parse.quote(v, safe='') if k != 'scope' else v}"
        for k, v in params.items()
    )

    auth_url = f"{base}?{param_str}"

    return RedirectResponse(auth_url)

@router.post("/user/exchange")
async def user_exchange(code: str):
    prov = get_user_provider()
    tokens = await prov.exchange_code(code)
    return JSONResponse(tokens)

@router.post("/refresh")
async def refresh_user_token(data: RefreshRequest):
    provider = get_user_provider()

    if provider is None:
        raise HTTPException(500, "Auth provider not configured")

    try:
        tokens = await provider.refresh_token(data.refresh_token)
        return {
            "message": "Token refreshed successfully",
            "tokens": tokens,
        }
    except Exception as e:
        raise HTTPException(401, f"Refresh failed: {e}")


@router.post("/client/token")
async def client_token(client_id: str, client_secret: str, scope: str | None = None):
    prov = get_client_provider()
    tokens = await prov.client_credentials_grant(client_id, client_secret, scope)
    return JSONResponse(tokens)