import httpx
from typing import Optional
from app.config import settings
from app.core.logging_config import logger
from app.llm.base import BaseLLMProvider, LLMGenerationResult


class GoogleGeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider using direct REST API."""

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        model = model_name or settings.GEMINI_MODEL or "gemini-1.5-flash"
        super().__init__(provider_name="gemini", model_name=model)
        self.api_key = api_key or settings.GEMINI_API_KEY

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
            raise ValueError("GEMINI_API_KEY is not configured in environment or .env file.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

        contents = []
        if system_instruction:
            contents.append({
                "role": "user",
                "parts": [{"text": f"System Instructions:\n{system_instruction}\n\nPlease acknowledge and follow these instructions."}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will strictly follow all instructions and rely only on the provided statutory evidence."}]
            })

        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error(f"Gemini API error ({resp.status_code}): {resp.text}")
                raise RuntimeError(f"Gemini API request failed with status {resp.status_code}: {resp.text}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini returned no candidates.")

            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            usage = data.get("usageMetadata", {})
            total_tokens = usage.get("totalTokenCount", 0)

            is_refusal = "not available" in text.lower() or "not indexed" in text.lower()

            return LLMGenerationResult(
                raw_response=text,
                provider_name=self.provider_name,
                model_name=self.model_name,
                tokens_used=total_tokens,
                is_refusal=is_refusal
            )
