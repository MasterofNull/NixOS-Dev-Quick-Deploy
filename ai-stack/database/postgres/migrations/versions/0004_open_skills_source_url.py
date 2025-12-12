from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_open_skills_source_url"
down_revision = "0003_open_skills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("open_skills", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("open_skills", sa.Column("managed_by", sa.String(length=32), nullable=False, server_default="local"))


def downgrade() -> None:
    op.drop_column("open_skills", "managed_by")
    op.drop_column("open_skills", "source_url")
