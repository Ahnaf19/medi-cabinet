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
    MedicineData,
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

    # Route to appropriate handler
    if parsed.command_type == "add":
        await handle_add_medicine(update, context, parsed, config)
    elif parsed.command_type == "use":
        await handle_use_medicine(update, context, parsed, config)
    elif parsed.command_type == "search":
        await handle_search_medicine(update, context, parsed, config)
    elif parsed.command_type == "list":
        await handle_list_all(update, context, config)
    else:
        await update.message.reply_text(
            " Sorry, I didn't understand that command.\n\n"
            "Try:\n"
            "`+Napa 10` to add medicine\n"
            "`-Napa 2` to use medicine\n"
            "`?Napa` to search\n"
            "`?all` to list all\n"
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

    Args:
        context: Bot context
    """
    config: Settings = context.bot_data["config"]

    # This would need to iterate through all groups
    # For now, we'll skip the proactive notification
    # In production, you'd maintain a list of active group chats
    logger.info("Scheduled expiry check would run here")


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
