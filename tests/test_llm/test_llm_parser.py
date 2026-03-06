"""Tests for LLM parser (Tier 2 fallback)."""

import pytest

from src.llm.base import BaseLLMProvider, LLMResponse, ToolCall
from src.llm.parser import LLMParser


class MockProvider(BaseLLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, response: LLMResponse):
        super().__init__(api_key="test", model="test")
        self._response = response

    @property
    def provider_name(self) -> str:
        return "mock"

    async def complete(self, messages, tools=None, tool_choice=None):
        return self._response


class TestLLMParser:
    """Test LLM-based parser."""

    @pytest.mark.asyncio
    async def test_parse_add_command(self):
        """Test parsing an add command from LLM."""
        response = LLMResponse(
            tool_calls=[
                ToolCall(
                    id="1",
                    name="extract_medicine_command",
                    arguments={
                        "command_type": "add",
                        "medicine_name": "Napa",
                        "quantity": 10,
                        "unit": "tablets",
                    },
                )
            ]
        )
        parser = LLMParser(MockProvider(response))
        result = await parser.parse("I bought some Napa today, 10 pieces")

        assert result is not None
        assert result.command_type == "add"
        assert result.medicine_name == "Napa"
        assert result.quantity == 10
        assert result.unit == "tablets"

    @pytest.mark.asyncio
    async def test_parse_use_command(self):
        """Test parsing a use command from LLM."""
        response = LLMResponse(
            tool_calls=[
                ToolCall(
                    id="1",
                    name="extract_medicine_command",
                    arguments={
                        "command_type": "use",
                        "medicine_name": "paracetamol",
                        "quantity": 2,
                    },
                )
            ]
        )
        parser = LLMParser(MockProvider(response))
        result = await parser.parse("I had a headache so I took 2 paracetamol")

        assert result is not None
        assert result.command_type == "use"
        assert result.medicine_name == "Paracetamol"
        assert result.quantity == 2

    @pytest.mark.asyncio
    async def test_parse_search_command(self):
        """Test parsing a search command from LLM."""
        response = LLMResponse(
            tool_calls=[
                ToolCall(
                    id="1",
                    name="extract_medicine_command",
                    arguments={
                        "command_type": "search",
                        "medicine_name": "Sergel",
                    },
                )
            ]
        )
        parser = LLMParser(MockProvider(response))
        result = await parser.parse("Is there any Sergel left?")

        assert result is not None
        assert result.command_type == "search"
        assert result.medicine_name == "Sergel"

    @pytest.mark.asyncio
    async def test_parse_no_tool_calls(self):
        """Test that parser returns None when LLM returns no tool calls."""
        response = LLMResponse(content="I don't understand")
        parser = LLMParser(MockProvider(response))
        result = await parser.parse("Hello there")

        assert result is None

    @pytest.mark.asyncio
    async def test_parse_with_expiry_date(self):
        """Test parsing with expiry date."""
        response = LLMResponse(
            tool_calls=[
                ToolCall(
                    id="1",
                    name="extract_medicine_command",
                    arguments={
                        "command_type": "add",
                        "medicine_name": "Napa",
                        "quantity": 10,
                        "expiry_date": "2026-12-31",
                    },
                )
            ]
        )
        parser = LLMParser(MockProvider(response))
        result = await parser.parse("Added Napa 10 expires Dec 2026")

        assert result is not None
        assert result.expiry_date is not None
        assert result.expiry_date.year == 2026

    @pytest.mark.asyncio
    async def test_parse_confidence(self):
        """Test that LLM-parsed commands have lower confidence."""
        response = LLMResponse(
            tool_calls=[
                ToolCall(
                    id="1",
                    name="extract_medicine_command",
                    arguments={"command_type": "add", "medicine_name": "Napa"},
                )
            ]
        )
        parser = LLMParser(MockProvider(response))
        result = await parser.parse("got some napa")

        assert result is not None
        assert result.confidence < 1.0

    @pytest.mark.asyncio
    async def test_parse_invalid_command_type(self):
        """Test that invalid command types are rejected."""
        response = LLMResponse(
            tool_calls=[
                ToolCall(
                    id="1",
                    name="extract_medicine_command",
                    arguments={"command_type": "invalid"},
                )
            ]
        )
        parser = LLMParser(MockProvider(response))
        result = await parser.parse("something weird")

        assert result is None

    @pytest.mark.asyncio
    async def test_parse_exception_handling(self):
        """Test graceful handling of provider errors."""

        class ErrorProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "error"

            async def complete(self, messages, tools=None, tool_choice=None):
                raise RuntimeError("API Error")

        parser = LLMParser(ErrorProvider(api_key="test", model="test"))
        result = await parser.parse("anything")

        assert result is None
