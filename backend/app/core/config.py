from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 360dialog
    D360_API_URL: str = "https://waba.360dialog.io/v1"
    D360_PARTNER_TOKEN: str

    # Webhook
    WEBHOOK_SECRET_PATH: str

    # App
    PUBLIC_APP_URL: str
    ALLOWED_ORIGINS: List[str] = []


settings = Settings()
