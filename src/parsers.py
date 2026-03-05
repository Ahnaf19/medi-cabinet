"""Natural language parsing for medicine bot commands."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Literal
from dateutil import parser as date_parser


CommandType = Literal[
    "add", "use", "search", "list", "routine", "cost", "interactions", "analytics", "unknown"
]


@dataclass
class ParsedCommand:
    """Parsed command with extracted information."""

    command_type: CommandType
    medicine_name: Optional[str] = None
    quantity: Optional[int] = None
    unit: str = "tablets"
    expiry_date: Optional[datetime] = None
    location: Optional[str] = None
    confidence: float = 1.0
    raw_text: str = ""
    # Phase 4: Routine fields
    meal_relation: Optional[str] = None
    schedule_times: Optional[list] = None
    frequency: Optional[str] = None
    # Phase 5: Cost field
    cost: Optional[float] = None


class CommandParser:
    """Main parser that dispatches to specific command parsers."""

    def __init__(self):
        """Initialize parser with sub-parsers."""
        self.add_parser = AddCommandParser()
        self.use_parser = UseCommandParser()
        self.search_parser = SearchCommandParser()
        self.list_parser = ListCommandParser()
        self.routine_parser = RoutineCommandParser()
        self.cost_parser = CostCommandParser()

    def parse(self, text: str) -> ParsedCommand:
        """Parse text and return structured command.

        Args:
            text: Raw text to parse

        Returns:
            ParsedCommand with extracted information
        """
        text = text.strip()

        # Try list command first (simple patterns)
        if result := self.list_parser.parse(text):
            result.raw_text = text
            return result

        # Try routine command
        if result := self.routine_parser.parse(text):
            result.raw_text = text
            return result

        # Try cost command
        if result := self.cost_parser.parse(text):
            result.raw_text = text
            return result

        # Try add command (+ prefix or keywords like "bought", "got")
        if result := self.add_parser.parse(text):
            result.raw_text = text
            return result

        # Try use command (- prefix or keywords like "used", "took")
        if result := self.use_parser.parse(text):
            result.raw_text = text
            return result

        # Try search command (? prefix or keywords like "have", "check")
        if result := self.search_parser.parse(text):
            result.raw_text = text
            return result

        # Unknown command
        return ParsedCommand(
            command_type="unknown",
            raw_text=text,
            confidence=0.0,
        )


class AddCommandParser:
    """Parser for adding medicines."""

    # Regex patterns for add commands (in priority order)
    PATTERNS = [
        # +Napa 10 caps / +Napa 10
        r"^\+\s*(\w+(?:\s+\w+)?)\s+(\d+)(?:\s+(\w+))?",
        # Bought/Got Napa Extra 10 tablets
        r"(?:bought|got|purchase[d]?|add(?:ed)?)\s+(\w+(?:\s+\w+)?)[,]?\s*(\d+)(?:\s+(\w+))?",
        # 10 Napa caps (quantity first)
        r"^(\d+)\s+(\w+(?:\s+\w+)?)(?:\s+(\w+))?",
        # Got paracetamol (no quantity)
        r"(?:bought|got|purchase[d]?|add(?:ed)?)\s+(\w+(?:\s+\w+)?)",
    ]

    # Unit patterns
    UNIT_KEYWORDS = [
        "tablet",
        "tablets",
        "tab",
        "tabs",
        "capsule",
        "capsules",
        "cap",
        "caps",
        "ml",
        "milliliter",
        "milliliters",
        "mg",
        "milligram",
        "milligrams",
        "strip",
        "strips",
        "bottle",
        "bottles",
        "piece",
        "pieces",
        "pcs",
        "pc",
    ]

    def parse(self, text: str) -> Optional[ParsedCommand]:
        """Parse add command.

        Args:
            text: Raw text to parse

        Returns:
            ParsedCommand if matched, None otherwise
        """
        text_lower = text.lower().strip()

        # Check if this looks like an add command
        if not (
            text_lower.startswith("+")
            or any(keyword in text_lower for keyword in ["bought", "got", "purchase", "add"])
            or re.match(r"^\d+\s+\w+", text_lower)
        ):
            return None

        for pattern in self.PATTERNS:
            if match := re.search(pattern, text_lower, re.IGNORECASE):
                groups = match.groups()

                # Extract medicine name and quantity based on pattern
                if text_lower.startswith("+"):
                    # Pattern: +Napa 10 caps
                    medicine_name = groups[0]
                    quantity = int(groups[1])
                    unit = groups[2] if len(groups) > 2 and groups[2] else "tablets"
                elif text_lower[0].isdigit():
                    # Pattern: 10 Napa caps (quantity first)
                    quantity = int(groups[0])
                    medicine_name = groups[1]
                    unit = groups[2] if len(groups) > 2 and groups[2] else "tablets"
                elif len(groups) >= 2 and groups[1]:
                    # Pattern: Bought Napa 10
                    medicine_name = groups[0]
                    try:
                        quantity = int(groups[1])
                    except (ValueError, IndexError):
                        quantity = None
                    unit = groups[2] if len(groups) > 2 and groups[2] else "tablets"
                else:
                    # Pattern: Got paracetamol (no quantity)
                    medicine_name = groups[0]
                    quantity = None
                    unit = "tablets"

                # Normalize unit
                unit = self._normalize_unit(unit)

                # Extract expiry date and location if present
                expiry_date = self._extract_expiry_date(text)
                location = self._extract_location(text)

                return ParsedCommand(
                    command_type="add",
                    medicine_name=medicine_name.strip().title(),
                    quantity=quantity,
                    unit=unit,
                    expiry_date=expiry_date,
                    location=location,
                    confidence=1.0,
                )

        return None

    def _normalize_unit(self, unit: str) -> str:
        """Normalize medicine unit.

        Args:
            unit: Raw unit string

        Returns:
            Normalized unit
        """
        unit_lower = unit.lower().strip()

        if unit_lower in ["tablet", "tablets", "tab", "tabs"]:
            return "tablets"
        elif unit_lower in ["capsule", "capsules", "cap", "caps"]:
            return "capsules"
        elif unit_lower in ["ml", "milliliter", "milliliters"]:
            return "ml"
        elif unit_lower in ["mg", "milligram", "milligrams"]:
            return "mg"
        elif unit_lower in ["strip", "strips"]:
            return "strips"
        elif unit_lower in ["bottle", "bottles"]:
            return "bottles"
        elif unit_lower in ["piece", "pieces", "pcs", "pc"]:
            return "pieces"
        else:
            return "tablets"

    def _extract_expiry_date(self, text: str) -> Optional[datetime]:
        """Extract expiry date from text.

        Args:
            text: Text to search

        Returns:
            Parsed datetime or None
        """
        # Look for expiry date patterns
        patterns = [
            r"expire[sd]?\s+([A-Za-z]+\s+\d{4})",  # expires Dec 2025
            r"expiry[:\s]+([A-Za-z]+\s+\d{4})",  # expiry: Dec 2025
            r"exp[:\s]+(\d{1,2}[/-]\d{4})",  # exp: 12/2025
            r"(\d{4}-\d{2})",  # 2025-12
        ]

        for pattern in patterns:
            if match := re.search(pattern, text, re.IGNORECASE):
                date_str = match.group(1)
                try:
                    # Parse flexible date format
                    parsed_date = date_parser.parse(date_str, fuzzy=True)
                    return parsed_date
                except (ValueError, date_parser.ParserError):
                    continue

        return None

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract storage location from text.

        Args:
            text: Text to search

        Returns:
            Location string or None
        """
        # Look for location patterns
        patterns = [
            r"(?:in|at|location[:\s]+)\s+([a-z\s]+(?:drawer|cabinet|room|shelf|box))",
        ]

        for pattern in patterns:
            if match := re.search(pattern, text, re.IGNORECASE):
                return match.group(1).strip().title()

        return None


