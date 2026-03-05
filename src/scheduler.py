"""Routine scheduler integrating with python-telegram-bot's JobQueue."""

from datetime import datetime, time as dt_time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from src.database import (
    Database,
    RoutineRepository,
    RoutineLogRepository,
    Routine,
)


class RoutineScheduler:
    """Manages scheduling of medicine routine reminders."""

    def __init__(self, job_queue, db_path: str):
        self.job_queue = job_queue
        self.db_path = db_path

    async def load_all_routines(self) -> int:
        """Load all active routines and schedule their jobs.

        Returns:
            Number of routines scheduled
        """
        async with Database(self.db_path) as db:
            repo = RoutineRepository(db)
            routines = await repo.get_active_routines()

        count = 0
        for routine in routines:
            try:
                self.schedule_routine(routine)
                count += 1
            except Exception as e:
                logger.error(f"Failed to schedule routine {routine.id}: {e}")

        logger.info(f"Loaded {count} active routines")
        return count

    def schedule_routine(self, routine: Routine) -> None:
        """Schedule jobs for a routine based on its times_of_day."""
        # Remove any existing jobs for this routine first
        self.unschedule_routine(routine.id)

        for time_str in routine.times_of_day:
            try:
                hour, minute = map(int, time_str.split(":"))
                job_time = dt_time(hour=hour, minute=minute)
                job_name = f"routine_{routine.id}_{time_str}"

                self.job_queue.run_daily(
                    self._reminder_callback,
                    time=job_time,
                    name=job_name,
                    data={
                        "routine_id": routine.id,
                        "chat_id": routine.group_chat_id,
                        "medicine_name": routine.medicine_name,
                        "dosage_quantity": routine.dosage_quantity,
                        "dosage_unit": routine.dosage_unit,
                        "meal_relation": routine.meal_relation,
                        "scheduled_time": time_str,
                    },
                )
                logger.debug(f"Scheduled routine {routine.id} at {time_str}")
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid time '{time_str}' for routine {routine.id}: {e}")

    def unschedule_routine(self, routine_id: int) -> None:
        """Remove all scheduled jobs for a routine."""
        prefix = f"routine_{routine_id}_"
        for job in self.job_queue.jobs():
            if job.name and job.name.startswith(prefix):
                job.schedule_removal()
                logger.debug(f"Removed job: {job.name}")

    @staticmethod
    async def _reminder_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a reminder message with Taken/Skip buttons."""
        data = context.job.data
        routine_id = data["routine_id"]
        chat_id = data["chat_id"]
        medicine_name = data["medicine_name"]
        dosage_qty = data["dosage_quantity"]
        dosage_unit = data["dosage_unit"]
        meal_relation = data.get("meal_relation")
        scheduled_time = data["scheduled_time"]

        db_path = context.bot_data.get("config").database_path

        # Mark old pending logs as missed, create new pending log
        async with Database(db_path) as db:
            log_repo = RoutineLogRepository(db)
            await log_repo.mark_old_pending_as_missed(routine_id)

            log_entry = await log_repo.create_log(
                routine_id=routine_id,
                scheduled_time=datetime.now(),
                group_chat_id=chat_id,
            )

        # Build message
        msg = f"Time to take your medicine!\n\n"
        msg += f"*{medicine_name}* - {dosage_qty} {dosage_unit}"
        if meal_relation:
            relation_text = meal_relation.replace("_", " ").title()
            msg += f"\n{relation_text}"
        msg += f"\nScheduled: {scheduled_time}"

        # Inline keyboard for response
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Taken",
                        callback_data=f"routine_taken_{log_entry.id}_{routine_id}",
                    ),
                    InlineKeyboardButton(
                        "Skip",
                        callback_data=f"routine_skip_{log_entry.id}_{routine_id}",
                    ),
                ]
            ]
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
