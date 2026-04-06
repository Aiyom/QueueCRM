from typing import List, Optional
from pydantic import BaseModel, field_validator

ALLOWED_LANGUAGES = {"ar", "en", "ru"}


class TenantSettingsResponse(BaseModel):
    enabled_languages: List[str]
    telegram_bot_token: Optional[str]
    d360_api_key: Optional[str]
    d360_channel_id: Optional[str]
    manager_telegram_chat_id: Optional[str]

    model_config = {"from_attributes": True}


class TenantSettingsUpdate(BaseModel):
    enabled_languages: Optional[List[str]] = None
    telegram_bot_token: Optional[str] = None
    d360_api_key: Optional[str] = None
    d360_channel_id: Optional[str] = None
    manager_telegram_chat_id: Optional[str] = None

    @field_validator("enabled_languages")
    @classmethod
    def validate_languages(cls, v: List[str]) -> List[str]:
        if v is not None:
            invalid = set(v) - ALLOWED_LANGUAGES
            if invalid:
                raise ValueError(f"Invalid languages: {invalid}. Allowed: {ALLOWED_LANGUAGES}")
            if not v:
                raise ValueError("At least one language must be enabled")
        return v
