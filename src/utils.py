"""Utility functions for the medi-cabinet bot."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dateutil import parser as date_parser

from config.config import Settings
from src.database import Medicine, Activity


def format_medicine_list(medicines: List[Medicine], low_stock_threshold: int = 3) -> str:
    """Format a list of medicines for display.

    Args:
        medicines: List of Medicine entities
        low_stock_threshold: Threshold for low stock warning

    Returns:
        Formatted string for display
    """
    if not medicines:
        return "No medicines found in cabinet."

    lines = []
    for medicine in medicines:
        # Stock status emoji
        stock_emoji = get_stock_status_emoji(medicine.quantity, low_stock_threshold)

        # Medicine line
        line = f"{stock_emoji} *{medicine.name}* - {medicine.quantity} {medicine.unit}"

        # Add expiry warning if applicable
        if medicine.expiry_date:
            days_until_expiry = calculate_days_until_expiry(medicine.expiry_date)
            if days_until_expiry <= 0:
                line += f" (EXPIRED {format_date(medicine.expiry_date)})"
            elif days_until_expiry <= 30:
                line += f" (Expires {format_date(medicine.expiry_date)})"

        # Add location if available
        if medicine.location:
            line += f" - {medicine.location}"

        lines.append(line)

    return "\n".join(lines)


def format_medicine_detail(medicine: Medicine) -> str:
    """Format detailed medicine information.

    Args:
        medicine: Medicine entity

    Returns:
        Formatted string with all details
    """
    lines = [
        f"*{medicine.name}*",
        f"Quantity: {medicine.quantity} {medicine.unit}",
    ]

    if medicine.expiry_date:
        days_until_expiry = calculate_days_until_expiry(medicine.expiry_date)
        expiry_status = "EXPIRED" if days_until_expiry <= 0 else "Expires"
        lines.append(f"Expiry: {expiry_status} {format_date(medicine.expiry_date)}")

    if medicine.location:
        lines.append(f"Location: {medicine.location}")

    lines.append(f"Added by: {medicine.added_by_username}")
    lines.append(f"Added on: {format_date(medicine.added_date)}")

    return "\n".join(lines)


def format_date(date: datetime) -> str:
    """Format datetime for human-readable display.

    Args:
        date: Datetime to format

    Returns:
        Formatted date string
    """
    now = datetime.now()
    diff = now - date

    if diff.days == 0:
        return "Today"
    elif diff.days == 1:
        return "Yesterday"
    elif diff.days < 7:
        return f"{diff.days} days ago"
    elif diff.days < 30:
        weeks = diff.days // 7
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    else:
        return date.strftime("%b %d, %Y")


def parse_date_flexible(date_str: str) -> Optional[datetime]:
    """Parse date string in various formats.

    Args:
        date_str: Date string to parse

    Returns:
        Parsed datetime or None if parsing fails
    """
    try:
        return date_parser.parse(date_str, fuzzy=True)
    except (ValueError, date_parser.ParserError):
        return None


def is_admin(user_id: int, config: Settings) -> bool:
    """Check if user is an admin.

    Args:
        user_id: Telegram user ID
        config: Settings instance

    Returns:
        True if user is admin, False otherwise
    """
    return user_id in config.admin_user_ids


def calculate_days_until_expiry(expiry_date: datetime) -> int:
    """Calculate days until medicine expiry.

    Args:
        expiry_date: Expiry datetime

    Returns:
        Number of days until expiry (negative if expired)
    """
    now = datetime.now()
    diff = expiry_date - now
    return diff.days


def get_stock_status_emoji(quantity: int, threshold: int) -> str:
    """Get emoji representing stock status.

    Args:
        quantity: Current quantity
        threshold: Low stock threshold

    Returns:
        Emoji string
    """
    if quantity == 0:
        return ""
    elif quantity < threshold:
        return ""
    else:
        return ""


def sanitize_medicine_name(name: str) -> str:
    """Sanitize medicine name by removing special characters.

    Args:
        name: Medicine name

    Returns:
        Sanitized name
    """
    # Remove special characters but keep spaces and hyphens
    import re

    sanitized = re.sub(r"[^\w\s-]", "", name)
    # Remove extra spaces
    sanitized = " ".join(sanitized.split())
    return sanitized.title()


def generate_usage_stats(stats_data: Dict[str, Any]) -> str:
    """Generate formatted usage statistics message.

    Args:
        stats_data: Statistics dictionary from database

    Returns:
        Formatted statistics string
    """
    lines = [
        f"*Usage Statistics (Last {stats_data['period_days']} days)*\n",
        f"Total Activities: {stats_data['total_activities']}",
    ]

    # Activities by action
    if stats_data.get("activities_by_action"):
        lines.append("\n*Activities by Type:*")
        for action, count in stats_data["activities_by_action"].items():
            emoji = {
                "added": "",
                "used": "",
                "searched": "",
                "deleted": "",
            }.get(action, "")
            lines.append(f"{emoji} {action.title()}: {count}")

    # Most active users
    if stats_data.get("most_active_users"):
        lines.append("\n*Most Active Users:*")
        for idx, user_data in enumerate(stats_data["most_active_users"], 1):
            lines.append(f"{idx}. {user_data['username']} ({user_data['count']} activities)")

    # Most used medicines
    if stats_data.get("most_used_medicines"):
        lines.append("\n*Most Used Medicines:*")
        for idx, med_data in enumerate(stats_data["most_used_medicines"], 1):
            lines.append(f"{idx}. {med_data['name']} ({med_data['usage_count']} times)")

    return "\n".join(lines)


def format_activity_history(activities: List[Activity]) -> str:
    """Format activity history for display.

    Args:
        activities: List of Activity entities

    Returns:
        Formatted history string
    """
    if not activities:
        return "No activity history available."

    lines = ["*Recent Activity:*\n"]

    for activity in activities[:10]:  # Show last 10 activities
        emoji = {
            "added": "",
            "used": "",
            "searched": "",
            "deleted": "",
        }.get(activity.action, "")

        line = f"{emoji} {activity.action.title()}"

        if activity.quantity_change:
            sign = "+" if activity.quantity_change > 0 else ""
            line += f" {sign}{activity.quantity_change}"

        line += f" by {activity.username}"
        line += f" ({format_date(activity.timestamp)})"

        lines.append(line)

    return "\n".join(lines)


def build_confirmation_keyboard(callback_data: str) -> Dict[str, Any]:
    """Build inline keyboard for confirmation.

    Args:
        callback_data: Callback data for the action

    Returns:
        Inline keyboard markup
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("Confirm", callback_data=f"confirm:{callback_data}"),
            InlineKeyboardButton("Cancel", callback_data="cancel"),
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def build_medicine_selection_keyboard(
    medicines: List[tuple], prefix: str = "select"
) -> Dict[str, Any]:
    """Build inline keyboard for medicine selection.

    Args:
        medicines: List of (medicine, confidence) tuples
        prefix: Callback data prefix

    Returns:
        Inline keyboard markup
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = []

    for idx, (medicine, confidence) in enumerate(medicines[:5], 1):  # Max 5 options
        button_text = f"{idx}. {medicine.name} ({medicine.quantity} {medicine.unit})"
        if confidence < 100:
            button_text += f" - {confidence}% match"

        keyboard.append(
            [
                InlineKeyboardButton(
                    button_text, callback_data=f"{prefix}:{medicine.id}"
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])

    return InlineKeyboardMarkup(keyboard)


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    # Characters that need to be escaped in MarkdownV2
    special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]

    for char in special_chars:
        text = text.replace(char, f"\\{char}")

    return text


def format_low_stock_alert(medicines: List[Medicine]) -> str:
    """Format low stock alert message.

    Args:
        medicines: List of low-stock medicines

    Returns:
        Formatted alert message
    """
    if not medicines:
        return ""

    lines = [" *Low Stock Alert!*\n"]

    for medicine in medicines:
        lines.append(
            f" *{medicine.name}* - Only {medicine.quantity} {medicine.unit} left!"
        )

    return "\n".join(lines)


def format_expiry_warning(medicines: List[Medicine]) -> str:
    """Format expiry warning message.

    Args:
        medicines: List of expiring medicines

    Returns:
        Formatted warning message
    """
    if not medicines:
        return ""

    lines = [" *Expiry Warning!*\n"]

    for medicine in medicines:
        days_until_expiry = calculate_days_until_expiry(medicine.expiry_date)

        if days_until_expiry <= 0:
            status = "EXPIRED"
        elif days_until_expiry == 1:
            status = "Expires tomorrow"
        else:
            status = f"Expires in {days_until_expiry} days"

        lines.append(f" *{medicine.name}* - {status}")

    return "\n".join(lines)


def get_welcome_message() -> str:
    """Get welcome message for /start command.

    Returns:
        Welcome message
    """
    return """
 *Welcome to Medi-Cabinet Bot!*

