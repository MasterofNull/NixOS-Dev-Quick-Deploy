from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_imported_documents"
down_revision = "0001_create_tool_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "imported_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project", sa.String(length=128), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.UniqueConstraint("project", "relative_path", name="uq_imported_documents_path"),
    )
    op.create_index(
        "idx_imported_documents_project",
        "imported_documents",
        ["project"],
    )
    op.create_index(
        "idx_imported_documents_content_type",
        "imported_documents",
        ["content_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_imported_documents_content_type", table_name="imported_documents")
    op.drop_index("idx_imported_documents_project", table_name="imported_documents")
    op.drop_table("imported_documents")

