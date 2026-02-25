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
    # Baseline revision already includes llm_used for fresh installs.
    # Keep this migration idempotent for mixed historical states.
    op.execute("ALTER TABLE telemetry_events ADD COLUMN IF NOT EXISTS llm_used VARCHAR(32)")


def downgrade() -> None:
    op.execute("ALTER TABLE telemetry_events DROP COLUMN IF EXISTS llm_used")
