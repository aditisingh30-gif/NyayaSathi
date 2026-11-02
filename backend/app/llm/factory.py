from typing import Optional
from app.config import settings
from app.core.logging_config import logger
from app.llm.base import BaseLLMProvider
from app.llm.gemini_provider import GoogleGeminiProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.fallback_provider import GroundedSynthesizerProvider


class LLMProviderFactory:
    """Factory to instantiate and retrieve configured LLM providers."""

    @staticmethod
    def get_provider(provider_name: Optional[str] = None) -> BaseLLMProvider:
        requested = (provider_name or settings.DEFAULT_LLM_PROVIDER or "auto").lower().strip()

        # 1. Google Gemini
        if requested in ("gemini", "google"):
            gemini = GoogleGeminiProvider()
            if gemini.is_available():
                return gemini
            logger.warning("Gemini requested but GEMINI_API_KEY is not set. Checking alternatives...")

        # 2. OpenAI
        if requested in ("openai", "gpt"):
            openai = OpenAIProvider()
            if openai.is_available():
                return openai
            logger.warning("OpenAI requested but OPENAI_API_KEY is not set. Checking alternatives...")

        # 3. Ollama
        if requested == "ollama":
            ollama = OllamaProvider()
            if ollama.is_available():
                return ollama
            logger.warning("Ollama requested but local server is not reachable. Checking alternatives...")

        # 4. Auto-detection mode: pick first available external provider
        gemini = GoogleGeminiProvider()
        if gemini.is_available():
            return gemini

        openai = OpenAIProvider()
        if openai.is_available():
            return openai

        ollama = OllamaProvider()
        if ollama.is_available():
            return ollama

        # 5. Default reliable provider: GroundedSynthesizerProvider
        return GroundedSynthesizerProvider()
