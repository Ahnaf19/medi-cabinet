"""Tests for command handlers."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.commands import (
    handle_add_cost,
    handle_add_medicine,
    handle_analytics,
    handle_check_interactions,
    handle_cost_summary,
    handle_delete_medicine,
    handle_error,
    handle_help,
    handle_list_all,
    handle_message,
    handle_photo,
    handle_routine,
    handle_routine_callback,
    handle_search_medicine,
    handle_start,
    handle_stats,
    handle_use_medicine,
    scheduled_expiry_check,
)
from src.database import (
    DrugInteraction,
    InsufficientStockError,
    Medicine,
    MedicineData,
    Routine,
    RoutineLog,
)
from src.parsers import ParsedCommand

# --- Helpers ---


def _make_medicine(**kwargs):
    """Create a Medicine entity with defaults."""
    defaults = {
        "id": 1,
        "name": "Napa",
        "quantity": 10,
        "unit": "tablets",
        "expiry_date": None,
        "location": None,
        "added_by_user_id": 123456,
        "added_by_username": "TestUser",
        "added_date": datetime.now(),
        "group_chat_id": 789012,
        "last_updated": datetime.now(),
    }
    defaults.update(kwargs)
    return Medicine(**defaults)


def _make_routine(**kwargs):
    defaults = {
        "id": 1,
        "medicine_id": 1,
        "medicine_name": "Napa",
        "dosage_quantity": 1,
        "dosage_unit": "tablets",
        "frequency": "daily",
        "times_of_day": ["08:00"],
        "days_of_week": None,
        "meal_relation": None,
        "status": "active",
        "notes": None,
        "created_by_user_id": 123456,
        "created_by_username": "TestUser",
        "group_chat_id": 789012,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "start_date": None,
        "end_date": None,
    }
    defaults.update(kwargs)
    return Routine(**defaults)


def _make_routine_log(**kwargs):
    defaults = {
        "id": 1,
        "routine_id": 1,
        "scheduled_time": datetime.now(),
        "actual_time": None,
        "status": "pending",
        "group_chat_id": 789012,
        "created_at": datetime.now(),
    }
    defaults.update(kwargs)
    return RoutineLog(**defaults)


def _make_interaction(**kwargs):
    defaults = {
        "id": 1,
        "drug_a_name": "Aspirin",
        "drug_b_name": "Warfarin",
        "severity": "severe",
        "description": "Increased bleeding risk",
        "source": "BNF",
    }
    defaults.update(kwargs)
    return DrugInteraction(**defaults)


# --- /start and /help ---


class TestHandleStart:
    async def test_sends_welcome_message(self, mock_update, mock_context):
        await handle_start(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        text = mock_update.message.reply_text.call_args[0][0]
        assert "Medi-Cabinet" in text


class TestHandleHelp:
    async def test_sends_help_message(self, mock_update, mock_context):
        await handle_help(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        text = mock_update.message.reply_text.call_args[0][0]
        assert "/help" in text or "Help" in text


# --- Message router ---


class TestHandleMessage:
    async def test_returns_on_no_text(self, mock_update, mock_context):
        mock_update.message = None
        await handle_message(mock_update, mock_context)
        # No exception = pass

    async def test_routes_add_command(self, mock_update, mock_context):
        mock_update.message.text = "+Napa 10"
        with patch("src.commands.handle_add_medicine", new_callable=AsyncMock) as mock_add:
            await handle_message(mock_update, mock_context)
            mock_add.assert_called_once()

    async def test_routes_use_command(self, mock_update, mock_context):
        mock_update.message.text = "-Napa 2"
        with patch("src.commands.handle_use_medicine", new_callable=AsyncMock) as mock_use:
            await handle_message(mock_update, mock_context)
            mock_use.assert_called_once()

    async def test_routes_search_command(self, mock_update, mock_context):
        mock_update.message.text = "?Napa"
        with patch("src.commands.handle_search_medicine", new_callable=AsyncMock) as mock_search:
            await handle_message(mock_update, mock_context)
            mock_search.assert_called_once()

    async def test_routes_list_command(self, mock_update, mock_context):
        mock_update.message.text = "?all"
        with patch("src.commands.handle_list_all", new_callable=AsyncMock) as mock_list:
            await handle_message(mock_update, mock_context)
            mock_list.assert_called_once()

    async def test_unknown_sends_help_nudge(self, mock_update, mock_context):
        mock_update.message.text = "xyzzy"
        await handle_message(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        text = mock_update.message.reply_text.call_args[0][0]
        assert "didn't understand" in text


# --- Add medicine ---


class TestHandleAddMedicine:
    def _parsed(self, name="Napa", quantity=10, unit="tablets"):
        return ParsedCommand(
            command_type="add",
            medicine_name=name,
            quantity=quantity,
            unit=unit,
        )

    async def test_no_name_asks_for_name(self, mock_update, mock_context, test_config):
        parsed = ParsedCommand(command_type="add", medicine_name=None)
        await handle_add_medicine(mock_update, mock_context, parsed, test_config)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "specify" in text.lower()

    async def test_no_quantity_asks_for_quantity(self, mock_update, mock_context, test_config):
        parsed = ParsedCommand(command_type="add", medicine_name="Napa", quantity=None)
        await handle_add_medicine(mock_update, mock_context, parsed, test_config)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "Napa" in text

    @patch("src.commands.Database")
    async def test_happy_path(self, mock_db_cls, mock_update, mock_context, test_config):
        medicine = _make_medicine(quantity=10)
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.ActivityLogRepository") as mock_activity_cls,
        ):
            mock_repo = AsyncMock()
            mock_repo.add_medicine.return_value = medicine
            mock_repo_cls.return_value = mock_repo

            mock_activity = AsyncMock()
            mock_activity_cls.return_value = mock_activity

            await handle_add_medicine(mock_update, mock_context, self._parsed(), test_config)

        text = mock_update.message.reply_text.call_args_list[0][0][0]
        assert "Added" in text
        assert "Napa" in text

    @patch("src.commands.Database")
    async def test_low_stock_note(self, mock_db_cls, mock_update, mock_context, test_config):
        medicine = _make_medicine(quantity=2)
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.ActivityLogRepository") as mock_activity_cls,
        ):
            mock_repo_cls.return_value = AsyncMock(add_medicine=AsyncMock(return_value=medicine))
            mock_activity_cls.return_value = AsyncMock()

            await handle_add_medicine(
                mock_update, mock_context, self._parsed(quantity=1), test_config
            )

        text = mock_update.message.reply_text.call_args_list[0][0][0]
        assert "low stock" in text.lower() or "Still low" in text


# --- Use medicine ---


class TestHandleUseMedicine:
    def _parsed(self, name="Napa", quantity=2, unit="tablets"):
        return ParsedCommand(
            command_type="use",
            medicine_name=name,
            quantity=quantity,
            unit=unit,
        )

    async def test_no_name_asks(self, mock_update, mock_context, test_config):
        parsed = ParsedCommand(command_type="use", medicine_name=None)
        await handle_use_medicine(mock_update, mock_context, parsed, test_config)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "specify" in text.lower()

    async def test_no_quantity_asks(self, mock_update, mock_context, test_config):
        parsed = ParsedCommand(command_type="use", medicine_name="Napa", quantity=None)
        await handle_use_medicine(mock_update, mock_context, parsed, test_config)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "Napa" in text

    @patch("src.commands.Database")
    async def test_not_found(self, mock_db_cls, mock_update, mock_context, test_config):
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.ActivityLogRepository"),
        ):
            mock_repo_cls.return_value = AsyncMock(find_by_name_fuzzy=AsyncMock(return_value=[]))

            await handle_use_medicine(mock_update, mock_context, self._parsed(), test_config)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "not found" in text.lower()

    @patch("src.commands.Database")
    async def test_happy_path(self, mock_db_cls, mock_update, mock_context, test_config):
        medicine = _make_medicine(quantity=10)
        updated = _make_medicine(quantity=8)
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.ActivityLogRepository") as mock_activity_cls,
        ):
            mock_repo = AsyncMock()
            mock_repo.find_by_name_fuzzy.return_value = [(medicine, 100)]
            mock_repo.update_quantity.return_value = updated
            mock_repo_cls.return_value = mock_repo
            mock_activity_cls.return_value = AsyncMock()

            await handle_use_medicine(mock_update, mock_context, self._parsed(), test_config)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "Used" in text
        assert "8" in text

    @patch("src.commands.Database")
    async def test_insufficient_stock(self, mock_db_cls, mock_update, mock_context, test_config):
        medicine = _make_medicine(quantity=1)
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.ActivityLogRepository"),
        ):
            mock_repo = AsyncMock()
            mock_repo.find_by_name_fuzzy.return_value = [(medicine, 100)]
            mock_repo.update_quantity.side_effect = InsufficientStockError(available=1, requested=5)
            mock_repo_cls.return_value = mock_repo

            await handle_use_medicine(
                mock_update,
                mock_context,
                self._parsed(quantity=5),
                test_config,
            )

        text = mock_update.message.reply_text.call_args[0][0]
        assert "Insufficient" in text

    @patch("src.commands.Database")
    async def test_multiple_fuzzy_matches(
        self, mock_db_cls, mock_update, mock_context, test_config
    ):
        m1 = _make_medicine(name="Napa", id=1)
        m2 = _make_medicine(name="Napa Extra", id=2)
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.ActivityLogRepository"),
        ):
            mock_repo_cls.return_value = AsyncMock(
                find_by_name_fuzzy=AsyncMock(return_value=[(m1, 85), (m2, 82)])
            )

            await handle_use_medicine(
                mock_update,
                mock_context,
                self._parsed(),
                test_config,
            )

        text = mock_update.message.reply_text.call_args[0][0]
        assert "multiple" in text.lower() or "Found multiple" in text


# --- Search ---


class TestHandleSearchMedicine:
    def _parsed(self, name="Napa"):
        return ParsedCommand(command_type="search", medicine_name=name)

    async def test_no_name_asks(self, mock_update, mock_context, test_config):
        parsed = ParsedCommand(command_type="search", medicine_name=None)
        await handle_search_medicine(mock_update, mock_context, parsed, test_config)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "specify" in text.lower()

    @patch("src.commands.Database")
    async def test_not_found(self, mock_db_cls, mock_update, mock_context, test_config):
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.ActivityLogRepository"),
        ):
            mock_repo_cls.return_value = AsyncMock(find_by_name_fuzzy=AsyncMock(return_value=[]))

            await handle_search_medicine(mock_update, mock_context, self._parsed(), test_config)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "No medicine found" in text

    @patch("src.commands.Database")
    async def test_single_match(self, mock_db_cls, mock_update, mock_context, test_config):
        medicine = _make_medicine()
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.ActivityLogRepository") as mock_activity_cls,
        ):
            mock_repo_cls.return_value = AsyncMock(
                find_by_name_fuzzy=AsyncMock(return_value=[(medicine, 100)])
            )
            mock_activity_cls.return_value = AsyncMock()

            await handle_search_medicine(mock_update, mock_context, self._parsed(), test_config)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "Found" in text
        assert "Napa" in text

    @patch("src.commands.Database")
    async def test_multiple_matches(self, mock_db_cls, mock_update, mock_context, test_config):
        m1 = _make_medicine(name="Napa", id=1)
        m2 = _make_medicine(name="Napa Extra", id=2)
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.ActivityLogRepository") as mock_activity_cls,
        ):
            mock_repo_cls.return_value = AsyncMock(
                find_by_name_fuzzy=AsyncMock(return_value=[(m1, 100), (m2, 85)])
            )
            mock_activity_cls.return_value = AsyncMock()

            await handle_search_medicine(mock_update, mock_context, self._parsed(), test_config)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "2" in text


# --- List all ---


class TestHandleListAll:
    @patch("src.commands.Database")
    async def test_empty_cabinet(self, mock_db_cls, mock_update, mock_context, test_config):
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.commands.MedicineRepository") as mock_repo_cls:
            mock_repo_cls.return_value = AsyncMock(get_all=AsyncMock(return_value=[]))

            await handle_list_all(mock_update, mock_context, test_config)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "empty" in text.lower()

    @patch("src.commands.Database")
    async def test_with_medicines(self, mock_db_cls, mock_update, mock_context, test_config):
        medicines = [
            _make_medicine(name="Napa", quantity=10, id=1),
            _make_medicine(name="Sergel", quantity=5, id=2),
        ]
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.commands.MedicineRepository") as mock_repo_cls:
            mock_repo_cls.return_value = AsyncMock(get_all=AsyncMock(return_value=medicines))

            await handle_list_all(mock_update, mock_context, test_config)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "Medicine Cabinet" in text
        assert "Napa" in text
        assert "Sergel" in text

    @patch("src.commands.Database")
    async def test_low_stock_appended(self, mock_db_cls, mock_update, mock_context, test_config):
        medicines = [
            _make_medicine(name="Napa", quantity=1, id=1),
        ]
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.commands.MedicineRepository") as mock_repo_cls:
            mock_repo_cls.return_value = AsyncMock(get_all=AsyncMock(return_value=medicines))

            await handle_list_all(mock_update, mock_context, test_config)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "Low Stock" in text


# --- Delete ---


class TestHandleDeleteMedicine:
    async def test_non_admin_rejected(self, mock_update, mock_context):
        mock_update.effective_user.id = 999999  # not in admin list
        await handle_delete_medicine(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "admin" in text.lower()

    async def test_no_args_shows_usage(self, mock_update, mock_context):
        mock_context.args = []
        await handle_delete_medicine(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "specify" in text.lower()

    @patch("src.commands.Database")
    async def test_not_found(self, mock_db_cls, mock_update, mock_context):
        mock_context.args = ["Napa"]
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.ActivityLogRepository"),
        ):
            mock_repo_cls.return_value = AsyncMock(find_by_name_fuzzy=AsyncMock(return_value=[]))

            await handle_delete_medicine(mock_update, mock_context)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "not found" in text.lower()

    @patch("src.commands.Database")
    async def test_happy_path(self, mock_db_cls, mock_update, mock_context):
        mock_context.args = ["Napa"]
        medicine = _make_medicine()
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.ActivityLogRepository") as mock_activity_cls,
        ):
            mock_repo = AsyncMock()
            mock_repo.find_by_name_fuzzy.return_value = [(medicine, 100)]
            mock_repo.delete_medicine.return_value = True
            mock_repo_cls.return_value = mock_repo
            mock_activity_cls.return_value = AsyncMock()

            await handle_delete_medicine(mock_update, mock_context)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "Deleted" in text


# --- Stats ---


class TestHandleStats:
    @patch("src.commands.Database")
    async def test_returns_stats(self, mock_db_cls, mock_update, mock_context):
        stats = {
            "total_activities": 5,
            "activities_by_action": {"added": 3, "used": 2},
            "most_active_users": [],
            "most_used_medicines": [],
            "period_days": 30,
        }
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.commands.ActivityLogRepository") as mock_repo_cls:
            mock_repo_cls.return_value = AsyncMock(get_stats=AsyncMock(return_value=stats))

            await handle_stats(mock_update, mock_context)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "Statistics" in text or "5" in text


# --- Error handler ---


class TestHandleError:
    async def test_logs_and_replies(self, mock_update, mock_context):
        mock_context.error = Exception("test error")
        await handle_error(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_called_once()
        text = mock_update.effective_message.reply_text.call_args[0][0]
        assert "wrong" in text.lower()

    async def test_no_update(self, mock_context):
        mock_context.error = Exception("test error")
        await handle_error(None, mock_context)  # should not raise


# --- Routine handler ---


class TestHandleRoutine:
    async def test_no_args_shows_help(self, mock_update, mock_context):
        mock_context.args = []
        await handle_routine(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "Routine Commands" in text

    async def test_unknown_subcommand(self, mock_update, mock_context):
        mock_context.args = ["foobar"]
        await handle_routine(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "Unknown" in text

    @patch("src.commands._handle_routine_list", new_callable=AsyncMock)
    async def test_list_routes(self, mock_list, mock_update, mock_context):
        mock_context.args = ["list"]
        await handle_routine(mock_update, mock_context)
        mock_list.assert_called_once()

    async def test_pause_without_id(self, mock_update, mock_context):
        mock_context.args = ["pause"]
        await handle_routine(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "routine ID" in text.lower() or "id" in text.lower()

    @patch("src.commands._handle_routine_action", new_callable=AsyncMock)
    async def test_delete_with_id(self, mock_action, mock_update, mock_context):
        mock_context.args = ["delete", "5"]
        await handle_routine(mock_update, mock_context)
        mock_action.assert_called_once()
        # Verify routine_id=5 passed
        assert mock_action.call_args[0][4] == 5


# --- Routine callback ---


class TestHandleRoutineCallback:
    @patch("src.services.routine_service.RoutineService")
    async def test_taken_deducts_stock(self, mock_svc_cls, mock_update, mock_context):
        query = AsyncMock()
        query.data = "routine_taken_10_5"
        query.message = MagicMock()
        query.message.text = "Reminder text"
        mock_update.callback_query = query
        mock_update.effective_user.first_name = "TestUser"

        mock_svc = AsyncMock()
        mock_svc.mark_taken.return_value = _make_routine_log(status="taken")
        mock_svc_cls.return_value = mock_svc

        await handle_routine_callback(mock_update, mock_context)
        query.answer.assert_called_once()
        mock_svc.mark_taken.assert_called_once_with(10, 5)

    @patch("src.services.routine_service.RoutineService")
    async def test_skip_no_deduction(self, mock_svc_cls, mock_update, mock_context):
        query = AsyncMock()
        query.data = "routine_skip_10_5"
        query.message = MagicMock()
        query.message.text = "Reminder text"
        mock_update.callback_query = query

        mock_svc = AsyncMock()
        mock_svc_cls.return_value = mock_svc

        await handle_routine_callback(mock_update, mock_context)
        mock_svc.mark_skipped.assert_called_once_with(10)

    async def test_invalid_callback_data(self, mock_update, mock_context):
        query = AsyncMock()
        query.data = "bad"
        mock_update.callback_query = query
        await handle_routine_callback(mock_update, mock_context)
        query.answer.assert_called_once()


# --- Interactions ---


class TestHandleCheckInteractions:
    async def test_no_args_shows_help(self, mock_update, mock_context):
        mock_context.args = []
        await handle_check_interactions(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "interactions" in text.lower()

    @patch("src.services.interaction_service.InteractionService")
    async def test_no_interactions_found(self, mock_svc_cls, mock_update, mock_context):
        mock_context.args = ["Napa"]
        mock_svc = AsyncMock()
        mock_svc.check_against_cabinet.return_value = []
        mock_svc_cls.return_value = mock_svc

        await handle_check_interactions(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "No known interactions" in text

    @patch("src.services.interaction_service.InteractionService")
    async def test_interactions_found(self, mock_svc_cls, mock_update, mock_context):
        mock_context.args = ["Aspirin"]
        interaction = _make_interaction()
        mock_svc = AsyncMock()
        mock_svc.check_against_cabinet.return_value = [interaction]
        mock_svc_cls.return_value = mock_svc

        await handle_check_interactions(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "Interaction Warning" in text or "Aspirin" in text


# --- Cost ---


class TestHandleAddCost:
    async def test_no_args_shows_help(self, mock_update, mock_context):
        mock_context.args = []
        await handle_add_cost(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "cost" in text.lower()

    async def test_bad_amount_format(self, mock_update, mock_context):
        mock_context.args = ["Napa", "abc"]
        await handle_add_cost(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "Invalid" in text

    @patch("src.commands.Database")
    async def test_happy_path(self, mock_db_cls, mock_update, mock_context):
        medicine = _make_medicine()
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.CostRepository") as mock_cost_cls,
        ):
            mock_repo_cls.return_value = AsyncMock(
                find_by_name_fuzzy=AsyncMock(return_value=[(medicine, 100)])
            )
            mock_cost_cls.return_value = AsyncMock()
            mock_context.args = ["Napa", "50"]

            await handle_add_cost(mock_update, mock_context)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "Cost recorded" in text


# --- Cost summary ---


class TestHandleCostSummary:
    @patch("src.commands.Database")
    async def test_returns_summary(self, mock_db_cls, mock_update, mock_context):
        summary = {
            "total_spent": 150.0,
            "by_medicine": [],
            "period_days": 30,
        }
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.commands.CostRepository") as mock_cost_cls:
            mock_cost_cls.return_value = AsyncMock(get_cost_summary=AsyncMock(return_value=summary))

            await handle_cost_summary(mock_update, mock_context)

        text = mock_update.message.reply_text.call_args[0][0]
        assert "Cost Summary" in text


# --- Photo handler ---


class TestHandlePhoto:
    async def test_no_llm_configured(self, mock_update, mock_context):
        mock_context.bot_data["llm_provider"] = None
        await handle_photo(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "LLM provider" in text or "vision" in text.lower()

    @patch("src.commands.Database")
    @patch("src.services.image_service.ImageService")
    async def test_happy_path_with_mock_vision(
        self, mock_img_cls, mock_db_cls, mock_update, mock_context
    ):
        # Set up LLM provider mock
        provider = MagicMock()
        provider.supports_vision = True
        mock_context.bot_data["llm_provider"] = provider

        # Photo mock
        photo = MagicMock()
        photo.file_id = "file123"
        mock_update.message.photo = [photo]
        file_mock = AsyncMock()
        file_mock.download_as_bytearray.return_value = bytearray(b"fake_image")
        mock_context.bot.get_file.return_value = file_mock

        # ImageService returns medicines
        medicine_data = MedicineData(
            name="Napa",
            quantity=10,
            unit="tablets",
            expiry_date=None,
            location=None,
            added_by_user_id=123456,
            added_by_username="TestUser",
            group_chat_id=789012,
        )
        mock_svc = AsyncMock()
        mock_svc.extract_from_photo.return_value = [medicine_data]
        mock_img_cls.return_value = mock_svc

        # DB mock
        medicine = _make_medicine()
        db_instance = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.commands.MedicineRepository") as mock_repo_cls,
            patch("src.commands.ActivityLogRepository") as mock_activity_cls,
        ):
            mock_repo_cls.return_value = AsyncMock(add_medicine=AsyncMock(return_value=medicine))
            mock_activity_cls.return_value = AsyncMock()

            await handle_photo(mock_update, mock_context)

        # Should have sent "Analyzing..." then the result
        calls = mock_update.message.reply_text.call_args_list
        assert any("Analyzing" in str(c) for c in calls)
        assert any("Found" in str(c) or "added" in str(c) for c in calls)


# --- Analytics ---


class TestHandleAnalytics:
    @patch("src.services.analytics_service.AnalyticsService")
    async def test_returns_report(self, mock_svc_cls, mock_update, mock_context):
        report = {
            "usage_stats": {"total_activities": 0, "period_days": 30},
            "inventory_summary": {
                "total_medicines": 3,
                "total_units": 25,
                "low_stock_count": 1,
                "expired_count": 0,
            },
            "cost_summary": {"total_spent": 0},
            "adherence": {},
            "restock_predictions": [],
            "period_days": 30,
        }
        mock_svc = AsyncMock()
        mock_svc.get_full_report.return_value = report
        mock_svc_cls.return_value = mock_svc

        await handle_analytics(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "Analytics" in text


# --- Scheduled expiry check ---


class TestScheduledExpiryCheck:
    @patch("src.commands.Database")
    async def test_sends_alerts_to_groups(self, mock_db_cls, mock_context):
        from datetime import timedelta

        expiring_medicine = _make_medicine(expiry_date=datetime.now() + timedelta(days=5))

        db_instance = AsyncMock()
        db_instance.fetch_all = AsyncMock(return_value=[{"group_chat_id": 789012}])
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db_instance)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.commands.MedicineRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_expiring_soon.return_value = [expiring_medicine]
            mock_repo.get_low_stock.return_value = []
            mock_repo_cls.return_value = mock_repo

            await scheduled_expiry_check(mock_context)

        mock_context.bot.send_message.assert_called()
        call_kwargs = mock_context.bot.send_message.call_args
        assert call_kwargs[1]["chat_id"] == 789012 or call_kwargs[0][0] == 789012
