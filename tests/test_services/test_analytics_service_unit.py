"""Unit tests for AnalyticsService."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from src.database import Medicine
from src.services.analytics_service import AnalyticsService


def _make_medicine(**kwargs):
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


class TestAnalyticsServiceGetFullReport:
    @patch("src.services.analytics_service.Database")
    async def test_get_full_report_structure(self, mock_db_cls):
        db = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        medicines = [_make_medicine(quantity=10), _make_medicine(id=2, name="Sergel", quantity=2)]
        stats = {
            "total_activities": 5,
            "activities_by_action": {"added": 3, "used": 2},
            "most_active_users": [],
            "most_used_medicines": [],
            "period_days": 30,
        }

        with (
            patch("src.services.analytics_service.ActivityLogRepository") as mock_ar,
            patch("src.services.analytics_service.MedicineRepository") as mock_mr,
            patch("src.services.analytics_service.CostRepository") as mock_cr,
            patch("src.services.analytics_service.RoutineLogRepository") as mock_rl,
        ):
            mock_ar.return_value = AsyncMock(get_stats=AsyncMock(return_value=stats))
            mock_ar.return_value.db = db
            # Mock _predict_restocks dependency
            db.fetch_all = AsyncMock(return_value=[])
            mock_mr.return_value = AsyncMock(get_all=AsyncMock(return_value=medicines))
            mock_cr.return_value = AsyncMock(
                get_total_spent=AsyncMock(return_value=200.0),
                get_cost_summary=AsyncMock(
                    return_value={"by_medicine": [], "total_spent": 200.0, "period_days": 30}
                ),
            )
            mock_rl.return_value = AsyncMock(
                get_adherence_stats=AsyncMock(
                    return_value={"total": 10, "adherence_rate": 80.0, "period_days": 30}
                )
            )

            svc = AnalyticsService(":memory:")
            report = await svc.get_full_report(789012, days=30)

        assert "usage_stats" in report
        assert "inventory_summary" in report
        assert "cost_summary" in report
        assert report["inventory_summary"]["total_medicines"] == 2
        assert report["inventory_summary"]["total_units"] == 12
        assert report["inventory_summary"]["low_stock_count"] == 1

    @patch("src.services.analytics_service.Database")
    async def test_empty_report(self, mock_db_cls):
        db = AsyncMock()
        mock_db_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        mock_db_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = {
            "total_activities": 0,
            "activities_by_action": {},
            "most_active_users": [],
            "most_used_medicines": [],
            "period_days": 30,
        }

        with (
            patch("src.services.analytics_service.ActivityLogRepository") as mock_ar,
            patch("src.services.analytics_service.MedicineRepository") as mock_mr,
            patch("src.services.analytics_service.CostRepository") as mock_cr,
            patch("src.services.analytics_service.RoutineLogRepository") as mock_rl,
        ):
            mock_ar.return_value = AsyncMock(get_stats=AsyncMock(return_value=stats))
            mock_ar.return_value.db = db
            db.fetch_all = AsyncMock(return_value=[])
            mock_mr.return_value = AsyncMock(get_all=AsyncMock(return_value=[]))
            mock_cr.return_value = AsyncMock(
                get_total_spent=AsyncMock(return_value=0.0),
                get_cost_summary=AsyncMock(
                    return_value={"by_medicine": [], "total_spent": 0.0, "period_days": 30}
                ),
            )
            mock_rl.return_value = AsyncMock(get_adherence_stats=AsyncMock(return_value={}))

            svc = AnalyticsService(":memory:")
            report = await svc.get_full_report(789012)

        assert report["inventory_summary"]["total_medicines"] == 0
        assert report["cost_summary"]["total_spent"] == 0.0
