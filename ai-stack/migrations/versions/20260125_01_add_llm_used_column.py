"""Add llm_used column to telemetry_events if missing.

Revision ID: 20260125_01
Revises: 20260109_02
Create Date: 2026-01-25
"""

from alembic import op
import sqlalchemy as sa

revision = "20260125_01"
down_revision = "20260109_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("telemetry_events", sa.Column("llm_used", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("telemetry_events", "llm_used")
