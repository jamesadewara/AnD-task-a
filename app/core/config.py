import logging
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    APP_NAME: str = "reko-ai-review-generator"
    DEBUG: bool = True

    OPENROUTER_API_KEY: str = Field(
        default="",
        description="OpenRouter API Key"
    )
    LITELLM_MODEL_PRIMARY: str = "openrouter/google/gemma-2-9b-it:free"
    MAX_TOKENS: int = 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )


settings = Settings()
