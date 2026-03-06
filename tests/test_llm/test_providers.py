"""Tests for LLM providers."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.llm.base import LLMMessage
from src.llm.providers.anthropic import AnthropicProvider
from src.llm.providers.groq import GroqProvider
from src.llm.providers.openai import OpenAIProvider


class TestGroqProvider:
    """Test Groq provider."""

    def test_provider_name(self):
        provider = GroqProvider(api_key="test", model="test-model")
        assert provider.provider_name == "groq"

    def test_supports_vision(self):
        provider = GroqProvider(api_key="test", model="test-model")
        assert provider.supports_vision is True

    def test_supports_tool_calling(self):
        provider = GroqProvider(api_key="test", model="test-model")
        assert provider.supports_tool_calling is True

    def test_format_messages_simple(self):
        provider = GroqProvider(api_key="test", model="test-model")
        messages = [
            LLMMessage(role="system", content="You are helpful"),
            LLMMessage(role="user", content="Hello"),
        ]
        formatted = provider._format_messages(messages)
        assert len(formatted) == 2
        assert formatted[0]["role"] == "system"
        assert formatted[0]["content"] == "You are helpful"
        assert formatted[1]["role"] == "user"

    def test_format_messages_with_image(self):
        provider = GroqProvider(api_key="test", model="test-model")
        messages = [
            LLMMessage(
                role="user",
                content="What's in this image?",
                image_base64="abc123",
            ),
        ]
        formatted = provider._format_messages(messages)
        assert isinstance(formatted[0]["content"], list)
        assert formatted[0]["content"][0]["type"] == "text"
        assert formatted[0]["content"][1]["type"] == "image_url"

    def test_build_headers(self):
        provider = GroqProvider(api_key="test-key-123", model="test-model")
        headers = provider._build_headers()
        assert headers["Authorization"] == "Bearer test-key-123"
        assert headers["Content-Type"] == "application/json"


class TestOpenAIProvider:
    """Test OpenAI provider."""

    def test_provider_name(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
        assert provider.provider_name == "openai"

    def test_supports_vision(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
        assert provider.supports_vision is True

    def test_supports_tool_calling(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
        assert provider.supports_tool_calling is True

    def test_format_messages_simple(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
        messages = [
            LLMMessage(role="system", content="You are helpful"),
            LLMMessage(role="user", content="Hello"),
        ]
        formatted = provider._format_messages(messages)
        assert len(formatted) == 2
        assert formatted[0]["role"] == "system"
        assert formatted[0]["content"] == "You are helpful"

    def test_format_messages_with_image_base64(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
        messages = [
            LLMMessage(
                role="user",
                content="What's in this image?",
                image_base64="abc123",
            ),
        ]
        formatted = provider._format_messages(messages)
        assert isinstance(formatted[0]["content"], list)
        assert formatted[0]["content"][0]["type"] == "text"
        assert formatted[0]["content"][1]["type"] == "image_url"
        assert "base64" in formatted[0]["content"][1]["image_url"]["url"]

    def test_format_messages_with_image_url(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
        messages = [
            LLMMessage(
                role="user",
                content="What's in this?",
                image_url="https://example.com/img.jpg",
            ),
        ]
        formatted = provider._format_messages(messages)
        assert isinstance(formatted[0]["content"], list)
        assert formatted[0]["content"][1]["image_url"]["url"] == "https://example.com/img.jpg"

    def test_format_messages_with_tool_call_id(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
        messages = [
            LLMMessage(role="tool", content='{"result": "ok"}', tool_call_id="tc_123"),
        ]
        formatted = provider._format_messages(messages)
        assert formatted[0]["tool_call_id"] == "tc_123"

    def test_build_headers(self):
        provider = OpenAIProvider(api_key="sk-test-key", model="gpt-4o-mini")
        headers = provider._build_headers()
        assert headers["Authorization"] == "Bearer sk-test-key"
        assert headers["Content-Type"] == "application/json"

    async def test_complete_success(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")

        mock_response = httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Hello! How can I help?",
                        }
                    }
                ],
                "model": "gpt-4o-mini",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await provider.complete([LLMMessage(role="user", content="Hello")])

        assert result.content == "Hello! How can I help?"
        assert result.model == "gpt-4o-mini"

    async def test_complete_with_tool_calls(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")

        mock_response = httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "function": {
                                        "name": "extract_medicine_command",
                                        "arguments": json.dumps(
                                            {
                                                "command_type": "add",
                                                "medicine_name": "Napa",
                                                "quantity": 10,
                                            }
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ],
                "model": "gpt-4o-mini",
                "usage": {},
            },
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await provider.complete(
                [LLMMessage(role="user", content="add Napa 10")],
                tools=[{"type": "function", "function": {"name": "extract_medicine_command"}}],
            )

        assert result.has_tool_calls
        assert result.tool_calls[0].name == "extract_medicine_command"
        assert result.tool_calls[0].arguments["medicine_name"] == "Napa"

    async def test_complete_api_error(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")

        mock_response = httpx.Response(401, json={"error": "invalid api key"})

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await provider.complete([LLMMessage(role="user", content="Hello")])

        assert result.content is None
        assert "error" in result.raw

    async def test_complete_with_vision_uses_gpt4o(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")

        mock_response = httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "I see medicine"}}],
                "model": "gpt-4o",
                "usage": {},
            },
        )

        with patch(
            "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response
        ) as mock_post:
            result = await provider.complete_with_vision(
                [LLMMessage(role="user", content="What's this?", image_base64="abc")],
                tools=[{"type": "function", "function": {"name": "extract"}}],
            )

        # Should have used gpt-4o for vision
        call_json = mock_post.call_args[1]["json"]
        assert call_json["model"] == "gpt-4o"
        # Tools should be passed through (unlike Groq)
        assert "tools" in call_json
        assert result.content == "I see medicine"
        # Model should be restored after call
        assert provider.model == "gpt-4o-mini"


class TestAnthropicProvider:
    """Test Anthropic provider placeholder."""

    def test_provider_name(self):
        provider = AnthropicProvider(api_key="test", model="claude-sonnet-4-6")
        assert provider.provider_name == "anthropic"

    @pytest.mark.asyncio
    async def test_complete_raises_not_implemented(self):
        provider = AnthropicProvider(api_key="test", model="claude-sonnet-4-6")
        with pytest.raises(NotImplementedError):
            await provider.complete([LLMMessage(role="user", content="hello")])