I help your family track leftover medicines to reduce waste.

*Quick Commands:*
Add medicine: `+Napa 10` or `Bought Napa Extra 10 tablets`
Use medicine: `-Napa 2` or `Used 2 Napa`
Search: `?Napa` or `Do we have Napa?`
List all: `?all` or `list medicines`
Delete: `/delete Napa` (admin only)
Statistics: `/stats`

*Natural Language Support:*
Just type naturally! I understand phrases like:
- "Got paracetamol, 12"
- "Took some Napa"
- "Check if we have Sergel"

Type `/help` for more details!
    """.strip()


def get_help_message() -> str:
    """Get detailed help message.

    Returns:
        Help message with examples
    """
    return """
 *Medi-Cabinet Bot - Help*

*Adding Medicines:*
`+Napa 10` - Add 10 tablets of Napa
`Bought Napa Extra 20 tablets` - Natural language
`Got paracetamol, 12, expires Dec 2025` - With expiry
`Added Napa 10 tablets in bedroom drawer` - With location

*Using Medicines:*
`-Napa 2` - Use 2 tablets of Napa
`Used 2 Napa` - Natural language
`Took some paracetamol` - Use 1 (default for "some")

*Searching:*
`?Napa` - Search for Napa
`Do we have Napa?` - Natural question
`Check sergel` - Check if Sergel is available

*Listing:*
`?all` - List all medicines
`list medicines` - Show everything
`inventory` - Show inventory

*Admin Commands:*
`/delete Napa` - Delete a medicine (admin only)
`/stats` - Show usage statistics

*Features:*
Fuzzy matching for typos
Low stock alerts (< 3 tablets)
Expiry warnings (< 30 days)
Activity history tracking
Multi-group support

Need help? Just ask naturally!
    """.strip()
