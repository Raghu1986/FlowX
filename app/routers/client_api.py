# app/routers/client_api.py
from fastapi import APIRouter, Depends
from app.auth.deps import client_authorize

router = APIRouter(prefix="/client", tags=["client"])

@router.get("/metrics")
async def get_metrics(client_claims = Depends(client_authorize)):
    # client_claims contains validated JWT from Entra / Cognito client_credentials
    return {
        "client_id": client_claims.get("azp") or client_claims.get("client_id"),
        "scopes": client_claims.get("scp") or client_claims.get("scope"),
        "raw_claims": client_claims,
    }
