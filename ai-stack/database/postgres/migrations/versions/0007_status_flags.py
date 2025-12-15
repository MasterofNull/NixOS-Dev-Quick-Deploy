"""Add status flags to skills and documents

Revision ID: 0007_status_flags
Revises: 0006_codemachine_workflows
Create Date: 2025-11-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007_status_flags"
down_revision = "0006_codemachine_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "open_skills",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="approved",
        ),
    )
    op.add_column(
        "imported_documents",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="approved",
        ),
    )
    op.execute("UPDATE open_skills SET status = 'approved' WHERE status IS NULL")
    op.execute("UPDATE imported_documents SET status = 'approved' WHERE status IS NULL")


def downgrade() -> None:
    op.drop_column("open_skills", "status")
    op.drop_column("imported_documents", "status")
