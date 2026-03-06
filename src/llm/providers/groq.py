"""Groq LLM provider using OpenAI-compatible API."""

from typing import Any

import httpx
from loguru import logger

from src.llm.base import BaseLLMProvider, LLMMessage, LLMResponse
from src.llm.factory import LLMProviderFactory

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_VISION_MODEL = "llama-3.2-90b-vision-preview"


class GroqProvider(BaseLLMProvider):
    """Groq provider using their OpenAI-compatible API."""

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def supports_vision(self) -> bool:
        return True

    @property
    def supports_tool_calling(self) -> bool:
        return True

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _format_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert LLMMessage list to Groq API format."""
        formatted = []
        for msg in messages:
            if msg.image_base64:
                content = [
                    {"type": "text", "text": msg.content},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{msg.image_base64}",
                        },
                    },
                ]
                formatted.append({"role": msg.role, "content": content})
            elif msg.image_url:
                content = [
                    {"type": "text", "text": msg.content},
                    {
                        "type": "image_url",
                        "image_url": {"url": msg.image_url},
                    },
                ]
                formatted.append({"role": msg.role, "content": content})
            else:
                entry = {"role": msg.role, "content": msg.content}
                if msg.tool_call_id:
                    entry["tool_call_id"] = msg.tool_call_id
                formatted.append(entry)
        return formatted

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        """Send completion request to Groq API."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._format_messages(messages),
            "temperature": self.temperature,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GROQ_API_URL,
                headers=self._build_headers(),
                json=payload,
            )

            if response.status_code != 200:
                logger.error(f"Groq API error {response.status_code}: {response.text}")
                return LLMResponse(content=None, raw={"error": response.text})

            data = response.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})

            tool_calls = []
            if raw_tc := message.get("tool_calls"):
                tool_calls = self._parse_tool_calls(raw_tc)

            return LLMResponse(
                content=message.get("content"),
                tool_calls=tool_calls,
                model=data.get("model", self.model),
                usage=data.get("usage", {}),
                raw=data,
            )

    async def complete_with_vision(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send vision completion request using Groq's vision model."""
        original_model = self.model
        self.model = GROQ_VISION_MODEL
        try:
            # Vision model on Groq doesn't support tool calling,
            # so we ask for structured JSON in the prompt instead
            return await self.complete(messages, tools=None, tool_choice=None)
        finally:
            self.model = original_model


# Auto-register with factory
LLMProviderFactory.register("groq", GroqProvider)
