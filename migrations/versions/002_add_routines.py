"""Add routines and routine_logs tables for medicine scheduling.

Revision ID: 002
Revises: 001
Create Date: 2026-03-06 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create routines and routine_logs tables."""

    op.execute("""
        CREATE TABLE routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NULL,
            medicine_name TEXT NOT NULL COLLATE NOCASE,
            dosage_quantity INTEGER NOT NULL DEFAULT 1,
            dosage_unit TEXT NOT NULL DEFAULT 'tablets',
            frequency TEXT NOT NULL DEFAULT 'daily'
                CHECK (frequency IN ('daily', 'weekly', 'every_other_day', 'custom')),
            times_of_day TEXT NOT NULL DEFAULT '["08:00"]',
            days_of_week TEXT NULL,
            meal_relation TEXT NULL
                CHECK (meal_relation IN ('before_meal', 'after_meal', 'with_meal', NULL)),
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'paused', 'completed')),
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
    """)

    op.create_index("idx_routines_group", "routines", ["group_chat_id"])
    op.create_index("idx_routines_user", "routines", ["created_by_user_id"])
    op.create_index("idx_routines_active", "routines", ["status"])
    op.create_index("idx_routines_medicine", "routines", ["medicine_id"])

    op.execute("""
        CREATE TABLE routine_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            routine_id INTEGER NOT NULL,
            scheduled_time TIMESTAMP NOT NULL,
            actual_time TIMESTAMP NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'taken', 'missed', 'skipped')),
            group_chat_id INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (routine_id) REFERENCES routines(id) ON DELETE CASCADE
        )
    """)

    op.create_index("idx_routine_logs_routine", "routine_logs", ["routine_id"])
    op.create_index("idx_routine_logs_status", "routine_logs", ["status"])


def downgrade() -> None:
    """Drop routines and routine_logs tables."""
    op.drop_table("routine_logs")
    op.drop_table("routines")
