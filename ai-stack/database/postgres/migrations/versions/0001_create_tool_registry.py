from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_create_tool_registry"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_registry",
        sa.Column("name", sa.String(length=256), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("cost_estimate_tokens", sa.Integer(), nullable=False, server_default="2000"),
    )


def downgrade() -> None:
    op.drop_table("tool_registry")
