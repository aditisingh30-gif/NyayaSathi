import httpx
from typing import Optional
from app.config import settings
from app.core.logging_config import logger
from app.llm.base import BaseLLMProvider, LLMGenerationResult


class OllamaProvider(BaseLLMProvider):
    """Local offline Ollama LLM provider."""

    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None):
        model = model_name or settings.OLLAMA_MODEL or "llama3"
        super().__init__(provider_name="ollama", model_name=model)
        self.base_url = (base_url or settings.OLLAMA_BASE_URL or "http://localhost:11434").rstrip("/")

    def is_available(self) -> bool:
        # Check if Ollama is reachable
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=1.5)
            return r.status_code == 200
        except Exception:
            return False

    async def generate_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMGenerationResult:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_instruction or "",
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(url, json=payload)
            except Exception as e:
                logger.error(f"Cannot connect to Ollama at {self.base_url}: {e}")
                raise RuntimeError(f"Ollama server is unreachable at {self.base_url}. Ensure Ollama is running.")

            if resp.status_code != 200:
                logger.error(f"Ollama API error ({resp.status_code}): {resp.text}")
                raise RuntimeError(f"Ollama request failed with status {resp.status_code}: {resp.text}")

            data = resp.json()
            text = data.get("response", "")
            eval_count = data.get("eval_count", 0)

            is_refusal = "not available" in text.lower() or "not indexed" in text.lower()

            return LLMGenerationResult(
                raw_response=text,
                provider_name=self.provider_name,
                model_name=self.model_name,
                tokens_used=eval_count,
                is_refusal=is_refusal
            )
