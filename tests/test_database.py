"""Tests for database operations."""

import pytest
from datetime import datetime, timedelta

from src.database import (
    MedicineData,
    InsufficientStockError,
    DatabaseError,
)


class TestMedicineRepository:
    """Test medicine repository operations."""

    @pytest.mark.asyncio
    async def test_add_medicine(self, medicine_repo, sample_medicine_data):
        """Test adding a new medicine."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)

        assert medicine.id is not None
        assert medicine.name == sample_medicine_data.name
        assert medicine.quantity == sample_medicine_data.quantity
        assert medicine.unit == sample_medicine_data.unit
        assert medicine.group_chat_id == sample_medicine_data.group_chat_id

    @pytest.mark.asyncio
    async def test_add_duplicate_medicine_updates_quantity(
        self, medicine_repo, sample_medicine_data
    ):
        """Test that adding duplicate medicine updates quantity."""
        # Add first time
        medicine1 = await medicine_repo.add_medicine(sample_medicine_data)
        initial_quantity = medicine1.quantity

        # Add again with same name
        medicine2 = await medicine_repo.add_medicine(sample_medicine_data)

        # Should update existing, not create new
        assert medicine1.id == medicine2.id
        assert medicine2.quantity == initial_quantity + sample_medicine_data.quantity

    @pytest.mark.asyncio
    async def test_find_by_exact_name(self, medicine_repo, sample_medicine_data):
        """Test finding medicine by exact name."""
        await medicine_repo.add_medicine(sample_medicine_data)

        # Find by exact name (case insensitive)
        found = await medicine_repo.find_by_exact_name(
            "napa", sample_medicine_data.group_chat_id
        )

        assert found is not None
        assert found.name.lower() == sample_medicine_data.name.lower()

    @pytest.mark.asyncio
    async def test_find_by_exact_name_not_found(self, medicine_repo):
        """Test finding non-existent medicine."""
        found = await medicine_repo.find_by_exact_name("NonExistent", 789012)
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_name_fuzzy(self, medicine_repo, sample_medicine_data):
        """Test fuzzy name matching."""
        await medicine_repo.add_medicine(sample_medicine_data)

        # Exact match should have 100% confidence
        matches = await medicine_repo.find_by_name_fuzzy(
            "Napa", sample_medicine_data.group_chat_id, threshold=80
        )

        assert len(matches) > 0
        medicine, confidence = matches[0]
        assert medicine.name == "Napa"
        assert confidence == 100

    @pytest.mark.asyncio
    async def test_find_by_name_fuzzy_with_typo(self, medicine_repo, sample_medicine_data):
        """Test fuzzy matching with typo."""
        await medicine_repo.add_medicine(sample_medicine_data)

        # Search with typo
        matches = await medicine_repo.find_by_name_fuzzy(
            "Nappa", sample_medicine_data.group_chat_id, threshold=70
        )

        assert len(matches) > 0
        medicine, confidence = matches[0]
        assert medicine.name == "Napa"
        assert confidence >= 70

    @pytest.mark.asyncio
    async def test_update_quantity_increase(self, medicine_repo, sample_medicine_data):
        """Test increasing medicine quantity."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)
        initial_quantity = medicine.quantity

        # Increase quantity by 5
        updated = await medicine_repo.update_quantity(
            medicine.id, 5, sample_medicine_data.group_chat_id
        )

        assert updated.quantity == initial_quantity + 5

    @pytest.mark.asyncio
    async def test_update_quantity_decrease(self, medicine_repo, sample_medicine_data):
        """Test decreasing medicine quantity."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)
        initial_quantity = medicine.quantity

        # Decrease quantity by 3
        updated = await medicine_repo.update_quantity(
            medicine.id, -3, sample_medicine_data.group_chat_id
        )

        assert updated.quantity == initial_quantity - 3

    @pytest.mark.asyncio
    async def test_update_quantity_insufficient_stock(
        self, medicine_repo, sample_medicine_data
    ):
        """Test that using more than available raises error."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)

        # Try to use more than available
        with pytest.raises(InsufficientStockError) as exc_info:
            await medicine_repo.update_quantity(
                medicine.id, -100, sample_medicine_data.group_chat_id
            )

        assert exc_info.value.available == medicine.quantity
        assert exc_info.value.requested == 100

    @pytest.mark.asyncio
    async def test_get_all(self, medicine_repo, sample_medicine_data):
        """Test getting all medicines for a group."""
        # Add multiple medicines
        await medicine_repo.add_medicine(sample_medicine_data)

        data2 = MedicineData(
            name="Sergel",
            quantity=5,
            unit="tablets",
            expiry_date=None,
            location=None,
            added_by_user_id=123456,
            added_by_username="TestUser",
            group_chat_id=sample_medicine_data.group_chat_id,
        )
        await medicine_repo.add_medicine(data2)

        medicines = await medicine_repo.get_all(sample_medicine_data.group_chat_id)

        assert len(medicines) == 2
        names = {m.name for m in medicines}
        assert "Napa" in names
        assert "Sergel" in names

    @pytest.mark.asyncio
    async def test_get_low_stock(self, medicine_repo, sample_medicine_data):
        """Test getting low stock medicines."""
        # Add medicine with low stock
        low_stock_data = MedicineData(
            name="LowStock",
            quantity=2,
            unit="tablets",
            expiry_date=None,
            location=None,
            added_by_user_id=123456,
            added_by_username="TestUser",
            group_chat_id=sample_medicine_data.group_chat_id,
        )
        await medicine_repo.add_medicine(low_stock_data)

        # Add medicine with normal stock
        await medicine_repo.add_medicine(sample_medicine_data)

        # Get low stock (threshold = 3)
        low_stock = await medicine_repo.get_low_stock(
            sample_medicine_data.group_chat_id, threshold=3
        )

        assert len(low_stock) == 1
        assert low_stock[0].name == "LowStock"
        assert low_stock[0].quantity < 3

    @pytest.mark.asyncio
    async def test_get_expiring_soon(self, medicine_repo, sample_medicine_data):
        """Test getting expiring medicines."""
        # Add medicine expiring soon
        expiring_data = MedicineData(
            name="Expiring",
            quantity=10,
            unit="tablets",
            expiry_date=datetime.now() + timedelta(days=15),
            location=None,
            added_by_user_id=123456,
            added_by_username="TestUser",
            group_chat_id=sample_medicine_data.group_chat_id,
        )
        await medicine_repo.add_medicine(expiring_data)

        # Add medicine not expiring soon
        sample_medicine_data.expiry_date = datetime.now() + timedelta(days=365)
        await medicine_repo.add_medicine(sample_medicine_data)

        # Get expiring within 30 days
        expiring = await medicine_repo.get_expiring_soon(
            sample_medicine_data.group_chat_id, days=30
        )

        assert len(expiring) == 1
        assert expiring[0].name == "Expiring"

    @pytest.mark.asyncio
    async def test_delete_medicine(self, medicine_repo, sample_medicine_data):
        """Test deleting a medicine."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)

        # Delete medicine
        deleted = await medicine_repo.delete_medicine(
            medicine.id, sample_medicine_data.group_chat_id
        )

        assert deleted is True

        # Verify it's gone
        found = await medicine_repo.get_by_id(
            medicine.id, sample_medicine_data.group_chat_id
        )
        assert found is None

    @pytest.mark.asyncio
    async def test_multi_group_isolation(self, medicine_repo, sample_medicine_data):
        """Test that groups don't see each other's medicines."""
        # Add medicine to group 1
        await medicine_repo.add_medicine(sample_medicine_data)

        # Try to find in different group
        found = await medicine_repo.find_by_exact_name(
            sample_medicine_data.name, 999999  # Different group
        )

        assert found is None


class TestActivityLogRepository:
    """Test activity log repository operations."""

    @pytest.mark.asyncio
    async def test_log_activity(self, medicine_repo, activity_repo, sample_medicine_data):
        """Test logging an activity."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)

        activity = await activity_repo.log_activity(
            medicine_id=medicine.id,
            action="added",
            user_id=123456,
            username="TestUser",
            group_chat_id=sample_medicine_data.group_chat_id,
            quantity_change=10,
        )

        assert activity.id is not None
        assert activity.medicine_id == medicine.id
        assert activity.action == "added"
        assert activity.quantity_change == 10

    @pytest.mark.asyncio
    async def test_get_history(self, medicine_repo, activity_repo, sample_medicine_data):
        """Test getting activity history."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)

        # Log multiple activities
        await activity_repo.log_activity(
            medicine.id, "added", 123456, "User1", sample_medicine_data.group_chat_id, 10
        )
        await activity_repo.log_activity(
            medicine.id, "used", 123456, "User1", sample_medicine_data.group_chat_id, -2
        )

        history = await activity_repo.get_history(medicine.id, limit=10)

        assert len(history) == 2
        assert history[0].action == "used"  # Most recent first
        assert history[1].action == "added"

    @pytest.mark.asyncio
    async def test_get_stats(self, medicine_repo, activity_repo, sample_medicine_data):
        """Test getting usage statistics."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)

        # Log activities
        await activity_repo.log_activity(
            medicine.id, "added", 123456, "User1", sample_medicine_data.group_chat_id, 10
        )
        await activity_repo.log_activity(
            medicine.id, "used", 123456, "User1", sample_medicine_data.group_chat_id, -2
        )
        await activity_repo.log_activity(
            medicine.id, "searched", 789012, "User2", sample_medicine_data.group_chat_id
        )

        stats = await activity_repo.get_stats(sample_medicine_data.group_chat_id, days=30)

        assert stats["total_activities"] == 3
        assert "added" in stats["activities_by_action"]
        assert "used" in stats["activities_by_action"]
        assert len(stats["most_active_users"]) > 0
