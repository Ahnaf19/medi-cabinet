"""Tests for command parsers."""

import pytest
from src.parsers import (
    CommandParser,
    AddCommandParser,
    UseCommandParser,
    SearchCommandParser,
    ListCommandParser,
)


class TestAddCommandParser:
    """Test add command parsing."""

    def test_simple_add_with_plus(self):
        """Test simple add command with + prefix."""
        parser = AddCommandParser()
        result = parser.parse("+Napa 10")

        assert result is not None
        assert result.command_type == "add"
        assert result.medicine_name == "Napa"
        assert result.quantity == 10
        assert result.unit == "tablets"

    def test_add_with_space_in_name(self):
        """Test add command with space in medicine name."""
        parser = AddCommandParser()
        result = parser.parse("+Napa Extra 20")

        assert result is not None
        assert result.medicine_name == "Napa Extra"
        assert result.quantity == 20

    def test_natural_language_bought(self):
        """Test natural language 'bought' command."""
        parser = AddCommandParser()
        result = parser.parse("Bought Napa Extra 10 tablets")

        assert result is not None
        assert result.medicine_name == "Napa Extra"
        assert result.quantity == 10
        assert result.unit == "tablets"

    def test_natural_language_got(self):
        """Test natural language 'got' command."""
        parser = AddCommandParser()
        result = parser.parse("Got paracetamol, 12")

        assert result is not None
        assert result.medicine_name == "Paracetamol"
        assert result.quantity == 12

    def test_quantity_first(self):
        """Test command with quantity first."""
        parser = AddCommandParser()
        result = parser.parse("10 Napa")

        assert result is not None
        assert result.medicine_name == "Napa"
        assert result.quantity == 10

    def test_without_quantity(self):
        """Test command without explicit quantity."""
        parser = AddCommandParser()
        result = parser.parse("Got paracetamol")

        assert result is not None
        assert result.medicine_name == "Paracetamol"
        assert result.quantity is None

    def test_with_unit(self):
        """Test command with different units."""
        parser = AddCommandParser()

        result = parser.parse("Bought Syrup 1 bottle")
        assert result.unit == "bottles"

        result = parser.parse("+Capsule 5 caps")
        assert result.unit == "capsules"

    def test_not_add_command(self):
        """Test that non-add commands return None."""
        parser = AddCommandParser()

        assert parser.parse("-Napa 2") is None
        assert parser.parse("?Napa") is None
        assert parser.parse("Hello world") is None


class TestUseCommandParser:
    """Test use command parsing."""

    def test_simple_use_with_minus(self):
        """Test simple use command with - prefix."""
        parser = UseCommandParser()
        result = parser.parse("-Napa 2")

        assert result is not None
        assert result.command_type == "use"
        assert result.medicine_name == "Napa"
        assert result.quantity == 2

    def test_natural_language_used(self):
        """Test natural language 'used' command."""
        parser = UseCommandParser()
        result = parser.parse("Used 2 Napa")

        assert result is not None
        assert result.medicine_name == "Napa"
        assert result.quantity == 2

    def test_natural_language_took(self):
        """Test natural language 'took' command."""
        parser = UseCommandParser()
        result = parser.parse("Took some paracetamol")

        assert result is not None
        assert result.medicine_name == "Paracetamol"
        assert result.quantity == 1  # "some" defaults to 1

    def test_used_medicine_quantity(self):
        """Test 'used Napa 2' format."""
        parser = UseCommandParser()
        result = parser.parse("Used Napa 2")

        assert result is not None
        assert result.medicine_name == "Napa"
        assert result.quantity == 2

    def test_without_quantity(self):
        """Test use command without explicit quantity."""
        parser = UseCommandParser()
        result = parser.parse("Took Napa")

        assert result is not None
        assert result.medicine_name == "Napa"
        assert result.quantity == 1  # Default to 1

    def test_with_space_in_name(self):
        """Test use command with space in medicine name."""
        parser = UseCommandParser()
        result = parser.parse("-Napa Extra 3")

        assert result is not None
        assert result.medicine_name == "Napa Extra"
        assert result.quantity == 3

    def test_not_use_command(self):
        """Test that non-use commands return None."""
        parser = UseCommandParser()

        assert parser.parse("+Napa 10") is None
        assert parser.parse("?Napa") is None
        assert parser.parse("Hello world") is None


