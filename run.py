"""Entry point for Medi-Cabinet Bot."""

import sys
from pathlib import Path

from loguru import logger

from config.config import get_settings
from src.bot import MediCabinetBot


def main() -> None:
    """Main entry point."""
    try:
        # Load configuration
        config = get_settings()

        # Ensure logs directory exists
        Path("logs").mkdir(exist_ok=True)

        # Ensure backups directory exists
        Path("backups").mkdir(exist_ok=True)

        # Create and run bot
        bot = MediCabinetBot(config)
        bot.run()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.exception("Fatal error in main")
        sys.exit(1)


if __name__ == "__main__":
    main()
