from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.auth.validate import validate_bearer_token

class TokenCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth.split(" ")[1]

            # Universal validator
            request.state.identity = await validate_bearer_token(token)

        return await call_next(request)
