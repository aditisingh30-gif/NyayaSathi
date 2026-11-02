from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel


class LLMGenerationResult(BaseModel):
    """Result returned by an LLM provider."""
    raw_response: str
    direct_answer: Optional[str] = None
    legal_explanation: Optional[str] = None
    provider_name: str
    model_name: str
    tokens_used: Optional[int] = None
    is_refusal: bool = False


class BaseLLMProvider(ABC):
    """Abstract base class for all modular LLM providers."""

    def __init__(self, provider_name: str, model_name: str):
        self.provider_name = provider_name
        self.model_name = model_name

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMGenerationResult:
        """Generate response from the underlying LLM."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether required API keys / local endpoints are configured."""
        pass
