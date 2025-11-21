# app/core/auth/deps.py
from typing import Optional, List
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth.factory import get_user_provider, get_client_provider
from app.auth.providers import AuthError

bearer = HTTPBearer(auto_error=False)

async def user_authorize(token: HTTPAuthorizationCredentials = Depends(bearer)):
    """
    Dependency for user-authenticated endpoints.
    Validates user access/id token using configured user provider.
    """
    if token is None:
        raise HTTPException(401, "Missing Authorization")
    provider = get_user_provider()
    try:
        claims = await provider.validate_user_token(token.credentials)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    # scope/roles checks (optional)
    # if required_scopes:
    #     scopes = set(claims.get("scp", "").split()) if isinstance(claims.get("scp", ""), str) else set()
    #     if not set(required_scopes).issubset(scopes):
    #         raise HTTPException(403, "Missing required scopes")
    return claims

async def websocket_user_authorize(token: str):
    """
    Dependency for user-authenticated endpoints.
    Validates user access/id token using configured user provider.
    """
    if token is None:
        raise HTTPException(401, "Missing Authorization")
    provider = get_user_provider()
    try:
        claims = await provider.validate_user_token(token)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    # scope/roles checks (optional)
    # if required_scopes:
    #     scopes = set(claims.get("scp", "").split()) if isinstance(claims.get("scp", ""), str) else set()
    #     if not set(required_scopes).issubset(scopes):
    #         raise HTTPException(403, "Missing required scopes")
    return claims


async def client_authorize(token: HTTPAuthorizationCredentials = Depends(bearer)):
    """
    Dependency for client-authenticated endpoints (validate token emitted by client credentials).
    """
    if token is None:
        raise HTTPException(401, "Missing Authorization")
    provider = get_client_provider()
    try:
        claims = await provider.validate_client_token(token.credentials)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return claims
