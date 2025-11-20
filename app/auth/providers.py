# app/core/auth/providers.py
from __future__ import annotations
import time
import httpx
import jwt
from jwt import PyJWKClient
from typing import Any, Dict, Optional
from app.core.config import settings
from fastapi import HTTPException, status
from app.core.token_cache import token_cache

class AuthError(HTTPException):
    pass

class BaseAuthProvider:
    async def exchange_code(self, code: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def validate_user_token(self, token: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def client_credentials_grant(self, client_id: str, client_secret: str, scope: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

    async def validate_client_token(self, token: str) -> Dict[str, Any]:
        # Typically same as validate_user_token but validating aud/client claims
        return NotImplementedError #await self.validate_user_token(token)

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Exchange refresh token for new access/id tokens.
        """
        raise NotImplementedError


# ----------------------------
# Azure / Microsoft Entra provider
# ----------------------------
class AzureProvider(BaseAuthProvider):
    def __init__(self):
        if not settings.AZURE_AUTHORITY:
            raise RuntimeError("AZURE_AUTHORITY not configured")
        self.token_url = f"{settings.AZURE_AUTHORITY}/oauth2/v2.0/token"
        self.jwks_url = f"{settings.AZURE_AUTHORITY}/discovery/v2.0/keys"
        # PyJWKClient does caching of keys for us
        self._jwk_client = PyJWKClient(self.jwks_url)

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        data = {
            "client_id": settings.AZURE_CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.AZURE_REDIRECT_URI,
            "client_secret": settings.AZURE_CLIENT_SECRET,
        }
        async with httpx.AsyncClient() as c:
            r = await c.post(self.token_url, data=data, timeout=30)
        if r.status_code != 200:
            raise AuthError(status_code=400, detail="Token exchange failed")
        return r.json()

    async def validate_user_token(self, token: str) -> Dict[str, Any]:
        try:
            # 1. Check cache
            cached = await token_cache.get(token)
            if cached:
                return cached

            # 2. Validate using JWKS
            signing_key = self._jwk_client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=settings.AZURE_CLIENT_ID,
                issuer=settings.AZURE_AUTHORITY.rstrip("/") + "/v2.0",
                options={"verify_exp": True},
            )

            # 3. Cache result until expiration
            expires_in = claims["exp"] - int(time.time())
            await token_cache.set(token, claims, expires_in)

            return claims
        except Exception as e:
            raise AuthError(status_code=401, detail=f"Invalid token: {e}")

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        data = {
            "client_id": settings.AZURE_CLIENT_ID,
            "client_secret": settings.AZURE_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            # NOTE: optional, Azure allows empty scope for refresh
            "redirect_uri": settings.AZURE_REDIRECT_URI,
        }

        async with httpx.AsyncClient() as c:
            r = await c.post(self.token_url, data=data, timeout=30)

        if r.status_code != 200:
            raise AuthError(status_code=400, detail=f"Azure refresh token failed: {r.text}")

        return r.json()
    

    async def client_credentials_grant(self, client_id: str, client_secret: str, scope: Optional[str] = None) -> Dict[str, Any]:
        data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": scope,   # MUST BE v2.0 scope format
        }

        async with httpx.AsyncClient() as c:
            r = await c.post(self.token_url, data=data, timeout=30)

        if r.status_code != 200:
            raise AuthError(status_code=401, detail=f"Client credentials grant failed: {r.text}")

        return r.json()

    async def validate_client_token(self, token: str) -> Dict[str, Any]:
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            return decoded
            header = jwt.get_unverified_header(token)
            print(header)

            signing_key = self._jwk_client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=settings.AZURE_CLIENT_ID,
                issuer="https://login.microsoftonline.com/ca7621e7-a15f-4dc1-9515-5cbd8ac365b8/v2.0",
                options={"verify_exp": True},
            )
            # Additional checks for client tokens can be added here
            return claims
        except Exception as e:
            raise AuthError(status_code=401, detail=f"Invalid client token: {e}")    


# ----------------------------
# AWS Cognito provider
# ----------------------------
class CognitoProvider(BaseAuthProvider):
    def __init__(self):
        if not settings.COGNITO_USERPOOL_ID or not settings.COGNITO_REGION:
            raise RuntimeError("Cognito config missing")
        self.pool_id = settings.COGNITO_USERPOOL_ID
        self.region = settings.COGNITO_REGION
        self.client_id = settings.COGNITO_CLIENT_ID
        self.client_secret = settings.COGNITO_CLIENT_SECRET
        self.jwks_url = f"https://cognito-idp.{self.region}.amazonaws.com/{self.pool_id}/.well-known/jwks.json"
        self.token_url = f"https://{self.pool_id}.auth.{self.region}.amazoncognito.com/oauth2/token"
        self._jwk_client = PyJWKClient(self.jwks_url)

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "code": code,
            "redirect_uri": settings.COGNITO_REDIRECT_URI,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        # if secret configured add Authorization header
        if self.client_secret:
            import base64
            basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            headers["Authorization"] = f"Basic {basic}"

        async with httpx.AsyncClient() as c:
            r = await c.post(self.token_url, data=data, headers=headers, timeout=30)
        if r.status_code != 200:
            raise AuthError(status_code=400, detail="Cognito token exchange failed")
        return r.json()

    async def validate_user_token(self, token: str) -> Dict[str, Any]:
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{self.pool_id}",
                options={"verify_exp": True},
            )
            return claims
        except Exception as e:
            raise AuthError(status_code=401, detail=f"Invalid token: {e}")

    async def client_credentials_grant(self, client_id: str, client_secret: str, scope: Optional[str] = None) -> Dict[str, Any]:
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
        }
        if scope:
            data["scope"] = scope
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if client_secret:
            import base64
            basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
            headers["Authorization"] = f"Basic {basic}"

        async with httpx.AsyncClient() as c:
            r = await c.post(self.token_url, data=data, headers=headers, timeout=30)
        if r.status_code != 200:
            raise AuthError(status_code=401, detail="Cognito client credentials failed")
        return r.json()

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": refresh_token,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        if self.client_secret:
            import base64
            basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            headers["Authorization"] = f"Basic {basic}"

        async with httpx.AsyncClient() as c:
            r = await c.post(self.token_url, data=data, headers=headers, timeout=30)

        if r.status_code != 200:
            raise AuthError(status_code=400, detail=f"Cognito refresh token failed: {r.text}")

        return r.json()
    
