"""Image processing service using Vision LLM."""

import base64
import json
from typing import Any

from loguru import logger

from src.database import MedicineData
from src.llm.base import BaseLLMProvider, LLMMessage
from src.llm.tools import IMAGE_EXTRACTION_TOOL

IMAGE_SYSTEM_PROMPT = """You are a medicine identification assistant.
Analyze the photo and extract information about any medicines visible.
Look for: brand name, generic name, dosage, quantity, expiry date, manufacturer.
Focus on Bangladeshi medicine brands. Return structured data for each medicine found.

If the image is a prescription, extract each prescribed medicine.
If the image is a medicine packet/box, extract the details from the packaging."""


class ImageService:
    """Processes medicine photos using Vision LLM."""

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    async def extract_from_photo(
        self,
        image_bytes: bytes,
        user_id: int,
        username: str,
        group_chat_id: int,
    ) -> list[MedicineData]:
        """Extract medicine data from a photo.

        Args:
            image_bytes: Raw image bytes
            user_id: User ID who sent the photo
            username: Username who sent the photo
            group_chat_id: Chat ID

        Returns:
            List of MedicineData objects extracted from the image
        """
        if not self.provider.supports_vision:
            logger.warning(f"Provider {self.provider.provider_name} doesn't support vision")
            return []

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        messages = [
            LLMMessage(role="system", content=IMAGE_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content="Please identify the medicines in this image and extract their details.",
                image_base64=image_b64,
            ),
        ]

        try:
            response = await self.provider.complete_with_vision(
                messages=messages,
                tools=[IMAGE_EXTRACTION_TOOL],
            )

            medicines = self._parse_response(response, user_id, username, group_chat_id)
            return medicines

        except Exception as e:
            logger.error(f"Vision extraction failed: {e}")
            return []

    def _parse_response(
        self,
        response,
        user_id: int,
        username: str,
        group_chat_id: int,
    ) -> list[MedicineData]:
        """Parse LLM response into MedicineData objects."""
        medicines = []

        # Try tool call response first
        if response.has_tool_calls:
            args = response.get_tool_arguments("extract_medicine_from_image")
            if args and "medicines" in args:
                for med in args["medicines"]:
                    medicines.append(self._med_dict_to_data(med, user_id, username, group_chat_id))
                return medicines

        # Fall back to parsing content as JSON (for vision models without tool calling)
        if response.content:
            try:
                # Try to find JSON in the response
                content = response.content
                start = content.find("[")
                end = content.rfind("]") + 1
                if start >= 0 and end > start:
                    items = json.loads(content[start:end])
                    for med in items:
                        medicines.append(
                            self._med_dict_to_data(med, user_id, username, group_chat_id)
                        )
                    return medicines
            except (json.JSONDecodeError, KeyError):
                pass

            # Try single object
            try:
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    med = json.loads(content[start:end])
                    medicines.append(self._med_dict_to_data(med, user_id, username, group_chat_id))
            except (json.JSONDecodeError, KeyError):
                logger.warning("Could not parse vision response as structured data")

        return medicines

    @staticmethod
    def _med_dict_to_data(
        med: dict[str, Any],
        user_id: int,
        username: str,
        group_chat_id: int,
    ) -> MedicineData:
        """Convert a dict from LLM response to MedicineData."""
        from datetime import datetime

        expiry = None
        if expiry_str := med.get("expiry_date"):
            try:
                expiry = datetime.fromisoformat(expiry_str)
            except ValueError:
                pass

        name = med.get("name", "Unknown Medicine")
        dosage = med.get("dosage", "")
        if dosage and dosage not in name:
            name = f"{name} {dosage}".strip()

        return MedicineData(
            name=name.title(),
            quantity=med.get("quantity", 1),
            unit=med.get("unit", "tablets"),
            expiry_date=expiry,
            location=None,
            added_by_user_id=user_id,
            added_by_username=username,
            group_chat_id=group_chat_id,
        )
