"""Main bot application class."""

import sys
from datetime import time
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)
from loguru import logger

from config.config import Settings
from src.commands import (
    handle_start,
    handle_help,
    handle_message,
    handle_delete_medicine,
    handle_stats,
    handle_error,
    scheduled_expiry_check,
    scheduled_backup,
)


class MediCabinetBot:
    """Main bot application class."""

    def __init__(self, config: Settings):
        """Initialize bot with configuration.

        Args:
            config: Settings instance
        """
        self.config = config
        self.app = None

        # Configure logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Setup loguru logging configuration."""
        # Remove default handler
        logger.remove()

        # Console handler
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=self.config.log_level,
        )

        # File handler with rotation
        logger.add(
            "logs/medi-cabinet_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=self.config.log_level,
            rotation="500 MB",
            retention="10 days",
            compression="zip",
        )

        logger.info("Logging configured")

    def _register_handlers(self) -> None:
        """Register all command and message handlers."""
        # Command handlers
        self.app.add_handler(CommandHandler("start", handle_start))
        self.app.add_handler(CommandHandler("help", handle_help))
        self.app.add_handler(CommandHandler("delete", handle_delete_medicine))
        self.app.add_handler(CommandHandler("stats", handle_stats))

        # Message handler for natural text
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

        # Error handler
        self.app.add_error_handler(handle_error)

        logger.info("Handlers registered")

    def _setup_jobs(self) -> None:
        """Setup scheduled jobs."""
        if not self.app.job_queue:
            logger.warning("Job queue not available, skipping scheduled jobs")
            return

        # Daily expiry check at 9 AM
        self.app.job_queue.run_daily(
            scheduled_expiry_check,
            time=time(hour=9, minute=0),
            name="expiry_check",
        )

        # Daily database backup at 3 AM
        self.app.job_queue.run_daily(
            scheduled_backup,
            time=time(hour=3, minute=0),
            name="database_backup",
        )

        logger.info("Scheduled jobs configured")

    async def post_init(self, application: Application) -> None:
        """Post initialization hook.

        Args:
            application: Application instance
        """
        # Store config in bot_data for access in handlers
        application.bot_data["config"] = self.config
        logger.info("Bot initialized successfully")

    async def post_shutdown(self, application: Application) -> None:
        """Post shutdown hook.

        Args:
            application: Application instance
        """
        logger.info("Bot shutdown complete")

    def run(self) -> None:
        """Run the bot (blocking)."""
        try:
            logger.info("Starting Medi-Cabinet Bot...")
            logger.info(f"Database: {self.config.database_path}")
            logger.info(f"Admin users: {self.config.admin_user_ids}")

            # Build application
            self.app = (
                Application.builder()
                .token(self.config.telegram_bot_token)
                .post_init(self.post_init)
                .post_shutdown(self.post_shutdown)
                .build()
            )

            # Register handlers and jobs
            self._register_handlers()
            self._setup_jobs()

            # Start the bot
            logger.info("Bot is now running. Press Ctrl+C to stop.")
            self.app.run_polling(allowed_updates=None)

        except Exception as e:
            logger.exception("Fatal error occurred")
            raise

    async def start_async(self) -> None:
        """Start the bot asynchronously (non-blocking).

        Useful for testing or running alongside other async operations.
        """
        logger.info("Starting Medi-Cabinet Bot (async mode)...")

        # Build application
        self.app = (
            Application.builder()
            .token(self.config.telegram_bot_token)
            .post_init(self.post_init)
            .post_shutdown(self.post_shutdown)
            .build()
        )

        # Register handlers and jobs
        self._register_handlers()
        self._setup_jobs()

        # Initialize and start
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(allowed_updates=None)

        logger.info("Bot started successfully (async mode)")

    async def stop_async(self) -> None:
        """Stop the bot asynchronously.

        Useful for testing or graceful shutdown.
        """
        if self.app:
            logger.info("Stopping bot...")
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            logger.info("Bot stopped successfully")
