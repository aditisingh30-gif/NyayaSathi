import httpx
from typing import Optional
from app.config import settings
from app.core.logging_config import logger
from app.llm.base import BaseLLMProvider, LLMGenerationResult


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider using direct REST API."""

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        model = model_name or settings.OPENAI_MODEL or "gpt-4o-mini"
        super().__init__(provider_name="openai", model_name=model)
        self.api_key = api_key or settings.OPENAI_API_KEY

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    async def generate_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMGenerationResult:
        if not self.is_available():
            raise ValueError("OPENAI_API_KEY is not configured in environment or .env file.")

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error(f"OpenAI API error ({resp.status_code}): {resp.text}")
                raise RuntimeError(f"OpenAI API request failed with status {resp.status_code}: {resp.text}")

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("OpenAI returned no choices.")

            text = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)

            is_refusal = "not available" in text.lower() or "not indexed" in text.lower()

            return LLMGenerationResult(
                raw_response=text,
                provider_name=self.provider_name,
                model_name=self.model_name,
                tokens_used=total_tokens,
                is_refusal=is_refusal
            )
