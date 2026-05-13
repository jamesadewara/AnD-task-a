from typing import Any, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "AnD-ai-review-generator"
    DEBUG: bool = True
    CORS_ALLOWED_ORIGINS: Union[list[str], str] = ["http://localhost:3000"]

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        return ["http://localhost:3000"]

    OPENROUTER_API_KEY: str = Field(
        default="",
        description="OpenRouter API Key"
    )

    LITELLM_MODEL_PRIMARY: str = "z-ai/glm-4.5-air:free"
    LITELLM_FALLBACK_MODELS: list[str] = [
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "google/gemma-4-31b-it:free"
    ]

    MAX_TOKENS: int = 1024

    NIGERIAN_MARKERS: list[str] = [
        # Core pidgin verbs/particles
        "na", "dey", "sha", "abi",
        # Exclamations & culturalisms
        "omo", "abeg", "wahala", "no wahala", "no be so",
        "sweet die", "dey whine me", "don tire", "sharp sharp",
        "value for money", "my people",
        # Slang & identity markers
        "naija", "nepa", "chop", "maga", "sabi", "oga", "pikin",
        "babe", "my guy", "chale", "level", "pepper dem",
        "dey go", "see as", "e be like",
        # Location markers
        "lagos", "abuja", "ph", "bariga",
        # Food markers
        "jollof",
    ]

    # Catalogue for extract_user_markers() — what we scan for in user's own text
    ALL_MARKERS: list[str] = [
        "omo", "abeg", "wahala", "nepa", "no wahala", "sweet die",
        "no be so", "sharp me", "dey", "am", "sha", "maga", "dey whine me",
        "my people", "na fire", "chop", "swallow", "value for money",
        "don tire", "sharp sharp", "naija", "no go", "fit",
    ]

    # Sentiment words for _validate_rating_alignment() and _estimate_sentiment()
    NEGATIVE_SENTIMENT_WORDS: list[str] = [
        "too much", "expensive", "overpriced", "wahala", "cry",
        "bleed", "whine", "no be so", "abeg no",
        "no go recommend", "kill person",
    ]
    POSITIVE_SENTIMENT_WORDS: list[str] = [
        "sweet die", "commend", "excellent", "love", "perfect",
        "worth", "recommended", "fantastic", "recommend", "serve well",
    ]

    # Dynamic fallback markers for different archetypes when no user history exists
    ARCHETYPE_FALLBACK_MARKERS: dict[str, list[str]] = {
        "haggler": ["abeg", "omo", "wahala", "no be so"],
        "big woman": ["commend", "worthy", "exquisite"],
        "community": ["my people", "na fire", "abeg"],
        "default": ["abeg", "omo"]
    }


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )


settings = Settings()
