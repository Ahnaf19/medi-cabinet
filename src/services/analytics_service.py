"""Analytics service for usage patterns, cost tracking, and predictions."""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from src.database import (
    Database,
    MedicineRepository,
    ActivityLogRepository,
    RoutineLogRepository,
    CostRepository,
)


class AnalyticsService:
    """Generates analytics from medicine usage data."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def get_full_report(self, group_chat_id: int, days: int = 30) -> Dict[str, Any]:
        """Generate a comprehensive analytics report."""
        async with Database(self.db_path) as db:
            activity_repo = ActivityLogRepository(db)
            medicine_repo = MedicineRepository(db)
            cost_repo = CostRepository(db)

            # Basic stats
            stats = await activity_repo.get_stats(group_chat_id, days)
            medicines = await medicine_repo.get_all(group_chat_id)
            total_spent = await cost_repo.get_total_spent(group_chat_id, days)
            cost_summary = await cost_repo.get_cost_summary(group_chat_id, days)

            # Adherence stats (may not have routines table yet)
            adherence = {}
            try:
                routine_log_repo = RoutineLogRepository(db)
                adherence = await routine_log_repo.get_adherence_stats(group_chat_id, days)
            except Exception:
                pass

            # Restock predictions
            restock_predictions = await self._predict_restocks(
                activity_repo, medicines, group_chat_id, days
            )

        return {
            "usage_stats": stats,
            "inventory_summary": {
                "total_medicines": len(medicines),
                "total_units": sum(m.quantity for m in medicines),
                "low_stock_count": sum(1 for m in medicines if m.quantity < 3),
                "expired_count": sum(
                    1 for m in medicines if m.expiry_date and m.expiry_date < datetime.now()
                ),
            },
            "cost_summary": {
                "total_spent": total_spent,
                "by_medicine": cost_summary.get("by_medicine", []),
            },
            "adherence": adherence,
            "restock_predictions": restock_predictions,
            "period_days": days,
        }

    async def _predict_restocks(
        self,
        activity_repo: ActivityLogRepository,
        medicines: list,
        group_chat_id: int,
        days: int,
    ) -> List[Dict[str, Any]]:
        """Predict when medicines will need restocking based on usage rate."""
        predictions = []
        cutoff = datetime.now() - timedelta(days=days)

        for medicine in medicines:
            if medicine.quantity <= 0:
                continue

            # Get usage count in period
            rows = await activity_repo.db.fetch_all(
                """
                SELECT COUNT(*) as count, COALESCE(SUM(ABS(quantity_change)), 0) as total_used
                FROM activity_log
                WHERE medicine_id = ? AND action = 'used'
                  AND group_chat_id = ? AND timestamp >= ?
                """,
                (medicine.id, group_chat_id, cutoff.isoformat()),
            )

            if not rows or rows[0]["total_used"] == 0:
                continue

            total_used = rows[0]["total_used"]
            daily_rate = total_used / days

            if daily_rate > 0:
                days_until_empty = int(medicine.quantity / daily_rate)
                predictions.append(
                    {
                        "name": medicine.name,
                        "current_stock": medicine.quantity,
                        "daily_usage": round(daily_rate, 1),
                        "days_until_empty": days_until_empty,
                        "restock_date": (
                            datetime.now() + timedelta(days=days_until_empty)
                        ).strftime("%b %d, %Y"),
                    }
                )

        # Sort by urgency
        predictions.sort(key=lambda x: x["days_until_empty"])
        return predictions
