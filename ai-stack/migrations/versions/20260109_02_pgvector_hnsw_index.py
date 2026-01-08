"""Add pgvector HNSW index for document embeddings.

Revision ID: 20260109_02
Revises: 20260109_01
Create Date: 2026-01-09
"""

from alembic import op

revision = "20260109_02"
down_revision = "20260109_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_embeddings_embedding_hnsw
        ON document_embeddings
        USING hnsw (embedding vector_l2_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_embeddings_embedding_hnsw")
