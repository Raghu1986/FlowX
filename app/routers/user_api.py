# app/routers/user_api.py
from fastapi import APIRouter, Depends
from app.auth.deps import user_authorize

router = APIRouter(prefix="/user", tags=["user"])

@router.get("/profile")
async def get_profile(user_claims = Depends(user_authorize)):
    # user_claims contains validated JWT claims from Entra or Cognito
    return {
        "sub": user_claims.get("sub"),
        "name": user_claims.get("name") or user_claims.get("preferred_username"),
        "raw_claims": user_claims,
    }
