"""Add medicine_costs table for cost tracking.

Revision ID: 004
Revises: 003
Create Date: 2026-03-06 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create medicine_costs table."""

    op.execute("""
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
    """)

    op.create_index("idx_costs_medicine", "medicine_costs", ["medicine_id"])
    op.create_index("idx_costs_group", "medicine_costs", ["group_chat_id"])


def downgrade() -> None:
    """Drop medicine_costs table."""
    op.drop_table("medicine_costs")
