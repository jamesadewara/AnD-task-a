import logging
from typing import Any, Dict, List, AsyncGenerator
from litellm import acompletion
from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self.model = settings.LITELLM_MODEL_PRIMARY
        self.api_key = settings.OPENROUTER_API_KEY
        self.api_base = "https://openrouter.ai/api/v1"
        if not self.api_key:
            logger.error("❌ OPENROUTER_API_KEY is EMPTY in Settings!")
        else:
            logger.info(f"✅ OPENROUTER_API_KEY found (starts with: {self.api_key[:4]}...)")

    async def get_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        response = await acompletion(
            model=self.model,
            messages=messages,
            api_key=self.api_key,
            api_base=self.api_base,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def get_streaming_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> AsyncGenerator[Any, None]:
        response = await acompletion(
            model=self.model,
            messages=messages,
            api_key=self.api_key,
            api_base=self.api_base,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in response:
            yield chunk


llm_service = LLMService()
