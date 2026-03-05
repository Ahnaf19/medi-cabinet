"""Unit tests for RoutineScheduler."""

from datetime import datetime
from datetime import time as dt_time
from unittest.mock import AsyncMock, MagicMock, patch

from src.database import Routine, RoutineLog
from src.scheduler import RoutineScheduler


def _make_routine(**kwargs):
    defaults = {
        "id": 1,
        "medicine_id": 1,
        "medicine_name": "Napa",
        "dosage_quantity": 1,
        "dosage_unit": "tablets",
        "frequency": "daily",
        "times_of_day": ["08:00", "20:00"],
        "days_of_week": None,
        "meal_relation": "after_meal",
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


class TestScheduleRoutine:
    def test_schedule_creates_daily_jobs(self):
        job_queue = MagicMock()
        job_queue.jobs.return_value = []
        scheduler = RoutineScheduler(job_queue, ":memory:")
        routine = _make_routine(times_of_day=["08:00", "20:00"])

        scheduler.schedule_routine(routine)

        assert job_queue.run_daily.call_count == 2
        calls = job_queue.run_daily.call_args_list
        assert calls[0][1]["name"] == "routine_1_08:00"
        assert calls[1][1]["name"] == "routine_1_20:00"
        assert calls[0][1]["time"] == dt_time(8, 0)
        assert calls[1][1]["time"] == dt_time(20, 0)

    def test_schedule_passes_correct_data(self):
        job_queue = MagicMock()
        job_queue.jobs.return_value = []
        scheduler = RoutineScheduler(job_queue, ":memory:")
        routine = _make_routine(times_of_day=["09:30"], meal_relation="before_meal")

        scheduler.schedule_routine(routine)

        data = job_queue.run_daily.call_args[1]["data"]
        assert data["routine_id"] == 1
        assert data["chat_id"] == 789012
        assert data["medicine_name"] == "Napa"
        assert data["meal_relation"] == "before_meal"

    def test_schedule_removes_existing_jobs_first(self):
        existing_job = MagicMock()
        existing_job.name = "routine_1_08:00"
        job_queue = MagicMock()
        job_queue.jobs.return_value = [existing_job]
        scheduler = RoutineScheduler(job_queue, ":memory:")

        scheduler.schedule_routine(_make_routine(times_of_day=["09:00"]))

        existing_job.schedule_removal.assert_called_once()

    def test_schedule_handles_invalid_time(self):
        job_queue = MagicMock()
        job_queue.jobs.return_value = []
        job_queue.run_daily.side_effect = ValueError("bad time")
        scheduler = RoutineScheduler(job_queue, ":memory:")

        # Should not raise
        scheduler.schedule_routine(_make_routine(times_of_day=["25:99"]))


class TestUnscheduleRoutine:
    def test_unschedule_removes_matching_jobs(self):
        job1 = MagicMock()
        job1.name = "routine_5_08:00"
        job2 = MagicMock()
        job2.name = "routine_5_20:00"
        job3 = MagicMock()
        job3.name = "routine_6_08:00"  # different routine
        job_queue = MagicMock()
        job_queue.jobs.return_value = [job1, job2, job3]

        scheduler = RoutineScheduler(job_queue, ":memory:")
        scheduler.unschedule_routine(5)

        job1.schedule_removal.assert_called_once()
        job2.schedule_removal.assert_called_once()
        job3.schedule_removal.assert_not_called()

    def test_unschedule_noop_when_no_jobs(self):
        job_queue = MagicMock()
        job_queue.jobs.return_value = []
        scheduler = RoutineScheduler(job_queue, ":memory:")
        scheduler.unschedule_routine(999)  # should not raise


class TestReminderCallback:
    async def test_sends_inline_keyboard(self):
        context = MagicMock()
        context.job = MagicMock()
        context.job.data = {
            "routine_id": 1,
            "chat_id": 789012,
            "medicine_name": "Napa",
            "dosage_quantity": 1,
            "dosage_unit": "tablets",
            "meal_relation": "after_meal",
            "scheduled_time": "08:00",
        }
        config = MagicMock()
        config.database_path = ":memory:"
        context.bot_data = {"config": config}
        context.bot = AsyncMock()

        with patch("src.scheduler.Database") as mock_db_cls:
            db = AsyncMock()
            mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db)
            mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            log_entry = RoutineLog(
                id=10,
                routine_id=1,
                scheduled_time=datetime.now(),
                actual_time=None,
                status="pending",
                group_chat_id=789012,
                created_at=datetime.now(),
            )

            with patch("src.scheduler.RoutineLogRepository") as mock_lr:
                mock_lr.return_value = AsyncMock(
                    mark_old_pending_as_missed=AsyncMock(return_value=0),
                    create_log=AsyncMock(return_value=log_entry),
                )

                await RoutineScheduler._reminder_callback(context)

        context.bot.send_message.assert_called_once()
        call_kwargs = context.bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == 789012
        assert "Napa" in call_kwargs["text"]
        assert "After Meal" in call_kwargs["text"]
        # Verify inline keyboard
        keyboard = call_kwargs["reply_markup"]
        buttons = keyboard.inline_keyboard[0]
        assert buttons[0].text == "Taken"
        assert buttons[1].text == "Skip"
        assert "routine_taken_10_1" in buttons[0].callback_data


class TestLoadAllRoutines:
    @patch("src.scheduler.Database")
    async def test_load_schedules_active_routines(self, mock_db_cls):
        db = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        routines = [
            _make_routine(id=1, times_of_day=["08:00"]),
            _make_routine(id=2, times_of_day=["09:00"]),
        ]

        with patch("src.scheduler.RoutineRepository") as mock_rr:
            mock_rr.return_value = AsyncMock(get_active_routines=AsyncMock(return_value=routines))

            job_queue = MagicMock()
            job_queue.jobs.return_value = []
            scheduler = RoutineScheduler(job_queue, ":memory:")
            count = await scheduler.load_all_routines()

        assert count == 2
        assert job_queue.run_daily.call_count == 2
