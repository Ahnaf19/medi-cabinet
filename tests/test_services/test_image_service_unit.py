"""Unit tests for ImageService."""

from unittest.mock import AsyncMock, MagicMock

from src.database import MedicineData
from src.llm.base import LLMResponse, ToolCall
from src.services.image_service import ImageService


class TestImageServiceParseResponse:
    def _svc(self):
        provider = MagicMock()
        provider.supports_vision = True
        return ImageService(provider)

    def test_parse_tool_call_response(self):
        svc = self._svc()
        response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="tc1",
                    name="extract_medicine_from_image",
                    arguments={
                        "medicines": [
                            {"name": "Napa", "quantity": 10, "unit": "tablets"},
                            {"name": "Sergel", "quantity": 5},
                        ]
                    },
                )
            ],
        )
        result = svc._parse_response(response, 1, "User", 100)
        assert len(result) == 2
        assert result[0].name == "Napa"
        assert result[0].quantity == 10
        assert result[1].name == "Sergel"

    def test_parse_json_array_fallback(self):
        svc = self._svc()
        response = LLMResponse(
            content='Found medicines: [{"name": "Aspirin", "quantity": 20}]',
        )
        result = svc._parse_response(response, 1, "User", 100)
        assert len(result) == 1
        assert result[0].name == "Aspirin"

    def test_parse_json_object_fallback(self):
        svc = self._svc()
        response = LLMResponse(
            content='Found: {"name": "Paracetamol", "quantity": 5}',
        )
        result = svc._parse_response(response, 1, "User", 100)
        assert len(result) == 1
        assert result[0].name == "Paracetamol"

    def test_parse_unparseable_content(self):
        svc = self._svc()
        response = LLMResponse(content="I couldn't identify any medicines.")
        result = svc._parse_response(response, 1, "User", 100)
        assert len(result) == 0

    def test_parse_empty_response(self):
        svc = self._svc()
        response = LLMResponse(content=None)
        result = svc._parse_response(response, 1, "User", 100)
        assert len(result) == 0

    def test_dosage_appended_to_name(self):
        svc = self._svc()
        response = LLMResponse(
            content='[{"name": "Napa", "dosage": "500mg", "quantity": 10}]',
        )
        result = svc._parse_response(response, 1, "User", 100)
        assert "500Mg" in result[0].name or "500mg" in result[0].name.lower()


class TestImageServiceExtractFromPhoto:
    async def test_no_vision_support_returns_empty(self):
        provider = MagicMock()
        provider.supports_vision = False
        provider.provider_name = "test"
        svc = ImageService(provider)
        result = await svc.extract_from_photo(b"fake", 1, "User", 100)
        assert result == []

    async def test_happy_path_with_mock_provider(self):
        provider = AsyncMock()
        provider.supports_vision = True
        provider.complete_with_vision.return_value = LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="tc1",
                    name="extract_medicine_from_image",
                    arguments={"medicines": [{"name": "Napa", "quantity": 10}]},
                )
            ],
        )
        svc = ImageService(provider)
        result = await svc.extract_from_photo(b"fake_image", 1, "User", 100)
        assert len(result) == 1
        assert isinstance(result[0], MedicineData)

    async def test_provider_error_returns_empty(self):
        provider = AsyncMock()
        provider.supports_vision = True
        provider.complete_with_vision.side_effect = Exception("API error")
        svc = ImageService(provider)
        result = await svc.extract_from_photo(b"fake", 1, "User", 100)
        assert result == []
