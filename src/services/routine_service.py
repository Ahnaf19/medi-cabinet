"""Routine service - orchestrates routine CRUD, scheduling, and stock deduction."""

from typing import List, Optional

from loguru import logger

from src.database import (
    Database,
    RoutineRepository,
    RoutineLogRepository,
    MedicineRepository,
    Routine,
    RoutineData,
    RoutineLog,
)


class RoutineService:
    """Business logic for medicine routines."""

    def __init__(self, db_path: str, scheduler=None):
        self.db_path = db_path
        self.scheduler = scheduler

    async def create_routine(self, data: RoutineData) -> Routine:
        """Create a routine and optionally link to existing medicine."""
        async with Database(self.db_path) as db:
            routine_repo = RoutineRepository(db)
            medicine_repo = MedicineRepository(db)

            # Try to link to existing medicine in cabinet
            medicine = await medicine_repo.find_by_exact_name(
                data.medicine_name, data.group_chat_id
            )
            if medicine:
                data.medicine_id = medicine.id

            routine = await routine_repo.create(data)

        # Schedule if scheduler available
        if self.scheduler:
            self.scheduler.schedule_routine(routine)

        logger.info(f"Created routine {routine.id} for {routine.medicine_name}")
        return routine

    async def list_routines(
        self, group_chat_id: int, user_id: Optional[int] = None
    ) -> List[Routine]:
        """List routines for a group, optionally filtered by user."""
        async with Database(self.db_path) as db:
            repo = RoutineRepository(db)
            if user_id:
                return await repo.get_user_routines(user_id, group_chat_id)
            return await repo.get_active_routines(group_chat_id)

    async def pause_routine(self, routine_id: int) -> Optional[Routine]:
        """Pause a routine and remove scheduled jobs."""
        async with Database(self.db_path) as db:
            repo = RoutineRepository(db)
            routine = await repo.update_status(routine_id, "paused")

        if self.scheduler:
            self.scheduler.unschedule_routine(routine_id)

        return routine

    async def resume_routine(self, routine_id: int) -> Optional[Routine]:
        """Resume a paused routine."""
        async with Database(self.db_path) as db:
            repo = RoutineRepository(db)
            routine = await repo.update_status(routine_id, "active")

        if routine and self.scheduler:
            self.scheduler.schedule_routine(routine)

        return routine

    async def delete_routine(self, routine_id: int) -> bool:
        """Delete a routine and its scheduled jobs."""
        if self.scheduler:
            self.scheduler.unschedule_routine(routine_id)

        async with Database(self.db_path) as db:
            repo = RoutineRepository(db)
            return await repo.delete(routine_id)

    async def mark_taken(self, log_id: int, routine_id: int) -> Optional[RoutineLog]:
        """Mark a routine dose as taken and deduct from stock if linked."""
        async with Database(self.db_path) as db:
            log_repo = RoutineLogRepository(db)
            routine_repo = RoutineRepository(db)
            medicine_repo = MedicineRepository(db)

            log_entry = await log_repo.mark_taken(log_id)

            # Deduct from stock if routine is linked to a medicine
            routine = await routine_repo.get_by_id(routine_id)
            if routine and routine.medicine_id:
                try:
                    await medicine_repo.update_quantity(
                        routine.medicine_id,
                        -routine.dosage_quantity,
                        routine.group_chat_id,
                    )
                    logger.debug(
                        f"Deducted {routine.dosage_quantity} {routine.dosage_unit} "
                        f"from {routine.medicine_name}"
                    )
                except Exception as e:
                    logger.warning(f"Could not deduct stock: {e}")

            return log_entry

    async def mark_skipped(self, log_id: int) -> None:
        """Mark a routine dose as skipped."""
        async with Database(self.db_path) as db:
            log_repo = RoutineLogRepository(db)
            await log_repo.mark_skipped(log_id)
