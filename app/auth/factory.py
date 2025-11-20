# app/core/auth/factory.py
from app.core.config import settings
from app.auth.providers import AzureProvider, CognitoProvider

_provider_cache = {}

def get_provider(name: str):
    name = (name or "").lower()
    if name == "azure" or name == "entra":
        if "azure" not in _provider_cache:
            _provider_cache["azure"] = AzureProvider()
        return _provider_cache["azure"]
    if name == "cognito" or name == "aws_cognito":
        if "cognito" not in _provider_cache:
            _provider_cache["cognito"] = CognitoProvider()
        return _provider_cache["cognito"]
    raise ValueError("Unknown auth provider: " + str(name))


def get_user_provider():
    return get_provider(settings.AUTH_USER_PROVIDER)

def get_client_provider():
    return get_provider(settings.AUTH_CLIENT_PROVIDER)
