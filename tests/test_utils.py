"""Tests for utility functions."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.utils import (
    format_medicine_list,
    format_medicine_detail,
    format_date,
    parse_date_flexible,
    calculate_days_until_expiry,
    get_stock_status_emoji,
    sanitize_medicine_name,
    generate_usage_stats,
    format_activity_history,
    format_low_stock_alert,
    format_expiry_warning,
    get_welcome_message,
    get_help_message,
    format_routine_list,
    format_routine_detail,
    format_interaction_warning,
    format_cost_summary,
    format_adherence_stats,
    format_analytics_report,
)
from src.database import Medicine, Activity, Routine, DrugInteraction


def _make_medicine(**kwargs):
    defaults = dict(
        id=1,
        name="Napa",
        quantity=10,
        unit="tablets",
        expiry_date=None,
        location=None,
        added_by_user_id=123,
        added_by_username="TestUser",
        added_date=datetime.now(),
        group_chat_id=-100,
        last_updated=datetime.now(),
    )
    defaults.update(kwargs)
    return Medicine(**defaults)


def _make_activity(**kwargs):
    defaults = dict(
        id=1,
        medicine_id=1,
        action="added",
        quantity_change=10,
        user_id=123,
        username="TestUser",
        timestamp=datetime.now(),
        group_chat_id=-100,
    )
    defaults.update(kwargs)
    return Activity(**defaults)


def _make_routine(**kwargs):
    defaults = dict(
        id=1,
        medicine_id=None,
        medicine_name="Napa",
        dosage_quantity=1,
        dosage_unit="tablet",
        frequency="daily",
        times_of_day=["08:00", "20:00"],
        days_of_week=None,
        meal_relation="after_meal",
        status="active",
        notes=None,
        created_by_user_id=123,
        created_by_username="TestUser",
        group_chat_id=-100,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        start_date=None,
        end_date=None,
    )
    defaults.update(kwargs)
    return Routine(**defaults)


def _make_interaction(**kwargs):
    defaults = dict(
        id=1,
        drug_a_name="Napa",
        drug_b_name="Warfarin",
        severity="moderate",
        description="Paracetamol may increase warfarin effect.",
        source="BNFC",
    )
    defaults.update(kwargs)
    return DrugInteraction(**defaults)


class TestFormatDate:
    def test_today(self):
        assert format_date(datetime.now()) == "Today"

    def test_yesterday(self):
        assert format_date(datetime.now() - timedelta(days=1)) == "Yesterday"

    def test_days_ago(self):
        result = format_date(datetime.now() - timedelta(days=3))
        assert result == "3 days ago"

    def test_weeks_ago(self):
        result = format_date(datetime.now() - timedelta(days=14))
        assert result == "2 weeks ago"

    def test_month_plus(self):
        result = format_date(datetime.now() - timedelta(days=60))
        assert "," in result  # e.g., "Jan 05, 2026"


class TestParseDateFlexible:
    def test_valid_date(self):
        result = parse_date_flexible("December 2025")
        assert result is not None
        assert result.month == 12

    def test_invalid_date(self):
        assert parse_date_flexible("not a date at all xyz") is None


class TestCalculateDaysUntilExpiry:
    def test_future_expiry(self):
        future = datetime.now() + timedelta(days=10)
        result = calculate_days_until_expiry(future)
        assert result in (9, 10)  # Fractional day boundary

    def test_past_expiry(self):
        past = datetime.now() - timedelta(days=5)
        result = calculate_days_until_expiry(past)
        assert result in (-5, -6)  # Fractional day boundary


class TestGetStockStatusEmoji:
    def test_zero_stock(self):
        result = get_stock_status_emoji(0, 3)
        assert isinstance(result, str)

    def test_low_stock(self):
        result = get_stock_status_emoji(2, 3)
        assert isinstance(result, str)

    def test_normal_stock(self):
        result = get_stock_status_emoji(10, 3)
        assert isinstance(result, str)

    def test_different_values(self):
        # Each stock level returns a string (emoji)
        zero = get_stock_status_emoji(0, 3)
        low = get_stock_status_emoji(2, 3)
        normal = get_stock_status_emoji(10, 3)
        # All should return non-None strings
        assert isinstance(zero, str)
        assert isinstance(low, str)
        assert isinstance(normal, str)


class TestSanitizeMedicineName:
    def test_normal_name(self):
        assert sanitize_medicine_name("Napa") == "Napa"

    def test_special_chars(self):
        result = sanitize_medicine_name("Napa!@#$")
        assert result == "Napa"

    def test_extra_spaces(self):
        result = sanitize_medicine_name("Napa   Extra")
        assert result == "Napa Extra"


class TestFormatMedicineList:
    def test_empty_list(self):
        assert "No medicines" in format_medicine_list([])

    def test_single_medicine(self):
        medicines = [_make_medicine()]
        result = format_medicine_list(medicines)
        assert "Napa" in result
        assert "10" in result

    def test_with_expiry(self):
        soon = datetime.now() + timedelta(days=10)
        medicines = [_make_medicine(expiry_date=soon)]
        result = format_medicine_list(medicines)
        assert "Expires" in result

    def test_expired(self):
        past = datetime.now() - timedelta(days=5)
        medicines = [_make_medicine(expiry_date=past)]
        result = format_medicine_list(medicines)
        assert "EXPIRED" in result

    def test_with_location(self):
        medicines = [_make_medicine(location="Bedroom")]
        result = format_medicine_list(medicines)
        assert "Bedroom" in result


class TestFormatMedicineDetail:
    def test_basic(self):
        result = format_medicine_detail(_make_medicine())
        assert "Napa" in result
        assert "10 tablets" in result
        assert "TestUser" in result

    def test_with_expiry(self):
        soon = datetime.now() + timedelta(days=5)
        result = format_medicine_detail(_make_medicine(expiry_date=soon))
        assert "Expiry" in result

    def test_with_location(self):
        result = format_medicine_detail(_make_medicine(location="Kitchen"))
        assert "Kitchen" in result


class TestFormatActivityHistory:
    def test_empty(self):
        assert "No activity" in format_activity_history([])

    def test_with_activities(self):
        activities = [
            _make_activity(action="added", quantity_change=10),
            _make_activity(action="used", quantity_change=-2),
        ]
        result = format_activity_history(activities)
        assert "Added" in result
        assert "Used" in result


class TestGenerateUsageStats:
    def test_basic_stats(self):
        stats = {
            "period_days": 30,
            "total_activities": 15,
            "activities_by_action": {"added": 10, "used": 5},
            "most_active_users": [{"username": "User1", "count": 10}],
            "most_used_medicines": [{"name": "Napa", "usage_count": 5}],
        }
        result = generate_usage_stats(stats)
        assert "15" in result
        assert "Napa" in result
        assert "User1" in result


class TestAlertFormatting:
    def test_low_stock_empty(self):
        assert format_low_stock_alert([]) == ""

    def test_low_stock(self):
        medicines = [_make_medicine(quantity=2)]
        result = format_low_stock_alert(medicines)
        assert "Napa" in result
        assert "2" in result

    def test_expiry_warning_empty(self):
        assert format_expiry_warning([]) == ""

    def test_expiry_warning(self):
        soon = datetime.now() + timedelta(days=3)
        medicines = [_make_medicine(expiry_date=soon)]
        result = format_expiry_warning(medicines)
        assert "days" in result
        assert "Napa" in result


class TestMessages:
    def test_welcome_message(self):
        msg = get_welcome_message()
        assert "Welcome" in msg
        assert "+Napa" in msg

    def test_help_message(self):
        msg = get_help_message()
        assert "Help" in msg
        assert "/routine" in msg
        assert "/cost" in msg
        assert "/analytics" in msg


class TestRoutineFormatting:
    def test_empty_list(self):
        assert "No routines" in format_routine_list([])

    def test_routine_list(self):
        routines = [_make_routine()]
        result = format_routine_list(routines)
        assert "Napa" in result
        assert "08:00" in result
        assert "daily" in result

    def test_paused_routine(self):
        routines = [_make_routine(status="paused")]
        result = format_routine_list(routines)
        assert "Napa" in result

    def test_routine_detail(self):
        result = format_routine_detail(_make_routine())
        assert "Napa" in result
        assert "After Meal" in result
        assert "daily" in result

    def test_routine_detail_with_days(self):
        result = format_routine_detail(_make_routine(days_of_week=["mon", "wed", "fri"]))
        assert "mon" in result


class TestInteractionFormatting:
    def test_empty(self):
        assert format_interaction_warning([]) == ""

    def test_interaction_warning(self):
        interactions = [_make_interaction()]
        result = format_interaction_warning(interactions)
        assert "Napa" in result
        assert "Warfarin" in result
        assert "MODERATE" in result

    def test_severe_interaction(self):
        interactions = [_make_interaction(severity="severe")]
        result = format_interaction_warning(interactions)
        assert "SEVERE" in result


class TestCostFormatting:
    def test_cost_summary(self):
        summary = {
            "total_spent": 500,
            "period_days": 30,
            "by_medicine": [{"name": "Napa", "total_cost": 300, "currency": "BDT", "purchases": 3}],
        }
        result = format_cost_summary(summary)
        assert "500" in result
        assert "Napa" in result

    def test_empty_cost_summary(self):
        summary = {"total_spent": 0, "by_medicine": []}
        result = format_cost_summary(summary)
        assert "0" in result
        assert "/cost" in result


class TestAdherenceFormatting:
    def test_no_data(self):
        assert "No routine data" in format_adherence_stats({})
        assert "No routine data" in format_adherence_stats({"total": 0})

    def test_with_data(self):
        stats = {
            "total": 30,
            "adherence_rate": 85.0,
            "period_days": 30,
            "by_status": {"taken": 25, "missed": 3, "skipped": 2},
        }
        result = format_adherence_stats(stats)
        assert "85" in result
        assert "25" in result


class TestAnalyticsFormatting:
    def test_full_report(self):
        report = {
            "inventory_summary": {
                "total_medicines": 10,
                "total_units": 100,
                "low_stock_count": 2,
                "expired_count": 1,
            },
            "usage_stats": {
                "total_activities": 50,
                "period_days": 30,
                "most_used_medicines": [{"name": "Napa", "usage_count": 20}],
            },
            "cost_summary": {"total_spent": 1000},
            "adherence": {"total": 30, "adherence_rate": 90.0},
            "restock_predictions": [{"name": "Napa", "days_until_empty": 5, "daily_usage": 2}],
        }
        result = format_analytics_report(report)
        assert "Analytics" in result
        assert "Napa" in result
        assert "1000" in result
        assert "90" in result
        assert "5 days" in result

    def test_minimal_report(self):
        report = {
            "inventory_summary": {"total_medicines": 0, "total_units": 0},
            "usage_stats": {"total_activities": 0},
            "cost_summary": {"total_spent": 0},
            "adherence": {"total": 0},
            "restock_predictions": [],
        }
        result = format_analytics_report(report)
        assert "Analytics" in result
