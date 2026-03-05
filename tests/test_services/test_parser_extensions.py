"""Tests for routine and cost command parsers."""

from src.parsers import RoutineCommandParser, CostCommandParser, CommandParser


class TestRoutineCommandParser:
    """Test routine command parsing."""

    def test_daily_with_time(self):
        parser = RoutineCommandParser()
        result = parser.parse("Take Napa at 08:00 daily")
        assert result is not None
        assert result.command_type == "routine"
        assert "Napa" in result.medicine_name
        assert result.schedule_times == ["08:00"]
        assert result.frequency == "daily"

    def test_with_am_pm(self):
        parser = RoutineCommandParser()
        result = parser.parse("Take Sergel at 8:00 AM daily")
        assert result is not None
        assert "Sergel" in result.medicine_name
        assert result.schedule_times == ["08:00"]

    def test_pm_conversion(self):
        parser = RoutineCommandParser()
        result = parser.parse("Take Napa at 2:00 PM daily")
        assert result is not None
        assert result.schedule_times == ["14:00"]

    def test_before_meal(self):
        parser = RoutineCommandParser()
        result = parser.parse("Take Sergel at 08:00 daily before meal")
        assert result is not None
        assert result.meal_relation == "before_meal"

    def test_after_meal(self):
        parser = RoutineCommandParser()
        result = parser.parse("Take Napa at 08:00 daily after meal")
        assert result is not None
        assert result.meal_relation == "after_meal"

    def test_with_meal(self):
        parser = RoutineCommandParser()
        result = parser.parse("Take Napa at 12:00 daily with food")
        assert result is not None
        assert result.meal_relation == "with_meal"

    def test_weekly_frequency(self):
        parser = RoutineCommandParser()
        result = parser.parse("Take VitaminD at 10:00 weekly")
        assert result is not None
        assert result.frequency == "weekly"

    def test_every_other_day(self):
        parser = RoutineCommandParser()
        result = parser.parse("Take Napa at 08:00 every other day")
        assert result is not None
        assert result.frequency == "every_other_day"

    def test_word_time_morning(self):
        parser = RoutineCommandParser()
        result = parser.parse("Remind me Napa daily morning")
        assert result is not None
        assert result.schedule_times == ["08:00"]

    def test_word_time_evening(self):
        parser = RoutineCommandParser()
        result = parser.parse("Remind me Sergel daily evening")
        assert result is not None
        assert result.schedule_times == ["20:00"]

    def test_quantity_with_unit(self):
        parser = RoutineCommandParser()
        result = parser.parse("Take Napa 2 tablets at 08:00 daily")
        assert result is not None
        assert result.quantity == 2

    def test_not_routine_command(self):
        parser = RoutineCommandParser()
        assert parser.parse("+Napa 10") is None
        assert parser.parse("?Napa") is None
        assert parser.parse("Hello world") is None

    def test_no_time_indicator(self):
        parser = RoutineCommandParser()
        # Must have time-related keyword
        assert parser.parse("Take Napa") is None

    def test_via_command_parser_routing(self):
        parser = CommandParser()
        result = parser.parse("Take Napa at 08:00 daily before meal")
        assert result.command_type == "routine"


class TestCostCommandParser:
    """Test cost command parsing."""

    def test_cost_prefix(self):
        parser = CostCommandParser()
        result = parser.parse("cost Napa 50")
        assert result is not None
        assert result.command_type == "cost"
        assert result.medicine_name == "Napa"
        assert result.cost == 50.0

    def test_cost_with_tk(self):
        parser = CostCommandParser()
        result = parser.parse("cost Napa 50tk")
        assert result is not None
        assert result.cost == 50.0

    def test_cost_with_taka(self):
        parser = CostCommandParser()
        result = parser.parse("cost Sergel 120 taka")
        assert result is not None
        assert result.medicine_name == "Sergel"
        assert result.cost == 120.0

    def test_cost_suffix_pattern(self):
        parser = CostCommandParser()
        result = parser.parse("Napa cost 100 taka")
        assert result is not None
        assert result.medicine_name == "Napa"
        assert result.cost == 100.0

    def test_price_keyword(self):
        parser = CostCommandParser()
        result = parser.parse("price Napa 75")
        assert result is not None
        assert result.cost == 75.0

    def test_paid_keyword(self):
        parser = CostCommandParser()
        result = parser.parse("paid Napa 200")
        assert result is not None
        assert result.cost == 200.0

    def test_decimal_cost(self):
        parser = CostCommandParser()
        result = parser.parse("cost Napa 99.50")
        assert result is not None
        assert result.cost == 99.50

    def test_not_cost_command(self):
        parser = CostCommandParser()
        assert parser.parse("+Napa 10") is None
        assert parser.parse("?Napa") is None

    def test_via_command_parser_routing(self):
        parser = CommandParser()
        result = parser.parse("cost Napa 50tk")
        assert result.command_type == "cost"
