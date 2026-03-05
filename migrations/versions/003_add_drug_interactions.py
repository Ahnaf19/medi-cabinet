"""Add drug_interactions table.

Revision ID: 003
Revises: 002
Create Date: 2026-03-06 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create drug_interactions table."""

    op.execute("""
        CREATE TABLE drug_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_a_name TEXT NOT NULL COLLATE NOCASE,
            drug_b_name TEXT NOT NULL COLLATE NOCASE,
            severity TEXT NOT NULL DEFAULT 'mild'
                CHECK (severity IN ('mild', 'moderate', 'severe', 'contraindicated')),
            description TEXT NOT NULL,
            source TEXT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(drug_a_name, drug_b_name)
        )
    """)

    op.create_index(
        "idx_interactions_drug_a", "drug_interactions", ["drug_a_name"]
    )
    op.create_index(
        "idx_interactions_drug_b", "drug_interactions", ["drug_b_name"]
    )


def downgrade() -> None:
    """Drop drug_interactions table."""
    op.drop_table("drug_interactions")
