"""Abstract base classes for LLM providers."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMMessage:
    """A message in the LLM conversation."""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_call_id: str | None = None
    image_url: str | None = None
    image_base64: str | None = None


@dataclass
class ToolCall:
    """A tool call returned by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from an LLM completion."""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    def get_tool_arguments(self, tool_name: str) -> dict[str, Any] | None:
        """Get arguments for a specific tool call by name."""
        for tc in self.tool_calls:
            if tc.name == tool_name:
                return tc.arguments
        return None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: str, model: str, temperature: float = 0.0):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        ...

    @property
    def supports_vision(self) -> bool:
        return False

    @property
    def supports_tool_calling(self) -> bool:
        return True

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        """Send a completion request.

        Args:
            messages: List of conversation messages
            tools: Optional tool definitions for function calling
            tool_choice: "auto", "none", or specific tool name

        Returns:
            LLMResponse with content and/or tool calls
        """
        ...

    async def complete_with_vision(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send a vision completion request (for image analysis).

        Default implementation raises NotImplementedError.
        Override in providers that support vision.
        """
        raise NotImplementedError(
            f"{self.provider_name} does not support vision. "
            "Override complete_with_vision() to add support."
        )

    @staticmethod
    def _parse_tool_calls(raw_tool_calls: list[dict[str, Any]]) -> list[ToolCall]:
        """Parse raw tool calls from API response into ToolCall objects."""
        tool_calls = []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            args_str = func.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=func.get("name", ""),
                    arguments=args,
                )
            )
        return tool_calls
