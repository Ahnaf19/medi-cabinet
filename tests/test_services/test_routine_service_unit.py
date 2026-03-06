"""Unit tests for RoutineService orchestration logic."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.database import Routine, RoutineData, RoutineLog
from src.services.routine_service import RoutineService


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


class TestRoutineServiceCreate:
    @patch("src.services.routine_service.Database")
    async def test_create_links_to_medicine(self, mock_db_cls):
        db = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        routine = _make_routine(medicine_id=5)
        medicine = MagicMock(id=5)

        with (
            patch("src.services.routine_service.RoutineRepository") as mock_rr,
            patch("src.services.routine_service.MedicineRepository") as mock_mr,
        ):
            mock_mr.return_value = AsyncMock(find_by_exact_name=AsyncMock(return_value=medicine))
            mock_rr.return_value = AsyncMock(create=AsyncMock(return_value=routine))

            scheduler = MagicMock()
            svc = RoutineService(":memory:", scheduler)
            result = await svc.create_routine(
                RoutineData(
                    medicine_name="Napa",
                    created_by_user_id=123456,
                    created_by_username="TestUser",
                    group_chat_id=789012,
                )
            )

        assert result.id == 1
        scheduler.schedule_routine.assert_called_once_with(routine)

    @patch("src.services.routine_service.Database")
    async def test_create_without_scheduler(self, mock_db_cls):
        db = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        routine = _make_routine()

        with (
            patch("src.services.routine_service.RoutineRepository") as mock_rr,
            patch("src.services.routine_service.MedicineRepository") as mock_mr,
        ):
            mock_mr.return_value = AsyncMock(find_by_exact_name=AsyncMock(return_value=None))
            mock_rr.return_value = AsyncMock(create=AsyncMock(return_value=routine))

            svc = RoutineService(":memory:", scheduler=None)
            result = await svc.create_routine(
                RoutineData(
                    medicine_name="Napa",
                    created_by_user_id=123456,
                    created_by_username="TestUser",
                    group_chat_id=789012,
                )
            )

        assert result.medicine_name == "Napa"


class TestRoutineServicePauseResume:
    @patch("src.services.routine_service.Database")
    async def test_pause_calls_scheduler(self, mock_db_cls):
        db = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        routine = _make_routine(status="paused")

        with patch("src.services.routine_service.RoutineRepository") as mock_rr:
            mock_rr.return_value = AsyncMock(update_status=AsyncMock(return_value=routine))

            scheduler = MagicMock()
            svc = RoutineService(":memory:", scheduler)
            result = await svc.pause_routine(1)

        assert result.status == "paused"
        scheduler.unschedule_routine.assert_called_once_with(1)

    @patch("src.services.routine_service.Database")
    async def test_resume_reschedules(self, mock_db_cls):
        db = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        routine = _make_routine(status="active")

        with patch("src.services.routine_service.RoutineRepository") as mock_rr:
            mock_rr.return_value = AsyncMock(update_status=AsyncMock(return_value=routine))

            scheduler = MagicMock()
            svc = RoutineService(":memory:", scheduler)
            result = await svc.resume_routine(1)

        assert result.status == "active"
        scheduler.schedule_routine.assert_called_once_with(routine)


class TestRoutineServiceMarkTaken:
    @patch("src.services.routine_service.Database")
    async def test_mark_taken_deducts_stock(self, mock_db_cls):
        db = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        routine = _make_routine(medicine_id=5, dosage_quantity=2)
        log = _make_routine_log(status="taken")

        with (
            patch("src.services.routine_service.RoutineLogRepository") as mock_lr,
            patch("src.services.routine_service.RoutineRepository") as mock_rr,
            patch("src.services.routine_service.MedicineRepository") as mock_mr,
        ):
            mock_lr.return_value = AsyncMock(mark_taken=AsyncMock(return_value=log))
            mock_rr.return_value = AsyncMock(get_by_id=AsyncMock(return_value=routine))
            mock_mr_inst = AsyncMock()
            mock_mr.return_value = mock_mr_inst

            svc = RoutineService(":memory:")
            result = await svc.mark_taken(1, 1)

        assert result.status == "taken"
        mock_mr_inst.update_quantity.assert_called_once_with(5, -2, 789012)

    @patch("src.services.routine_service.Database")
    async def test_mark_taken_no_medicine_id(self, mock_db_cls):
        db = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        routine = _make_routine(medicine_id=None)
        log = _make_routine_log(status="taken")

        with (
            patch("src.services.routine_service.RoutineLogRepository") as mock_lr,
            patch("src.services.routine_service.RoutineRepository") as mock_rr,
            patch("src.services.routine_service.MedicineRepository") as mock_mr,
        ):
            mock_lr.return_value = AsyncMock(mark_taken=AsyncMock(return_value=log))
            mock_rr.return_value = AsyncMock(get_by_id=AsyncMock(return_value=routine))
            mock_mr_inst = AsyncMock()
            mock_mr.return_value = mock_mr_inst

            svc = RoutineService(":memory:")
            await svc.mark_taken(1, 1)

        mock_mr_inst.update_quantity.assert_not_called()


class TestRoutineServiceDelete:
    @patch("src.services.routine_service.Database")
    async def test_delete_unschedules(self, mock_db_cls):
        db = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.routine_service.RoutineRepository") as mock_rr:
            mock_rr.return_value = AsyncMock(delete=AsyncMock(return_value=True))

            scheduler = MagicMock()
            svc = RoutineService(":memory:", scheduler)
            result = await svc.delete_routine(1)

        assert result is True
        scheduler.unschedule_routine.assert_called_once_with(1)
