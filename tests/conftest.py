"""Pytest configuration and fixtures."""

import pytest
import asyncio
from datetime import datetime
from pathlib import Path

from config.config import Settings
from src.database import (
    Database,
    MedicineRepository,
    ActivityLogRepository,
    RoutineRepository,
    RoutineLogRepository,
    DrugInteractionRepository,
    CostRepository,
    MedicineData,
    RoutineData,
    CostData,
)


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
        await db.execute(
            """
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
        """
        )

        await db.execute(
            """
            CREATE INDEX idx_medicines_group_name
            ON medicines(group_chat_id, name COLLATE NOCASE)
        """
        )

        await db.execute(
            """
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
        """
        )

        await db.execute(
            """
            CREATE INDEX idx_activity_timestamp
            ON activity_log(timestamp DESC)
        """
        )

        # Phase 4: Routines tables
        await db.execute(
            """
            CREATE TABLE routines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id INTEGER NULL,
                medicine_name TEXT NOT NULL COLLATE NOCASE,
                dosage_quantity INTEGER NOT NULL DEFAULT 1,
                dosage_unit TEXT NOT NULL DEFAULT 'tablets',
                frequency TEXT NOT NULL DEFAULT 'daily',
                times_of_day TEXT NOT NULL DEFAULT '["08:00"]',
                days_of_week TEXT NULL,
                meal_relation TEXT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT NULL,
                created_by_user_id INTEGER NOT NULL,
                created_by_username TEXT NOT NULL,
                group_chat_id INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                start_date DATE NULL,
                end_date DATE NULL,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE SET NULL
            )
        """
        )

        await db.execute(
            """
            CREATE TABLE routine_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                routine_id INTEGER NOT NULL,
                scheduled_time TIMESTAMP NOT NULL,
                actual_time TIMESTAMP NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                group_chat_id INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (routine_id) REFERENCES routines(id) ON DELETE CASCADE
            )
        """
        )

        # Phase 4: Drug interactions table
        await db.execute(
            """
            CREATE TABLE drug_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_a_name TEXT NOT NULL COLLATE NOCASE,
                drug_b_name TEXT NOT NULL COLLATE NOCASE,
                severity TEXT NOT NULL DEFAULT 'mild',
                description TEXT NOT NULL,
                source TEXT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(drug_a_name, drug_b_name)
            )
        """
        )

        # Phase 5: Cost tracking table
        await db.execute(
            """
            CREATE TABLE medicine_costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id INTEGER NOT NULL,
                cost_per_unit REAL NULL,
                currency TEXT NOT NULL DEFAULT 'BDT',
                purchase_date DATE NULL,
                total_quantity INTEGER NULL,
                total_cost REAL NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                group_chat_id INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
            )
        """
        )

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


@pytest.fixture
async def routine_repo(test_db):
    """Create routine repository."""
    return RoutineRepository(test_db)


@pytest.fixture
async def routine_log_repo(test_db):
    """Create routine log repository."""
    return RoutineLogRepository(test_db)


@pytest.fixture
async def interaction_repo(test_db):
    """Create drug interaction repository."""
    return DrugInteractionRepository(test_db)


@pytest.fixture
async def cost_repo(test_db):
    """Create cost repository."""
    return CostRepository(test_db)


@pytest.fixture
def sample_routine_data():
    """Create sample routine data."""
    return RoutineData(
        medicine_name="Napa",
        dosage_quantity=1,
        dosage_unit="tablets",
        frequency="daily",
        times_of_day=["08:00", "20:00"],
        meal_relation="after_meal",
        created_by_user_id=123456,
        created_by_username="TestUser",
        group_chat_id=789012,
    )
