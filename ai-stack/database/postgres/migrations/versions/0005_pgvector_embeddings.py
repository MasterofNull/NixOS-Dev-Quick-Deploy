from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "0005_pgvector_embeddings"
down_revision = "0004_open_skills_source_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension for semantic search
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "document_embeddings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("imported_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_id", sa.String(length=128), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("document_id", "chunk_id", name="uq_document_embeddings_chunk"),
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_embeddings_vector "
        "ON document_embeddings USING ivfflat (embedding vector_l2_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_embeddings_vector")
    op.drop_table("document_embeddings")
