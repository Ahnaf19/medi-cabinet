"""OpenAI LLM provider (placeholder)."""

from typing import Any, Dict, List, Optional

from src.llm.base import BaseLLMProvider, LLMMessage, LLMResponse
from src.llm.factory import LLMProviderFactory


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider placeholder.

    To use: set LLM_PROVIDER=openai and LLM_API_KEY=sk-... in your .env file.
    Default model: gpt-4o-mini
    """

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def supports_vision(self) -> bool:
        return True

    async def complete(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ) -> LLMResponse:
        raise NotImplementedError(
            "OpenAI provider not yet implemented. "
            "Set LLM_PROVIDER=groq for a working free-tier alternative."
        )


# Auto-register with factory
LLMProviderFactory.register("openai", OpenAIProvider)
