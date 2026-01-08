from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

METADATA = sa.MetaData()

TOOL_REGISTRY = sa.Table(
    "tool_registry",
    METADATA,
    sa.Column("name", sa.String(256), primary_key=True),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("manifest", sa.JSON, nullable=False),
    sa.Column("cost_estimate_tokens", sa.Integer, nullable=False, default=2000),
)

IMPORTED_DOCUMENTS = sa.Table(
    "imported_documents",
    METADATA,
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

OPEN_SKILLS = sa.Table(
    "open_skills",
    METADATA,
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

SYSTEM_REGISTRY = sa.Table(
    "system_registry",
    METADATA,
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

POINTS_OF_INTEREST = sa.Table(
    "points_of_interest",
    METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("name", sa.String(256), nullable=False),
    sa.Column("category", sa.String(128), nullable=False),
    sa.Column("url", sa.Text, nullable=True),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("source", sa.Text, nullable=True),
    sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("name", "category", name="uq_points_of_interest_name_category"),
)

TELEMETRY_EVENTS = sa.Table(
    "telemetry_events",
    METADATA,
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


def document_embeddings_table(metadata: sa.MetaData, embedding_dimension: int) -> sa.Table:
    return sa.Table(
        "document_embeddings",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("imported_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_id", sa.String(length=128), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(embedding_dimension), nullable=False),
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
        extend_existing=True,
    )