class UseCommandParser:
    """Parser for using/consuming medicines."""

    # Regex patterns for use commands (in priority order)
    PATTERNS = [
        # -Napa 2
        r"^-\s*(\w+(?:\s+\w+)?)\s+(\d+)",
        # Used 2 Napa
        r"(?:used|took|consume[d]?)\s+(\d+)\s+(\w+(?:\s+\w+)?)",
        # Used Napa 2
        r"(?:used|took|consume[d]?)\s+(\w+(?:\s+\w+)?)[,]?\s*(\d+)",
        # Used some Napa / Took Napa
        r"(?:used|took|consume[d]?)\s+(?:some\s+)?(\w+(?:\s+\w+)?)",
    ]

    def parse(self, text: str) -> Optional[ParsedCommand]:
        """Parse use command.

        Args:
            text: Raw text to parse

        Returns:
            ParsedCommand if matched, None otherwise
        """
        text_lower = text.lower().strip()

        # Check if this looks like a use command
        if not (
            text_lower.startswith("-")
            or any(keyword in text_lower for keyword in ["used", "took", "consume"])
        ):
            return None

        for pattern in self.PATTERNS:
            if match := re.search(pattern, text_lower, re.IGNORECASE):
                groups = match.groups()

                # Extract medicine name and quantity based on pattern
                if text_lower.startswith("-"):
                    # Pattern: -Napa 2
                    medicine_name = groups[0]
                    quantity = int(groups[1])
                elif groups[0].isdigit():
                    # Pattern: Used 2 Napa (quantity first)
                    quantity = int(groups[0])
                    medicine_name = groups[1]
                elif len(groups) >= 2 and groups[1]:
                    # Pattern: Used Napa 2
                    medicine_name = groups[0]
                    try:
                        quantity = int(groups[1])
                    except (ValueError, IndexError):
                        quantity = 1  # Default to 1 if "some" or no quantity
                else:
                    # Pattern: Took Napa / Used some Napa
                    medicine_name = groups[0]
                    quantity = 1  # Default quantity

                return ParsedCommand(
                    command_type="use",
                    medicine_name=medicine_name.strip().title(),
                    quantity=quantity,
                    confidence=1.0,
                )

        return None


