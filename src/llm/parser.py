"""LLM-based parser (Tier 2 fallback) for natural language understanding."""

from datetime import datetime
from typing import Optional

from loguru import logger

from src.llm.base import BaseLLMProvider, LLMMessage
from src.llm.tools import MEDICINE_EXTRACTION_TOOL
from src.parsers import ParsedCommand

SYSTEM_PROMPT = """You are a medicine inventory assistant for Bangladeshi families.
Extract structured commands from natural language messages about medicines.

Common Bangladesh medicine brands: Napa (paracetamol), Napa Extra, Sergel (esomeprazole),
Seclo (omeprazole), Ace (paracetamol), Maxpro (esomeprazole), Alatrol (cetirizine),
Fexo (fexofenadine), Histacin (chlorpheniramine), Virux (acyclovir),
Losectil (omeprazole), Monas (montelukast), Brodil (salbutamol),
Zimax (azithromycin), Cef-3 (cefixime), Amoxil (amoxicillin).

Rules:
- If user mentions adding/buying/getting medicine → command_type = "add"
- If user mentions using/taking/consuming medicine → command_type = "use"
- If user asks about availability or searches → command_type = "search"
- If user wants to see all medicines → command_type = "list"
- Default unit is "tablets" if not specified
- Parse any mentioned expiry dates into ISO format
- Detect storage locations when mentioned"""


class LLMParser:
    """Tier 2 parser that uses an LLM for natural language understanding."""

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    async def parse(self, text: str) -> Optional[ParsedCommand]:
        """Parse natural language text using LLM.

        Args:
            text: User's message text

        Returns:
            ParsedCommand if LLM successfully extracts a command, None otherwise
        """
        try:
            messages = [
                LLMMessage(role="system", content=SYSTEM_PROMPT),
                LLMMessage(role="user", content=text),
            ]

            response = await self.provider.complete(
                messages=messages,
                tools=[MEDICINE_EXTRACTION_TOOL],
                tool_choice="auto",
            )

            if not response.has_tool_calls:
                logger.debug(f"LLM returned no tool calls for: {text}")
                return None

            args = response.get_tool_arguments("extract_medicine_command")
            if not args:
                return None

            command_type = args.get("command_type")
            if not command_type or command_type not in ("add", "use", "search", "list"):
                return None

            # Parse expiry date if provided
            expiry_date = None
            if expiry_str := args.get("expiry_date"):
                try:
                    expiry_date = datetime.fromisoformat(expiry_str)
                except ValueError:
                    pass

            return ParsedCommand(
                command_type=command_type,
                medicine_name=args.get("medicine_name", "").strip().title() or None,
                quantity=args.get("quantity"),
                unit=args.get("unit", "tablets"),
                expiry_date=expiry_date,
                location=args.get("location"),
                confidence=0.8,
                raw_text=text,
            )

        except Exception as e:
            logger.warning(f"LLM parsing failed: {e}")
            return None
