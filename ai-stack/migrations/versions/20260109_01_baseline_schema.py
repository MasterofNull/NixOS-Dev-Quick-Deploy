"""Baseline AIDB schema.

Revision ID: 20260109_01
Revises: 
Create Date: 2026-01-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "20260109_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tool_registry",
        sa.Column("name", sa.String(256), primary_key=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("manifest", sa.JSON, nullable=False),
        sa.Column("cost_estimate_tokens", sa.Integer, nullable=False, default=2000),
    )

    op.create_table(
        "imported_documents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project", sa.String(128), nullable=False),
        sa.Column("relative_path", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'approved'")),
        sa.UniqueConstraint("project", "relative_path", name="uq_imported_documents_path"),
    )

    op.create_table(
        "open_skills",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("version", sa.String(32), nullable=True),
        sa.Column("tags", sa.JSON, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False),
        sa.Column("source_path", sa.Text, nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("managed_by", sa.String(32), nullable=False, server_default=sa.text("'local'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'approved'")),
    )

    op.create_table(
        "system_registry",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("install_command", sa.Text, nullable=True),
        sa.Column("dependencies", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("added_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "points_of_interest",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "category", name="uq_points_of_interest_name_category"),
    )

    op.create_table(
        "telemetry_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("llm_used", sa.String(32), nullable=True),
        sa.Column("tokens_saved", sa.Integer, nullable=True),
        sa.Column("rag_hits", sa.Integer, nullable=True),
        sa.Column("collections_used", sa.JSON, nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("cache_hit", sa.Boolean, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

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


def downgrade() -> None:
    op.drop_table("document_embeddings")
    op.drop_table("telemetry_events")
    op.drop_table("points_of_interest")
    op.drop_table("system_registry")
    op.drop_table("open_skills")
    op.drop_table("imported_documents")
    op.drop_table("tool_registry")