class SearchCommandParser:
    """Parser for searching medicines."""

    # Regex patterns for search commands (in priority order)
    PATTERNS = [
        # ?Napa
        r"^\?\s*(\w+(?:\s+\w+)?)",
        # Do we have Napa?
        r"do\s+we\s+have\s+(\w+(?:\s+\w+)?)",
        # Check Napa / Search Napa
        r"(?:check|search|find|show)\s+(\w+(?:\s+\w+)?)",
        # Have we got Napa?
        r"have\s+(?:we\s+)?(?:got\s+)?(\w+(?:\s+\w+)?)",
    ]

    def parse(self, text: str) -> Optional[ParsedCommand]:
        """Parse search command.

        Args:
            text: Raw text to parse

        Returns:
            ParsedCommand if matched, None otherwise
        """
        text_lower = text.lower().strip()

        # Check if this looks like a search command
        if not (
            text_lower.startswith("?")
            or any(keyword in text_lower for keyword in ["have", "check", "search", "find", "show"])
        ):
            return None

        for pattern in self.PATTERNS:
            if match := re.search(pattern, text_lower, re.IGNORECASE):
                medicine_name = match.group(1)

                return ParsedCommand(
                    command_type="search",
                    medicine_name=medicine_name.strip().title(),
                    confidence=1.0,
                )

        return None


class ListCommandParser:
    """Parser for listing all medicines."""

    # Keywords that trigger list command
    LIST_KEYWORDS = [
        "?all",
        "list",
        "show all",
        "show everything",
        "list all",
        "list medicines",
        "show medicines",
        "what do we have",
        "inventory",
    ]

    def parse(self, text: str) -> Optional[ParsedCommand]:
        """Parse list command.

        Args:
            text: Raw text to parse

        Returns:
            ParsedCommand if matched, None otherwise
        """
        text_lower = text.lower().strip()

        # Check for exact or partial match with list keywords
        for keyword in self.LIST_KEYWORDS:
            if text_lower == keyword or text_lower.startswith(keyword):
                return ParsedCommand(
                    command_type="list",
                    confidence=1.0,
                )

        return None


