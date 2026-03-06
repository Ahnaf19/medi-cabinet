"""Tests for LLM provider factory."""

import pytest

from src.llm.base import BaseLLMProvider, LLMResponse
from src.llm.factory import LLMProviderFactory


class DummyProvider(BaseLLMProvider):
    """Dummy provider for testing."""

    @property
    def provider_name(self) -> str:
        return "dummy"

    async def complete(self, messages, tools=None, tool_choice=None):
        return LLMResponse(content="test response")


class TestLLMProviderFactory:
    """Test LLM provider factory."""

    def test_register_and_create(self):
        """Test registering and creating a provider."""
        LLMProviderFactory.register("dummy", DummyProvider)

        provider = LLMProviderFactory.create("dummy", api_key="test-key", model="test-model")
        assert isinstance(provider, DummyProvider)
        assert provider.provider_name == "dummy"
        assert provider.api_key == "test-key"
        assert provider.model == "test-model"

    def test_create_unknown_provider(self):
        """Test creating an unregistered provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            LLMProviderFactory.create("nonexistent", api_key="key", model="model")

    def test_case_insensitive_registration(self):
        """Test that provider names are case-insensitive."""
        LLMProviderFactory.register("TestCase", DummyProvider)
        provider = LLMProviderFactory.create("testcase", api_key="key", model="model")
        assert isinstance(provider, DummyProvider)

    def test_from_config_disabled(self):
        """Test from_config returns None when provider is not set."""

        class FakeSettings:
            llm_provider = None
            llm_api_key = None
            llm_model = "test"
            llm_temperature = 0.0

        result = LLMProviderFactory.from_config(FakeSettings())
        assert result is None

    def test_from_config_no_api_key(self):
        """Test from_config returns None when API key is missing."""

        class FakeSettings:
            llm_provider = "groq"
            llm_api_key = None
            llm_model = "test"
            llm_temperature = 0.0

        result = LLMProviderFactory.from_config(FakeSettings())
        assert result is None

    def test_available_providers(self):
        """Test listing available providers."""
        LLMProviderFactory.register("dummy", DummyProvider)
        providers = LLMProviderFactory.available_providers()
        assert "dummy" in providers

    def test_groq_auto_registered(self):
        """Test that Groq is auto-registered when providers are imported."""
        import src.llm.providers  # noqa: F401

        assert "groq" in LLMProviderFactory.available_providers()

    def test_openai_auto_registered(self):
        """Test that OpenAI placeholder is auto-registered."""
        import src.llm.providers  # noqa: F401

        assert "openai" in LLMProviderFactory.available_providers()

    def test_anthropic_auto_registered(self):
        """Test that Anthropic placeholder is auto-registered."""
        import src.llm.providers  # noqa: F401

        assert "anthropic" in LLMProviderFactory.available_providers()
