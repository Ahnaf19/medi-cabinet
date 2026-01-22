"""Pytest configuration and fixtures."""

import pytest
import asyncio
from datetime import datetime
from pathlib import Path

from config.config import Settings
from src.database import Database, MedicineRepository, ActivityLogRepository, MedicineData


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config():
    """Create test configuration."""
    return Settings(
        telegram_bot_token="test_token",
        database_path=":memory:",  # Use in-memory database for tests
        log_level="DEBUG",
        admin_user_ids=[123456],
        low_stock_threshold=3,
        expiry_warning_days=30,
        fuzzy_match_threshold=80,
    )


@pytest.fixture
async def test_db():
    """Create test database with schema."""
    db_path = ":memory:"

    async with Database(db_path) as db:
        # Create tables manually for in-memory database
        await db.execute("""
            CREATE TABLE medicines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE,
                quantity INTEGER NOT NULL DEFAULT 0,
                unit TEXT DEFAULT 'tablets',
                expiry_date DATE NULL,
                location TEXT NULL,
                added_by_user_id INTEGER NOT NULL,
                added_by_username TEXT NOT NULL,
                added_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                group_chat_id INTEGER NOT NULL,
                last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_chat_id, name COLLATE NOCASE)
            )
        """)

        await db.execute("""
            CREATE INDEX idx_medicines_group_name
            ON medicines(group_chat_id, name COLLATE NOCASE)
        """)

        await db.execute("""
            CREATE TABLE activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                quantity_change INTEGER NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                group_chat_id INTEGER NOT NULL,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE,
                CHECK (action IN ('added', 'used', 'searched', 'deleted'))
            )
        """)

        await db.execute("""
            CREATE INDEX idx_activity_timestamp
            ON activity_log(timestamp DESC)
        """)

        yield db


@pytest.fixture
async def medicine_repo(test_db):
    """Create medicine repository."""
    return MedicineRepository(test_db)


@pytest.fixture
async def activity_repo(test_db):
    """Create activity log repository."""
    return ActivityLogRepository(test_db)


@pytest.fixture
def sample_medicine_data():
    """Create sample medicine data."""
    return MedicineData(
        name="Napa",
        quantity=10,
        unit="tablets",
        expiry_date=None,
        location=None,
        added_by_user_id=123456,
        added_by_username="TestUser",
        group_chat_id=789012,
    )


@pytest.fixture
def sample_medicines_list():
    """Create list of sample medicines for testing."""
    return [
        {
            "name": "Napa",
            "quantity": 10,
            "unit": "tablets",
            "group_chat_id": 789012,
        },
        {
            "name": "Napa Extra",
            "quantity": 5,
            "unit": "tablets",
            "group_chat_id": 789012,
        },
        {
            "name": "Sergel",
            "quantity": 2,
            "unit": "tablets",
            "group_chat_id": 789012,
        },
    ]