class TestSearchCommandParser:
    """Test search command parsing."""

    def test_simple_search_with_question_mark(self):
        """Test simple search with ? prefix."""
        parser = SearchCommandParser()
        result = parser.parse("?Napa")

        assert result is not None
        assert result.command_type == "search"
        assert result.medicine_name == "Napa"

    def test_natural_language_have(self):
        """Test natural language 'have' question."""
        parser = SearchCommandParser()
        result = parser.parse("Do we have Napa?")

        assert result is not None
        assert result.medicine_name == "Napa"

    def test_natural_language_check(self):
        """Test natural language 'check' command."""
        parser = SearchCommandParser()
        result = parser.parse("Check Sergel")

        assert result is not None
        assert result.medicine_name == "Sergel"

    def test_with_space_in_name(self):
        """Test search with space in medicine name."""
        parser = SearchCommandParser()
        result = parser.parse("?Napa Extra")

        assert result is not None
        assert result.medicine_name == "Napa Extra"

    def test_natural_language_find(self):
        """Test natural language 'find' command."""
        parser = SearchCommandParser()
        result = parser.parse("Find paracetamol")

        assert result is not None
        assert result.medicine_name == "Paracetamol"

    def test_not_search_command(self):
        """Test that non-search commands return None."""
        parser = SearchCommandParser()

        assert parser.parse("+Napa 10") is None
        assert parser.parse("-Napa 2") is None
        assert parser.parse("Hello world") is None


class TestListCommandParser:
    """Test list command parsing."""

    def test_question_mark_all(self):
        """Test ?all command."""
        parser = ListCommandParser()
        result = parser.parse("?all")

        assert result is not None
        assert result.command_type == "list"

    def test_list_keyword(self):
        """Test 'list' command."""
        parser = ListCommandParser()
        result = parser.parse("list")

        assert result is not None
        assert result.command_type == "list"

    def test_list_medicines(self):
        """Test 'list medicines' command."""
        parser = ListCommandParser()
        result = parser.parse("list medicines")

        assert result is not None
        assert result.command_type == "list"

    def test_show_all(self):
        """Test 'show all' command."""
        parser = ListCommandParser()
        result = parser.parse("show all")

        assert result is not None
        assert result.command_type == "list"

    def test_inventory(self):
        """Test 'inventory' command."""
        parser = ListCommandParser()
        result = parser.parse("inventory")

        assert result is not None
        assert result.command_type == "list"

    def test_not_list_command(self):
        """Test that non-list commands return None."""
        parser = ListCommandParser()

        assert parser.parse("+Napa 10") is None
        assert parser.parse("?Napa") is None


class TestCommandParser:
    """Test main command parser."""

    def test_add_command_routing(self):
        """Test that add commands are routed correctly."""
        parser = CommandParser()

        result = parser.parse("+Napa 10")
        assert result.command_type == "add"

        result = parser.parse("Bought Napa 20")
        assert result.command_type == "add"

    def test_use_command_routing(self):
        """Test that use commands are routed correctly."""
        parser = CommandParser()

        result = parser.parse("-Napa 2")
        assert result.command_type == "use"

        result = parser.parse("Used 2 Napa")
        assert result.command_type == "use"

    def test_search_command_routing(self):
        """Test that search commands are routed correctly."""
        parser = CommandParser()

        result = parser.parse("?Napa")
        assert result.command_type == "search"

        result = parser.parse("Do we have Napa?")
        assert result.command_type == "search"

    def test_list_command_routing(self):
        """Test that list commands are routed correctly."""
        parser = CommandParser()

        result = parser.parse("?all")
        assert result.command_type == "list"

        result = parser.parse("list medicines")
        assert result.command_type == "list"

    def test_unknown_command(self):
        """Test unknown command handling."""
        parser = CommandParser()

        result = parser.parse("Hello world")
        assert result.command_type == "unknown"

        result = parser.parse("Random text")
        assert result.command_type == "unknown"

    def test_raw_text_preserved(self):
        """Test that raw text is preserved in ParsedCommand."""
        parser = CommandParser()

        text = "+Napa 10 tablets"
        result = parser.parse(text)
        assert result.raw_text == text


class TestParserEdgeCases:
    """Test edge cases and special scenarios."""

    def test_case_insensitivity(self):
        """Test that parsing is case-insensitive."""
        parser = CommandParser()

        result1 = parser.parse("+NAPA 10")
        result2 = parser.parse("+napa 10")
        result3 = parser.parse("+Napa 10")

        assert result1.medicine_name == result2.medicine_name == result3.medicine_name

    def test_extra_whitespace(self):
        """Test handling of extra whitespace."""
        parser = CommandParser()

        result = parser.parse("  +Napa   10  ")
        assert result.command_type == "add"
        assert result.medicine_name == "Napa"
        assert result.quantity == 10

    def test_comma_separator(self):
        """Test comma as separator."""
        parser = CommandParser()

        result = parser.parse("Got paracetamol, 12")
        assert result.command_type == "add"
        assert result.medicine_name == "Paracetamol"
        assert result.quantity == 12