class RoutineCommandParser:
    """Parser for routine/schedule commands."""

    # Patterns: "Take Napa at 8AM daily", "Remind me Sergel before meal"
    PATTERNS = [
        # "take Napa 1 tablet at 08:00 daily before meal"
        r"(?:take|remind(?:\s+me)?)\s+(\w+(?:\s+\w+)?)\s+(\d+)?\s*(?:tablet|cap|ml)?\s*(?:at\s+)?(\d{1,2}[:.]\d{2}(?:\s*(?:am|pm))?)?(?:\s+(\w+))?\s*(?:(before|after|with)\s*meal)?",
        # "remind Napa at 8AM and 8PM daily"
        r"(?:take|remind(?:\s+me)?)\s+(\w+(?:\s+\w+)?)\s+(?:at\s+)?(\d{1,2}[:.]\d{2}(?:\s*(?:am|pm))?)(?:\s+(?:and|,)\s+(\d{1,2}[:.]\d{2}(?:\s*(?:am|pm))?))?",
    ]

    # Time conversion helpers
    TIME_PATTERN = re.compile(r"(\d{1,2})[:.:](\d{2})\s*(am|pm)?", re.IGNORECASE)

    def parse(self, text: str) -> Optional[ParsedCommand]:
        """Parse routine commands."""
        text_lower = text.lower().strip()

        # Must contain routine-related keywords
        if not any(kw in text_lower for kw in ["take", "remind", "routine", "schedule"]):
            return None

        # Must also contain time-related indicators
        if not any(
            kw in text_lower
            for kw in ["daily", "weekly", "every", "at ", "am", "pm", "morning", "evening"]
        ):
            return None

        # Extract medicine name (first word after trigger keyword)
        name_match = re.search(
            r"(?:take|remind(?:\s+me)?|routine\s+(?:add\s+)?)\s+(\w+(?:\s+\w+)?)",
            text_lower,
        )
        if not name_match:
            return None

        medicine_name = name_match.group(1).strip().title()

        # Remove common non-medicine words
        for word in ["me", "to", "my", "the", "a"]:
            if medicine_name.lower() == word:
                return None

        # Extract times
        times = []
        for m in self.TIME_PATTERN.finditer(text_lower):
            hour, minute = int(m.group(1)), int(m.group(2))
            ampm = m.group(3)
            if ampm:
                if ampm.lower() == "pm" and hour != 12:
                    hour += 12
                elif ampm.lower() == "am" and hour == 12:
                    hour = 0
            times.append(f"{hour:02d}:{minute:02d}")

        # Handle word-based times
        if not times:
            if "morning" in text_lower:
                times.append("08:00")
            if "evening" in text_lower or "night" in text_lower:
                times.append("20:00")
            if "afternoon" in text_lower:
                times.append("14:00")

        if not times:
            times = ["08:00"]  # Default

        # Frequency
        frequency = "daily"
        if "weekly" in text_lower:
            frequency = "weekly"
        elif "every other day" in text_lower or "alternate" in text_lower:
            frequency = "every_other_day"

        # Meal relation
        meal_relation = None
        if "before meal" in text_lower or "before food" in text_lower:
            meal_relation = "before_meal"
        elif "after meal" in text_lower or "after food" in text_lower:
            meal_relation = "after_meal"
        elif "with meal" in text_lower or "with food" in text_lower:
            meal_relation = "with_meal"

        # Quantity
        qty_match = re.search(r"(\d+)\s*(?:tablet|tab|cap|ml|piece)", text_lower)
        quantity = int(qty_match.group(1)) if qty_match else 1

        return ParsedCommand(
            command_type="routine",
            medicine_name=medicine_name,
            quantity=quantity,
            schedule_times=times,
            frequency=frequency,
            meal_relation=meal_relation,
            confidence=0.9,
        )


class CostCommandParser:
    """Parser for cost-related commands."""

    # Patterns: "+Napa 10 cost 50tk", "cost Napa 50", "Napa cost 100 taka"
    COST_PATTERN = re.compile(
        r"(?:cost|price|paid)\s+(\w+(?:\s+\w+)?)\s+(\d+(?:\.\d+)?)\s*(?:tk|taka|bdt)?",
        re.IGNORECASE,
    )
    COST_SUFFIX_PATTERN = re.compile(
        r"(\w+(?:\s+\w+)?)\s+cost\s+(\d+(?:\.\d+)?)\s*(?:tk|taka|bdt)?",
        re.IGNORECASE,
    )

    def parse(self, text: str) -> Optional[ParsedCommand]:
        """Parse cost commands."""
        text_lower = text.lower().strip()

        if "cost" not in text_lower and "price" not in text_lower and "paid" not in text_lower:
            return None

        # Try "cost Napa 50tk"
        if match := self.COST_PATTERN.search(text_lower):
            return ParsedCommand(
                command_type="cost",
                medicine_name=match.group(1).strip().title(),
                cost=float(match.group(2)),
                confidence=1.0,
            )

        # Try "Napa cost 100 taka"
        if match := self.COST_SUFFIX_PATTERN.search(text_lower):
            return ParsedCommand(
                command_type="cost",
                medicine_name=match.group(1).strip().title(),
                cost=float(match.group(2)),
                confidence=1.0,
            )

        return None
