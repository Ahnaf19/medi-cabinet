"""Tests for cost tracking and analytics."""

import pytest

from src.database import (
    CostData,
)


class TestCostRepository:
    """Test cost repository operations."""

    @pytest.mark.asyncio
    async def test_add_cost(self, cost_repo, medicine_repo, sample_medicine_data):
        """Test adding a cost entry."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)

        data = CostData(
            medicine_id=medicine.id,
            total_cost=50.0,
            user_id=123456,
            username="TestUser",
            group_chat_id=sample_medicine_data.group_chat_id,
        )
        cost = await cost_repo.add_cost(data)

        assert cost.id is not None
        assert cost.total_cost == 50.0
        assert cost.currency == "BDT"

    @pytest.mark.asyncio
    async def test_get_total_spent(self, cost_repo, medicine_repo, sample_medicine_data):
        """Test getting total spent."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)

        for amount in [50.0, 120.0, 30.0]:
            data = CostData(
                medicine_id=medicine.id,
                total_cost=amount,
                user_id=123456,
                username="TestUser",
                group_chat_id=sample_medicine_data.group_chat_id,
            )
            await cost_repo.add_cost(data)

        total = await cost_repo.get_total_spent(sample_medicine_data.group_chat_id)
        assert total == 200.0

    @pytest.mark.asyncio
    async def test_get_total_spent_with_period(
        self, cost_repo, medicine_repo, sample_medicine_data
    ):
        """Test getting total spent within a period."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)

        data = CostData(
            medicine_id=medicine.id,
            total_cost=100.0,
            user_id=123456,
            username="TestUser",
            group_chat_id=sample_medicine_data.group_chat_id,
        )
        await cost_repo.add_cost(data)

        total = await cost_repo.get_total_spent(sample_medicine_data.group_chat_id, days=30)
        assert total == 100.0

    @pytest.mark.asyncio
    async def test_get_cost_summary(self, cost_repo, medicine_repo, sample_medicine_data):
        """Test getting cost summary grouped by medicine."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)

        for amount in [50.0, 30.0]:
            data = CostData(
                medicine_id=medicine.id,
                total_cost=amount,
                user_id=123456,
                username="TestUser",
                group_chat_id=sample_medicine_data.group_chat_id,
            )
            await cost_repo.add_cost(data)

        summary = await cost_repo.get_cost_summary(sample_medicine_data.group_chat_id, days=30)

        assert summary["total_spent"] == 80.0
        assert len(summary["by_medicine"]) == 1
        assert summary["by_medicine"][0]["name"] == "Napa"
        assert summary["by_medicine"][0]["purchases"] == 2

    @pytest.mark.asyncio
    async def test_empty_cost_summary(self, cost_repo):
        """Test cost summary with no data."""
        summary = await cost_repo.get_cost_summary(999999, days=30)
        assert summary["total_spent"] == 0
        assert len(summary["by_medicine"]) == 0
