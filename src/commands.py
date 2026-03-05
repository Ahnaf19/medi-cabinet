"""Command handlers for the Telegram bot."""

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from loguru import logger

from config.config import Settings
from src.database import (
    Database,
    MedicineRepository,
    ActivityLogRepository,
    RoutineRepository,
    RoutineLogRepository,
    CostRepository,
    MedicineData,
    RoutineData,
    CostData,
    InsufficientStockError,
    DatabaseError,
)
from src.parsers import CommandParser
from src.utils import (
    format_medicine_list,
    format_medicine_detail,
    format_activity_history,
    format_low_stock_alert,
    format_expiry_warning,
    format_routine_list,
    format_routine_detail,
    format_interaction_warning,
    format_cost_summary,
    format_adherence_stats,
    format_analytics_report,
    generate_usage_stats,
    get_welcome_message,
    get_help_message,
    is_admin,
    calculate_days_until_expiry,
)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command.

    Args:
        update: Telegram update
        context: Bot context
    """
    await update.message.reply_text(
        get_welcome_message(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command.

    Args:
        update: Telegram update
        context: Bot context
    """
    await update.message.reply_text(
        get_help_message(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle natural text messages (main router).

    Args:
        update: Telegram update
        context: Bot context
    """
    if not update.message or not update.message.text:
        return

    text = update.message.text
    config: Settings = context.bot_data["config"]
    parser = CommandParser()

    # Parse the command
    parsed = parser.parse(text)

    logger.bind(
        user_id=update.effective_user.id,
        chat_id=update.effective_chat.id,
        command_type=parsed.command_type,
    ).info(f"Processing command: {text}")

    # Tier 2: LLM fallback for unknown commands
    if parsed.command_type == "unknown":
        llm_provider = context.bot_data.get("llm_provider")
        if llm_provider:
            from src.llm.parser import LLMParser

            llm_parsed = await LLMParser(llm_provider).parse(text)
            if llm_parsed:
                parsed = llm_parsed
                logger.info(f"LLM parsed as: {parsed.command_type}")

    # Route to appropriate handler
    if parsed.command_type == "add":
        await handle_add_medicine(update, context, parsed, config)
    elif parsed.command_type == "use":
        await handle_use_medicine(update, context, parsed, config)
    elif parsed.command_type == "search":
        await handle_search_medicine(update, context, parsed, config)
    elif parsed.command_type == "list":
        await handle_list_all(update, context, config)
    elif parsed.command_type == "routine":
        await _handle_routine_from_text(update, context, parsed, config)
    elif parsed.command_type == "cost":
        await _handle_cost_from_text(update, context, parsed, config)
    else:
        await update.message.reply_text(
            " Sorry, I didn't understand that command.\n\n"
            "Try:\n"
            "`+Napa 10` to add medicine\n"
            "`-Napa 2` to use medicine\n"
            "`?Napa` to search\n"
            "`?all` to list all\n"
            "`/routine add Napa at 8AM daily` to set reminders\n"
            "Type `/help` for more examples!",
            parse_mode=ParseMode.MARKDOWN,
        )


async def handle_add_medicine(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parsed,
    config: Settings,
) -> None:
    """Handle adding medicine.

    Args:
        update: Telegram update
        context: Bot context
        parsed: ParsedCommand object
        config: Settings instance
    """
    if not parsed.medicine_name:
        await update.message.reply_text(
            " Please specify a medicine name.\nExample: `+Napa 10`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Ask for quantity if not provided
    if parsed.quantity is None:
        await update.message.reply_text(
            f" How many {parsed.unit} of *{parsed.medicine_name}* did you add?",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    group_chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Unknown"

    async with Database(config.database_path) as db:
        medicine_repo = MedicineRepository(db)
        activity_repo = ActivityLogRepository(db)

        try:
            # Create medicine data
            medicine_data = MedicineData(
                name=parsed.medicine_name,
                quantity=parsed.quantity,
                unit=parsed.unit,
                expiry_date=parsed.expiry_date,
                location=parsed.location,
                added_by_user_id=user_id,
                added_by_username=username,
                group_chat_id=group_chat_id,
            )

            # Add or update medicine
            medicine = await medicine_repo.add_medicine(medicine_data)

            # Log activity
            await activity_repo.log_activity(
                medicine_id=medicine.id,
                action="added",
                user_id=user_id,
                username=username,
                group_chat_id=group_chat_id,
                quantity_change=parsed.quantity,
            )

            # Build response message
            response = f" Added *{medicine.name}* ({parsed.quantity} {medicine.unit})\n"
            response += f" Total now: {medicine.quantity} {medicine.unit}"

            if medicine.expiry_date:
                days = calculate_days_until_expiry(medicine.expiry_date)
                if days <= 0:
                    response += f"\n EXPIRED!"
                elif days <= 30:
                    response += f"\n Expiring in {days} days"

            # Check for low stock after addition
            if medicine.quantity < config.low_stock_threshold:
                response += f"\n Still low stock! (< {config.low_stock_threshold})"

            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

            # Check for drug interactions
            try:
                from src.services.interaction_service import InteractionService

                interaction_svc = InteractionService(config.database_path)
                interactions = await interaction_svc.check_against_cabinet(
                    medicine.name, group_chat_id
                )
                if interactions:
                    warning = format_interaction_warning(interactions)
                    await update.message.reply_text(warning, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass  # Don't block add if interaction check fails

        except DatabaseError as e:
            logger.exception("Database error while adding medicine")
            await update.message.reply_text(
                " Sorry, there was an error adding the medicine. Please try again."
            )


async def handle_use_medicine(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parsed,
    config: Settings,
) -> None:
    """Handle using/consuming medicine.

    Args:
        update: Telegram update
        context: Bot context
        parsed: ParsedCommand object
        config: Settings instance
    """
    if not parsed.medicine_name:
        await update.message.reply_text(
            " Please specify a medicine name.\nExample: `-Napa 2`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if not parsed.quantity:
        await update.message.reply_text(
            f" How many {parsed.unit} of *{parsed.medicine_name}* did you use?",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    group_chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Unknown"

    async with Database(config.database_path) as db:
        medicine_repo = MedicineRepository(db)
        activity_repo = ActivityLogRepository(db)

        try:
            # Find medicine by name (with fuzzy matching)
            matches = await medicine_repo.find_by_name_fuzzy(
                parsed.medicine_name,
                group_chat_id,
                threshold=config.fuzzy_match_threshold,
            )

            if not matches:
                await update.message.reply_text(
                    f" Medicine *{parsed.medicine_name}* not found in cabinet.\n"
                    f"Did you mean to search? Try `?{parsed.medicine_name}`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            if len(matches) == 1:
                medicine, confidence = matches[0]
            elif matches[0][1] == 100:
                # Exact match
                medicine, confidence = matches[0]
            else:
                # Multiple fuzzy matches - ask user to clarify
                response = f" Found multiple medicines matching *{parsed.medicine_name}*:\n\n"
                for idx, (med, conf) in enumerate(matches[:5], 1):
                    response += f"{idx}. {med.name} ({med.quantity} {med.unit}) - {conf}% match\n"
                response += "\nPlease be more specific!"
                await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
                return

            # Update quantity (negative delta for use)
            updated_medicine = await medicine_repo.update_quantity(
                medicine.id, -parsed.quantity, group_chat_id
            )

            # Log activity
            await activity_repo.log_activity(
                medicine_id=medicine.id,
                action="used",
                user_id=user_id,
                username=username,
                group_chat_id=group_chat_id,
                quantity_change=-parsed.quantity,
            )

            # Build response
            response = f" Used {parsed.quantity} {medicine.unit} of *{medicine.name}*\n"
            response += f" Remaining: {updated_medicine.quantity} {medicine.unit}"

            # Low stock warning
            if updated_medicine.quantity < config.low_stock_threshold:
                response += f"\n Low stock! Only {updated_medicine.quantity} left."

            if updated_medicine.quantity == 0:
                response += "\n Out of stock!"

            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

        except InsufficientStockError as e:
            await update.message.reply_text(
                f" Insufficient stock!\n"
                f"Available: {e.available} {parsed.unit}\n"
                f"Requested: {e.requested} {parsed.unit}",
                parse_mode=ParseMode.MARKDOWN,
            )

        except DatabaseError as e:
            logger.exception("Database error while using medicine")
            await update.message.reply_text(" Sorry, there was an error. Please try again.")


async def handle_search_medicine(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parsed,
    config: Settings,
) -> None:
    """Handle searching for medicine.

    Args:
        update: Telegram update
        context: Bot context
        parsed: ParsedCommand object
        config: Settings instance
    """
    if not parsed.medicine_name:
        await update.message.reply_text(
            " Please specify a medicine name.\nExample: `?Napa`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    group_chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Unknown"

    async with Database(config.database_path) as db:
        medicine_repo = MedicineRepository(db)
        activity_repo = ActivityLogRepository(db)

        try:
            # Find medicine by name (with fuzzy matching)
            matches = await medicine_repo.find_by_name_fuzzy(
                parsed.medicine_name,
                group_chat_id,
                threshold=config.fuzzy_match_threshold,
            )

            if not matches:
                await update.message.reply_text(
                    f" No medicine found matching *{parsed.medicine_name}*\n"
                    f"Try `?all` to see what's in the cabinet.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            # Log search activity for first match
            await activity_repo.log_activity(
                medicine_id=matches[0][0].id,
                action="searched",
                user_id=user_id,
                username=username,
                group_chat_id=group_chat_id,
            )

            # Display results
            if len(matches) == 1:
                medicine, confidence = matches[0]
                response = f" Found: {format_medicine_detail(medicine)}"
            else:
                response = (
                    f" Found {len(matches)} medicine(s) matching *{parsed.medicine_name}*:\n\n"
                )
                medicines_only = [med for med, conf in matches]
                response += format_medicine_list(medicines_only, config.low_stock_threshold)

            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

        except DatabaseError as e:
            logger.exception("Database error while searching medicine")
            await update.message.reply_text(" Sorry, there was an error. Please try again.")


async def handle_list_all(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    config: Settings,
) -> None:
    """Handle listing all medicines.

    Args:
        update: Telegram update
        context: Bot context
        config: Settings instance
    """
    group_chat_id = update.effective_chat.id

    async with Database(config.database_path) as db:
        medicine_repo = MedicineRepository(db)

        try:
            medicines = await medicine_repo.get_all(group_chat_id)

            if not medicines:
                await update.message.reply_text(
                    " Medicine cabinet is empty.\n" "Add some medicines using `+Napa 10`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            response = f" *Medicine Cabinet* (Total: {len(medicines)})\n\n"
            response += format_medicine_list(medicines, config.low_stock_threshold)

            # Check for low stock
            low_stock = [m for m in medicines if m.quantity < config.low_stock_threshold]
            if low_stock:
                response += "\n\n" + format_low_stock_alert(low_stock)

            # Check for expiring medicines
            expiring = [
                m
                for m in medicines
                if m.expiry_date
                and calculate_days_until_expiry(m.expiry_date) <= config.expiry_warning_days
            ]
            if expiring:
                response += "\n\n" + format_expiry_warning(expiring)

            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

        except DatabaseError as e:
            logger.exception("Database error while listing medicines")
            await update.message.reply_text(" Sorry, there was an error. Please try again.")


async def handle_delete_medicine(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle deleting medicine (admin only).

    Args:
        update: Telegram update
        context: Bot context
    """
    config: Settings = context.bot_data["config"]
    user_id = update.effective_user.id

    # Check admin permission
    if not is_admin(user_id, config):
        await update.message.reply_text(" This command is only available to administrators.")
        return

    # Extract medicine name from command
    if not context.args:
        await update.message.reply_text(
            " Please specify a medicine name.\nExample: `/delete Napa`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    medicine_name = " ".join(context.args)
    group_chat_id = update.effective_chat.id
    username = update.effective_user.first_name or "Unknown"

    async with Database(config.database_path) as db:
        medicine_repo = MedicineRepository(db)
        activity_repo = ActivityLogRepository(db)

        try:
            # Find medicine
            matches = await medicine_repo.find_by_name_fuzzy(
                medicine_name, group_chat_id, threshold=config.fuzzy_match_threshold
            )

            if not matches:
                await update.message.reply_text(
                    f" Medicine *{medicine_name}* not found.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            if len(matches) > 1 and matches[0][1] < 100:
                # Multiple fuzzy matches
                response = f" Found multiple medicines matching *{medicine_name}*:\n\n"
                for idx, (med, conf) in enumerate(matches[:5], 1):
                    response += f"{idx}. {med.name} - {conf}% match\n"
                response += "\nPlease be more specific!"
                await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
                return

            medicine, confidence = matches[0]

            # Log deletion activity before deleting
            await activity_repo.log_activity(
                medicine_id=medicine.id,
                action="deleted",
                user_id=user_id,
                username=username,
                group_chat_id=group_chat_id,
            )

            # Delete medicine
            deleted = await medicine_repo.delete_medicine(medicine.id, group_chat_id)

            if deleted:
                await update.message.reply_text(
                    f" Deleted *{medicine.name}* from cabinet.",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await update.message.reply_text(" Failed to delete medicine. Please try again.")

        except DatabaseError as e:
            logger.exception("Database error while deleting medicine")
            await update.message.reply_text(" Sorry, there was an error. Please try again.")


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle showing usage statistics.

    Args:
        update: Telegram update
        context: Bot context
    """
    config: Settings = context.bot_data["config"]
    group_chat_id = update.effective_chat.id

    async with Database(config.database_path) as db:
        activity_repo = ActivityLogRepository(db)

        try:
            # Get statistics for last 30 days
            stats_data = await activity_repo.get_stats(group_chat_id, days=30)

            response = generate_usage_stats(stats_data)

            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

        except DatabaseError as e:
            logger.exception("Database error while generating stats")
            await update.message.reply_text(
                " Sorry, there was an error generating statistics. Please try again."
            )


async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors.

    Args:
        update: Telegram update
        context: Bot context
    """
    logger.exception("An error occurred", error=context.error)

    if update and update.effective_message:
        await update.effective_message.reply_text(
            " Sorry, something went wrong. Please try again later."
        )


async def scheduled_expiry_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job to check for expiring medicines.

    Iterates active group chats and sends warnings for expiring medicines.
    """
    config: Settings = context.bot_data["config"]

    try:
        async with Database(config.database_path) as db:
            # Get distinct group chat IDs that have medicines
            rows = await db.fetch_all(
                "SELECT DISTINCT group_chat_id FROM medicines WHERE quantity > 0"
            )

            for row in rows:
                group_chat_id = row["group_chat_id"]
                medicine_repo = MedicineRepository(db)

                # Check expiring medicines
                expiring = await medicine_repo.get_expiring_soon(
                    group_chat_id, days=config.expiry_warning_days
                )

                if expiring:
                    msg = format_expiry_warning(expiring)
                    try:
                        await context.bot.send_message(
                            chat_id=group_chat_id,
                            text=f"Daily Check\n\n{msg}",
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    except Exception as e:
                        logger.warning(f"Could not send expiry alert to {group_chat_id}: {e}")

                # Check low stock
                low_stock = await medicine_repo.get_low_stock(
                    group_chat_id, config.low_stock_threshold
                )
                if low_stock:
                    msg = format_low_stock_alert(low_stock)
                    try:
                        await context.bot.send_message(
                            chat_id=group_chat_id,
                            text=msg,
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    except Exception as e:
                        logger.warning(f"Could not send low stock alert to {group_chat_id}: {e}")

    except Exception as e:
        logger.exception("Error in scheduled expiry check")


async def scheduled_backup(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job to backup database.

    Args:
        context: Bot context
    """
    config: Settings = context.bot_data["config"]

    import shutil
    from pathlib import Path

    try:
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"medi-cabinet_{timestamp}.db"

        shutil.copy(config.database_path, backup_path)
        logger.info(f"Database backed up to {backup_path}")

    except Exception as e:
        logger.exception("Failed to backup database")


# --- Phase 4: Routine handlers ---


async def handle_routine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /routine command: add, list, pause, delete."""
    config: Settings = context.bot_data["config"]

    if not context.args:
        await update.message.reply_text(
            "*Routine Commands:*\n\n"
            "`/routine add Napa 1 tablet at 08:00 daily before meal`\n"
            "`/routine list` - Show your routines\n"
            "`/routine pause <id>` - Pause a routine\n"
            "`/routine resume <id>` - Resume a routine\n"
            "`/routine delete <id>` - Delete a routine",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    subcommand = context.args[0].lower()
    remaining = " ".join(context.args[1:])

    if subcommand == "list":
        await _handle_routine_list(update, context, config)
    elif subcommand == "add":
        parser = CommandParser()
        parsed = parser.routine_parser.parse(f"take {remaining}")
        if not parsed:
            await update.message.reply_text(
                "Could not parse routine. Try:\n" "`/routine add Napa at 08:00 daily before meal`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        await _handle_routine_from_text(update, context, parsed, config)
    elif subcommand in ("pause", "resume", "delete"):
        if not remaining or not remaining.strip().isdigit():
            await update.message.reply_text(
                f"Please provide a routine ID: `/routine {subcommand} <id>`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        routine_id = int(remaining.strip())
        await _handle_routine_action(update, context, config, subcommand, routine_id)
    else:
        await update.message.reply_text(
            "Unknown subcommand. Use: `add`, `list`, `pause`, `resume`, `delete`",
            parse_mode=ParseMode.MARKDOWN,
        )


async def _handle_routine_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, config: Settings
) -> None:
    """List active routines."""
    group_chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    async with Database(config.database_path) as db:
        repo = RoutineRepository(db)
        routines = await repo.get_user_routines(user_id, group_chat_id)

    if not routines:
        await update.message.reply_text(
            "No routines set up yet.\n" "Add one with: `/routine add Napa at 08:00 daily`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    response = format_routine_list(routines)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


async def _handle_routine_from_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed, config: Settings
) -> None:
    """Create a routine from parsed command."""
    if not parsed.medicine_name:
        await update.message.reply_text("Please specify a medicine name for the routine.")
        return

    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Unknown"
    group_chat_id = update.effective_chat.id

    data = RoutineData(
        medicine_name=parsed.medicine_name,
        dosage_quantity=parsed.quantity or 1,
        dosage_unit=parsed.unit,
        frequency=parsed.frequency or "daily",
        times_of_day=parsed.schedule_times or ["08:00"],
        meal_relation=parsed.meal_relation,
        created_by_user_id=user_id,
        created_by_username=username,
        group_chat_id=group_chat_id,
    )

    from src.services.routine_service import RoutineService

    scheduler = context.bot_data.get("scheduler")
    svc = RoutineService(config.database_path, scheduler)
    routine = await svc.create_routine(data)

    times_str = ", ".join(routine.times_of_day)
    response = f" Routine created!\n\n"
    response += format_routine_detail(routine)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


async def _handle_routine_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    config: Settings,
    action: str,
    routine_id: int,
) -> None:
    """Handle pause/resume/delete routine actions."""
    from src.services.routine_service import RoutineService

    scheduler = context.bot_data.get("scheduler")
    svc = RoutineService(config.database_path, scheduler)

    if action == "pause":
        routine = await svc.pause_routine(routine_id)
        if routine:
            await update.message.reply_text(
                f" Paused routine #{routine_id} ({routine.medicine_name})",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(f"Routine #{routine_id} not found.")
    elif action == "resume":
        routine = await svc.resume_routine(routine_id)
        if routine:
            await update.message.reply_text(
                f" Resumed routine #{routine_id} ({routine.medicine_name})",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(f"Routine #{routine_id} not found.")
    elif action == "delete":
        deleted = await svc.delete_routine(routine_id)
        if deleted:
            await update.message.reply_text(f" Deleted routine #{routine_id}")
        else:
            await update.message.reply_text(f"Routine #{routine_id} not found.")


async def handle_routine_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard callbacks for routine Taken/Skip buttons."""
    query = update.callback_query
    await query.answer()

    config: Settings = context.bot_data["config"]
    data = query.data  # e.g., "routine_taken_123_456" or "routine_skip_123_456"
    parts = data.split("_")

    if len(parts) < 4:
        return

    action = parts[1]  # "taken" or "skip"
    log_id = int(parts[2])
    routine_id = int(parts[3])

    from src.services.routine_service import RoutineService

    scheduler = context.bot_data.get("scheduler")
    svc = RoutineService(config.database_path, scheduler)

    if action == "taken":
        log_entry = await svc.mark_taken(log_id, routine_id)
        username = update.effective_user.first_name or "Someone"
        await query.edit_message_text(
            f"{query.message.text}\n\n *{username}* took this dose!",
            parse_mode=ParseMode.MARKDOWN,
        )
    elif action == "skip":
        await svc.mark_skipped(log_id)
        await query.edit_message_text(
            f"{query.message.text}\n\n Dose skipped.",
            parse_mode=ParseMode.MARKDOWN,
        )


# --- Phase 4: Interaction handlers ---


async def handle_check_interactions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /interactions command."""
    config: Settings = context.bot_data["config"]

    if not context.args:
        await update.message.reply_text(
            "Check drug interactions:\n" "`/interactions Napa` - Check Napa against your cabinet",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    drug_name = " ".join(context.args)
    group_chat_id = update.effective_chat.id

    from src.services.interaction_service import InteractionService

    svc = InteractionService(config.database_path)
    interactions = await svc.check_against_cabinet(drug_name, group_chat_id)

    if not interactions:
        await update.message.reply_text(
            f"No known interactions found for *{drug_name}* " f"with medicines in your cabinet.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    warning = format_interaction_warning(interactions)
    await update.message.reply_text(warning, parse_mode=ParseMode.MARKDOWN)


# --- Phase 5: Cost handlers ---


async def handle_add_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cost command to add a cost entry."""
    config: Settings = context.bot_data["config"]

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Add medicine cost:\n"
            "`/cost Napa 50` - Napa cost 50 BDT\n"
            '`/cost "Napa Extra" 120` - Quoted names with spaces',
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Parse args: medicine_name amount
    *name_parts, amount_str = context.args
    medicine_name = " ".join(name_parts).strip('"').strip("'")

    try:
        amount = float(amount_str.replace("tk", "").replace("taka", "").strip())
    except ValueError:
        await update.message.reply_text(
            "Invalid amount. Example: `/cost Napa 50`", parse_mode=ParseMode.MARKDOWN
        )
        return

    group_chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Unknown"

    async with Database(config.database_path) as db:
        medicine_repo = MedicineRepository(db)
        cost_repo = CostRepository(db)

        # Find medicine
        matches = await medicine_repo.find_by_name_fuzzy(
            medicine_name, group_chat_id, threshold=config.fuzzy_match_threshold
        )
        if not matches:
            await update.message.reply_text(
                f"Medicine *{medicine_name}* not found in cabinet. "
                f"Add it first with `+{medicine_name} <quantity>`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        medicine = matches[0][0]
        cost_data = CostData(
            medicine_id=medicine.id,
            total_cost=amount,
            user_id=user_id,
            username=username,
            group_chat_id=group_chat_id,
            currency=config.default_currency,
        )
        await cost_repo.add_cost(cost_data)

    await update.message.reply_text(
        f" Cost recorded: *{medicine.name}* - {amount} {config.default_currency}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def _handle_cost_from_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed, config: Settings
) -> None:
    """Handle cost command from natural language parsing."""
    if not parsed.medicine_name or parsed.cost is None:
        return

    group_chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Unknown"

    async with Database(config.database_path) as db:
        medicine_repo = MedicineRepository(db)
        cost_repo = CostRepository(db)

        matches = await medicine_repo.find_by_name_fuzzy(
            parsed.medicine_name, group_chat_id, threshold=config.fuzzy_match_threshold
        )
        if not matches:
            await update.message.reply_text(
                f"Medicine *{parsed.medicine_name}* not found in cabinet.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        medicine = matches[0][0]
        cost_data = CostData(
            medicine_id=medicine.id,
            total_cost=parsed.cost,
            user_id=user_id,
            username=username,
            group_chat_id=group_chat_id,
            currency=config.default_currency,
        )
        await cost_repo.add_cost(cost_data)

    await update.message.reply_text(
        f" Cost recorded: *{medicine.name}* - {parsed.cost} {config.default_currency}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_cost_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /costs command to show cost summary."""
    config: Settings = context.bot_data["config"]
    group_chat_id = update.effective_chat.id

    async with Database(config.database_path) as db:
        cost_repo = CostRepository(db)
        summary = await cost_repo.get_cost_summary(group_chat_id, days=30)

    response = format_cost_summary(summary, config.default_currency)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


# --- Phase 3: Photo handler ---


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages - extract medicine info using vision LLM."""
    config: Settings = context.bot_data["config"]
    llm_provider = context.bot_data.get("llm_provider")

    if not llm_provider or not llm_provider.supports_vision:
        await update.message.reply_text(
            "Photo processing requires an LLM provider with vision support.\n"
            "Set `LLM_PROVIDER=groq` and `LLM_API_KEY=...` in your .env file.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Get photo (largest available)
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    # Download as bytes
    photo_bytes = await file.download_as_bytearray()

    await update.message.reply_text("Analyzing medicine photo...")

    from src.services.image_service import ImageService

    svc = ImageService(llm_provider)
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Unknown"
    group_chat_id = update.effective_chat.id

    medicines = await svc.extract_from_photo(bytes(photo_bytes), user_id, username, group_chat_id)

    if not medicines:
        await update.message.reply_text(
            "Could not identify any medicines in this photo. "
            "Try with a clearer image of the medicine packet."
        )
        return

    # Add extracted medicines
    async with Database(config.database_path) as db:
        medicine_repo = MedicineRepository(db)
        activity_repo = ActivityLogRepository(db)

        results = []
        for med_data in medicines:
            medicine = await medicine_repo.add_medicine(med_data)
            await activity_repo.log_activity(
                medicine_id=medicine.id,
                action="added",
                user_id=user_id,
                username=username,
                group_chat_id=group_chat_id,
                quantity_change=med_data.quantity,
            )
            results.append(medicine)

    response = f" Found and added {len(results)} medicine(s) from photo:\n\n"
    for med in results:
        response += f" *{med.name}* - {med.quantity} {med.unit}\n"

    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


# --- Phase 5: Analytics handler ---


async def handle_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /analytics command."""
    config: Settings = context.bot_data["config"]
    group_chat_id = update.effective_chat.id

    from src.services.analytics_service import AnalyticsService

    svc = AnalyticsService(config.database_path)
    report = await svc.get_full_report(group_chat_id, days=30)

    response = format_analytics_report(report)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
