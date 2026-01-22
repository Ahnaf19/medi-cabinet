"""Configuration management using Pydantic Settings."""

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Bot Configuration
    telegram_bot_token: str = Field(
        ...,
        description="Telegram bot token from @BotFather",
    )

    # Database Configuration
    database_path: str = Field(
        default="medi-cabinet.db",
        description="Path to SQLite database file",
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # Admin Configuration
    admin_user_ids: List[int] = Field(
        default_factory=list,
        description="List of Telegram user IDs with admin privileges",
    )

    # Medicine Tracking Configuration
    low_stock_threshold: int = Field(
        default=3,
        ge=0,
        description="Threshold for low stock alerts (number of units)",
    )

    expiry_warning_days: int = Field(
        default=30,
        ge=1,
        description="Number of days before expiry to show warnings",
    )

    fuzzy_match_threshold: int = Field(
        default=80,
        ge=0,
        le=100,
        description="Fuzzy matching threshold for medicine names (0-100)",
    )

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admin_user_ids(cls, value):
        """Parse comma-separated admin user IDs from environment variable."""
        if isinstance(value, str):
            if not value.strip():
                return []
            return [int(uid.strip()) for uid in value.split(",") if uid.strip()]
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Validate and normalize log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        value_upper = value.upper()
        if value_upper not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return value_upper


# Singleton instance
_settings_instance = None


def get_settings() -> Settings:
    """Get or create settings singleton instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
