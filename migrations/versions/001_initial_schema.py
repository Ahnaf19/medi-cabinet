"""Initial database schema with medicines and activity_log tables

Revision ID: 001
Revises:
Create Date: 2026-01-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create medicines and activity_log tables with indexes."""

    # Create medicines table
    op.execute('''
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
    ''')

    # Create indexes for medicines table
    op.create_index(
        'idx_medicines_group_name',
        'medicines',
        ['group_chat_id', 'name'],
    )

    op.execute('''
        CREATE INDEX idx_medicines_expiry
        ON medicines(expiry_date)
        WHERE expiry_date IS NOT NULL
    ''')

    op.execute('''
        CREATE INDEX idx_medicines_low_stock
        ON medicines(quantity)
        WHERE quantity < 3
    ''')

    # Create activity_log table
    op.execute('''
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
    ''')

    # Create indexes for activity_log table
    op.create_index(
        'idx_activity_timestamp',
        'activity_log',
        ['timestamp'],
    )

    op.create_index(
        'idx_activity_medicine',
        'activity_log',
        ['medicine_id'],
    )

    op.create_index(
        'idx_activity_group',
        'activity_log',
        ['group_chat_id'],
    )


def downgrade() -> None:
    """Drop all tables and indexes."""
    op.drop_table('activity_log')
    op.drop_table('medicines')
