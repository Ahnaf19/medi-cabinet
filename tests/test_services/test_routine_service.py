"""Tests for routine repository and service."""

from datetime import datetime

import pytest


class TestRoutineRepository:
    """Test routine repository operations."""

    @pytest.mark.asyncio
    async def test_create_routine(self, routine_repo, sample_routine_data):
        """Test creating a routine."""
        routine = await routine_repo.create(sample_routine_data)

        assert routine.id is not None
        assert routine.medicine_name == "Napa"
        assert routine.dosage_quantity == 1
        assert routine.frequency == "daily"
        assert routine.times_of_day == ["08:00", "20:00"]
        assert routine.meal_relation == "after_meal"
        assert routine.status == "active"

    @pytest.mark.asyncio
    async def test_get_active_routines(self, routine_repo, sample_routine_data):
        """Test getting active routines."""
        await routine_repo.create(sample_routine_data)
        routines = await routine_repo.get_active_routines(sample_routine_data.group_chat_id)
        assert len(routines) == 1
        assert routines[0].status == "active"

    @pytest.mark.asyncio
    async def test_get_user_routines(self, routine_repo, sample_routine_data):
        """Test getting routines for a specific user."""
        await routine_repo.create(sample_routine_data)
        routines = await routine_repo.get_user_routines(
            sample_routine_data.created_by_user_id,
            sample_routine_data.group_chat_id,
        )
        assert len(routines) == 1

    @pytest.mark.asyncio
    async def test_update_status(self, routine_repo, sample_routine_data):
        """Test pausing and resuming a routine."""
        routine = await routine_repo.create(sample_routine_data)

        # Pause
        paused = await routine_repo.update_status(routine.id, "paused")
        assert paused.status == "paused"

        # Resume
        resumed = await routine_repo.update_status(routine.id, "active")
        assert resumed.status == "active"

    @pytest.mark.asyncio
    async def test_delete_routine(self, routine_repo, sample_routine_data):
        """Test deleting a routine."""
        routine = await routine_repo.create(sample_routine_data)
        deleted = await routine_repo.delete(routine.id)
        assert deleted is True

        result = await routine_repo.get_by_id(routine.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_link_medicine(
        self, routine_repo, medicine_repo, sample_routine_data, sample_medicine_data
    ):
        """Test linking a routine to a medicine."""
        medicine = await medicine_repo.add_medicine(sample_medicine_data)
        routine = await routine_repo.create(sample_routine_data)

        await routine_repo.link_medicine(routine.id, medicine.id)
        updated = await routine_repo.get_by_id(routine.id)
        assert updated.medicine_id == medicine.id


class TestRoutineLogRepository:
    """Test routine log operations."""

    @pytest.mark.asyncio
    async def test_create_and_mark_taken(self, routine_repo, routine_log_repo, sample_routine_data):
        """Test creating a log and marking as taken."""
        routine = await routine_repo.create(sample_routine_data)

        log = await routine_log_repo.create_log(
            routine.id, datetime.now(), sample_routine_data.group_chat_id
        )
        assert log.status == "pending"

        taken = await routine_log_repo.mark_taken(log.id)
        assert taken.status == "taken"
        assert taken.actual_time is not None

    @pytest.mark.asyncio
    async def test_mark_skipped(self, routine_repo, routine_log_repo, sample_routine_data):
        """Test marking a log as skipped."""
        routine = await routine_repo.create(sample_routine_data)
        log = await routine_log_repo.create_log(
            routine.id, datetime.now(), sample_routine_data.group_chat_id
        )

        await routine_log_repo.mark_skipped(log.id)
        # Verify by getting pending - should be empty
        pending = await routine_log_repo.get_pending_log(routine.id)
        assert pending is None

    @pytest.mark.asyncio
    async def test_adherence_stats(self, routine_repo, routine_log_repo, sample_routine_data):
        """Test adherence statistics."""
        routine = await routine_repo.create(sample_routine_data)

        # Create logs with different statuses
        log1 = await routine_log_repo.create_log(
            routine.id, datetime.now(), sample_routine_data.group_chat_id
        )
        await routine_log_repo.mark_taken(log1.id)

        log2 = await routine_log_repo.create_log(
            routine.id, datetime.now(), sample_routine_data.group_chat_id
        )
        await routine_log_repo.mark_taken(log2.id)

        log3 = await routine_log_repo.create_log(
            routine.id, datetime.now(), sample_routine_data.group_chat_id
        )
        await routine_log_repo.mark_skipped(log3.id)

        stats = await routine_log_repo.get_adherence_stats(
            sample_routine_data.group_chat_id, days=30
        )

        assert stats["total"] == 3
        assert stats["by_status"]["taken"] == 2
        assert stats["by_status"]["skipped"] == 1
        assert stats["adherence_rate"] == pytest.approx(66.7, abs=0.1)
