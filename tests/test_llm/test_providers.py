"""Tests for LLM providers."""

import pytest

from src.llm.providers.groq import GroqProvider
from src.llm.providers.openai import OpenAIProvider
from src.llm.providers.anthropic import AnthropicProvider
from src.llm.base import LLMMessage


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
    """Test OpenAI provider placeholder."""

    def test_provider_name(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
        assert provider.provider_name == "openai"

    @pytest.mark.asyncio
    async def test_complete_raises_not_implemented(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
        with pytest.raises(NotImplementedError):
            await provider.complete([LLMMessage(role="user", content="hello")])


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
