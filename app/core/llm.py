import logging
import os
from typing import Any, Dict, List, AsyncGenerator
from openrouter import OpenRouter
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.primary_model = settings.LITELLM_MODEL_PRIMARY
        self.fallback_models = settings.LITELLM_FALLBACK_MODELS
        self.api_key = settings.OPENROUTER_API_KEY
        if not self.api_key:
            logger.error("❌ OPENROUTER_API_KEY is EMPTY in Settings!")

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def _call_llm(self, model: str, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
        """Internal helper using the official OpenRouter SDK with a strict timeout."""
        import asyncio
        logger.info(f"LLM Call (Task A - SDK): {model}")
        
        async def _do_call():
            async with OpenRouter(api_key=self.api_key) as client:
                response = await client.chat.send_async(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content or ""

        # Enforce a 20-second timeout per attempt to prevent hanging
        try:
            return await asyncio.wait_for(_do_call(), timeout=20.0)
        except asyncio.TimeoutError:
            logger.error(f"LLM Timeout for model {model}")
            raise Exception(f"Timeout (20s) exceeded for {model}")

    async def get_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500,
        on_fallback = None
    ) -> str:
        """Get completion with multi-model fallback and rotation logic."""
        models_to_try = [self.primary_model] + self.fallback_models
        
        last_error = None
        for i, model in enumerate(models_to_try):
            try:
                return await self._call_llm(model, messages, temperature, max_tokens)
            except Exception as e:
                last_error = e
                logger.warning(f"LLM attempt failed for {model}: {e}.")
                
                # If there's another model to try, trigger the fallback callback
                if i < len(models_to_try) - 1 and on_fallback:
                    next_model = models_to_try[i+1]
                    await on_fallback(model, next_model, str(e))
                
                continue
        
        logger.error(f"All LLM attempts failed (Task A). Last error: {last_error}")
        return f"ERROR: Unable to generate review after trying all available models. Last error: {str(last_error)}"

    async def get_streaming_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500,
        on_fallback = None
    ) -> AsyncGenerator[Any, None]:
        """Fallback-enabled streaming (yields the choice object)."""
        models_to_try = [self.primary_model] + self.fallback_models
        
        last_error = None
        for i, model in enumerate(models_to_try):
            try:
                import asyncio
                async def _do_call():
                    async with OpenRouter(api_key=self.api_key) as client:
                        return await client.chat.send_async(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens
                        )

                response = await asyncio.wait_for(_do_call(), timeout=25.0)
                yield response.choices[0]
                return # Success
            except Exception as e:
                last_error = e
                logger.warning(f"Streaming LLM attempt failed for {model}: {e}")
                if i < len(models_to_try) - 1 and on_fallback:
                    await on_fallback(model, models_to_try[i+1], str(e))
                continue
        
        raise Exception(f"All streaming attempts failed. Last error: {last_error}")

llm_service = LLMService()

llm_service = LLMService()
