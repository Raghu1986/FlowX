from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union


class Settings(BaseSettings):
    APP_NAME: str = "ExcelValidator"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "dev"  # dev | staging | prod
    HEARTBEAT_PUBSUB_CHANNEL: str = "service:heartbeat:pub"
    HEARTBEAT_ENABLED: bool = True
    HEARTBEAT_REDIS_STREAM: str = "service:heartbeat"
    HEARTBEAT_TTL_SECONDS: int = 900
    DATABASE_URL: str
    AWS_ACCESS_KEY_ID:str
    AWS_SECRET_ACCESS_KEY:str
    AWS_REGION:str
    S3_BUCKET:str
    INPUT_PREFIX: str = "uploads"
    OUTPUT_PREFIX: str = "validated"
    UPLOAD_BG_THRESHOLD_MB: int = 20
    REDIS_URL: str
    REDIS_STREAM_MAXLEN: int = 1000
    REDIS_STREAM_TTL_SEC: int = 3600  # 1 hour

    # Logging configuration
    LOG_LEVEL: str = "INFO"
    LOG_TARGETS: Union[str, List[str]] = "console"  # ✅ Accepts both str or list
    LOG_DIR: str = "logs"
    LOG_FILE_PATH: str = "logs/app.log"
    LOG_RETENTION_DAYS: int = 7
    AWS_CLOUDWATCH_GROUP: str | None = None
    AWS_CLOUDWATCH_STREAM: str | None = None

    # Auth config
    AUTH_USER_PROVIDER: str = "azure"      # azure | cognito
    AUTH_CLIENT_PROVIDER: str = "azure"    # azure | cognito

    # Azure
    AZURE_TENANT_ID: str | None = None
    AZURE_CLIENT_ID: str | None = None
    AZURE_CLIENT_SECRET: str | None = None
    AZURE_REDIRECT_URI: str | None = None
    AZURE_AUTHORITY: str | None = None  # e.g. https://login.microsoftonline.com/<tenant>/v2.0

    @property
    def azure_jwks_url(self) -> str | None:
        if not self.AZURE_AUTHORITY:
            return None
        return f"{self.AZURE_AUTHORITY}/discovery/v2.0/keys"

    # Cognito
    COGNITO_REGION: str | None = None
    COGNITO_USERPOOL_ID: str | None = None
    COGNITO_CLIENT_ID: str | None = None
    COGNITO_CLIENT_SECRET: str | None = None
    COGNITO_REDIRECT_URI: str | None = None

    @property
    def cognito_issuer(self) -> str | None:
        if not (self.COGNITO_REGION and self.COGNITO_USER_POOL_ID):
            return None
        return f"https://cognito-idp.{self.COGNITO_REGION}.amazonaws.com/{self.COGNITO_USER_POOL_ID}"

    @property
    def cognito_jwks_url(self) -> str | None:
        issuer = self.cognito_issuer
        if not issuer:
            return None
        return f"{issuer}/.well-known/jwks.json"

    

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ✅ Comma-separated value parser
    @field_validator("LOG_TARGETS", mode="before")
    def parse_log_targets(cls, v):
        if isinstance(v, str):
            # Split comma-separated string
            return [x.strip() for x in v.split(",") if x.strip()]
        elif isinstance(v, list):
            return v
        return ["console"]  # default fallback

settings = Settings()

print(settings.model_dump())