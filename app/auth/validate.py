import time
from fastapi import HTTPException
from app.auth.factory import get_user_provider, get_client_provider
from app.auth.providers import AuthError

async def validate_bearer_token(token: str) -> dict:
    """
    Auto-detect provider & token type.
    Attempts validation in this order:

       1. Azure User Token
       2. Azure Client Token
       3. Cognito User Token
       4. Cognito Client Token

    Returns:
        {
            "provider": "azure" / "cognito",
            "type": "user" / "client",
            "claims": {...}
        }
    """

    # 1️⃣ Azure User
    azure_user = get_user_provider()
    try:
        claims = await azure_user.validate_user_token(token)
        return {"provider": "azure", "type": "user", "claims": claims}
    except Exception:
        pass

    # 2️⃣ Azure Client
    azure_client = get_client_provider()
    try:
        claims = await azure_client.validate_client_token(token)
        return {"provider": "azure", "type": "client", "claims": claims}
    except Exception:
        pass

    # 3️⃣ Cognito User
    try:
        user_provider = get_user_provider()
        claims = await user_provider.validate_user_token(token)
        return {"provider": "cognito", "type": "user", "claims": claims}
    except Exception:
        pass

    # 4️⃣ Cognito Client
    try:
        client_provider = get_client_provider()
        claims = await client_provider.validate_client_token(token)
        return {"provider": "cognito", "type": "client", "claims": claims}
    except Exception:
        pass

    # ❌ None matched
    raise HTTPException(status_code=401, detail="Invalid or unsupported Bearer token")
