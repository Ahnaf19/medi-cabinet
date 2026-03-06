"""Anthropic LLM provider (placeholder)."""

from typing import Any

from src.llm.base import BaseLLMProvider, LLMMessage, LLMResponse
from src.llm.factory import LLMProviderFactory


class AnthropicProvider(BaseLLMProvider):
    """Anthropic provider placeholder.

    To use: set LLM_PROVIDER=anthropic and LLM_API_KEY=sk-ant-... in your .env file.
    Default model: claude-sonnet-4-6
    """

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def supports_vision(self) -> bool:
        return True

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        raise NotImplementedError(
            "Anthropic provider not yet implemented. "
            "Set LLM_PROVIDER=groq for a working free-tier alternative."
        )


# Auto-register with factory
LLMProviderFactory.register("anthropic", AnthropicProvider)
