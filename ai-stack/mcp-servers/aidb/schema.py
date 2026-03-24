from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
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
    # Phase 15.2.2 — Source trust level for RAG filtering
    # trusted: manually added by user | imported: from external URL/file | generated: AI-created
    sa.Column("source_trust_level", sa.String(16), nullable=False, server_default=sa.text("'imported'")),
    sa.Column("source_url", sa.Text, nullable=True),  # Original URL if imported from web
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

LEARNING_FEEDBACK = sa.Table(
    "learning_feedback",
    METADATA,
    sa.Column("feedback_id", sa.String(64), primary_key=True),
    sa.Column("interaction_id", sa.String(128), nullable=True),
    sa.Column("query", sa.Text, nullable=False),
    sa.Column("original_response", sa.Text, nullable=True),
    sa.Column("correction", sa.Text, nullable=False),
    sa.Column("rating", sa.Integer, nullable=True),
    sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("source", sa.String(64), nullable=False, server_default=sa.text("'hybrid'")),
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
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
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


# ---------------------------------------------------------------------------
# Kernel Patch Tracking Tables (Phase 30: Upstream Kernel Development)
# ---------------------------------------------------------------------------

KERNEL_PATCH_SERIES = sa.Table(
    "kernel_patch_series",
    METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("message_id", sa.String(256), nullable=False, unique=True),
    sa.Column("subject", sa.Text, nullable=False),
    sa.Column("author_name", sa.String(256), nullable=False),
    sa.Column("author_email", sa.String(256), nullable=False),
    sa.Column("subsystem", sa.String(128), nullable=True),
    sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
    sa.Column("patch_count", sa.Integer, nullable=False, server_default=sa.text("1")),
    sa.Column("cover_letter", sa.Text, nullable=True),
    sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'draft'")),
    # Status: draft, sent, review, accepted, rejected, superseded
    sa.Column("lore_url", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
)

KERNEL_PATCHES = sa.Table(
    "kernel_patches",
    METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("series_id", sa.Integer, sa.ForeignKey("kernel_patch_series.id", ondelete="CASCADE"), nullable=True),
    sa.Column("message_id", sa.String(256), nullable=False, unique=True),
    sa.Column("commit_hash", sa.String(40), nullable=True),
    sa.Column("patch_number", sa.Integer, nullable=False, server_default=sa.text("1")),
    sa.Column("subject", sa.Text, nullable=False),
    sa.Column("author_name", sa.String(256), nullable=False),
    sa.Column("author_email", sa.String(256), nullable=False),
    sa.Column("commit_message", sa.Text, nullable=False),
    sa.Column("diff_stat", sa.Text, nullable=True),
    sa.Column("files_changed", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("insertions", sa.Integer, nullable=True),
    sa.Column("deletions", sa.Integer, nullable=True),
    sa.Column("subsystem", sa.String(128), nullable=True),
    sa.Column("signed_off_by", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("reviewed_by", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("acked_by", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
)

KERNEL_TEST_RESULTS = sa.Table(
    "kernel_test_results",
    METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("patch_id", sa.Integer, sa.ForeignKey("kernel_patches.id", ondelete="CASCADE"), nullable=True),
    sa.Column("series_id", sa.Integer, sa.ForeignKey("kernel_patch_series.id", ondelete="CASCADE"), nullable=True),
    sa.Column("commit_hash", sa.String(40), nullable=True),
    sa.Column("test_name", sa.String(256), nullable=False),
    sa.Column("test_type", sa.String(64), nullable=False),
    # test_type: build, boot, unit, integration, performance, static_analysis
    sa.Column("architecture", sa.String(32), nullable=True),
    sa.Column("config", sa.String(128), nullable=True),  # defconfig, allmodconfig, etc.
    sa.Column("result", sa.String(32), nullable=False),
    # result: pass, fail, skip, error, timeout
    sa.Column("duration_seconds", sa.Float, nullable=True),
    sa.Column("log_summary", sa.Text, nullable=True),
    sa.Column("log_url", sa.Text, nullable=True),
    sa.Column("warnings", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("errors", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
)

KERNEL_REVIEW_COMMENTS = sa.Table(
    "kernel_review_comments",
    METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("patch_id", sa.Integer, sa.ForeignKey("kernel_patches.id", ondelete="CASCADE"), nullable=False),
    sa.Column("message_id", sa.String(256), nullable=True),
    sa.Column("reviewer_name", sa.String(256), nullable=False),
    sa.Column("reviewer_email", sa.String(256), nullable=False),
    sa.Column("comment_type", sa.String(32), nullable=False),
    # comment_type: inline, general, ack, reviewed-by, nack, question
    sa.Column("file_path", sa.Text, nullable=True),
    sa.Column("line_number", sa.Integer, nullable=True),
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("sentiment", sa.String(16), nullable=True),
    # sentiment: positive, neutral, negative, question
    sa.Column("requires_action", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("action_taken", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)


# ---------------------------------------------------------------------------
# Kernel CVE Tracking Tables (Phase 30.2: Vulnerability Management)
# ---------------------------------------------------------------------------

KERNEL_CVES = sa.Table(
    "kernel_cves",
    METADATA,
    sa.Column("cve_id", sa.String(20), primary_key=True),  # CVE-2026-12345
    sa.Column("nvd_id", sa.String(64), nullable=True),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("severity", sa.String(16), nullable=False),  # low, medium, high, critical
    sa.Column("cvss_v3_score", sa.Float, nullable=True),
    sa.Column("cvss_v3_vector", sa.String(128), nullable=True),
    sa.Column("affected_versions", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("fixed_in_version", sa.String(32), nullable=True),
    sa.Column("subsystems", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("cwe_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("references", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("exploit_available", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("cisa_kev", sa.Boolean, nullable=False, server_default=sa.text("false")),  # Known Exploited Vuln
    sa.Column("local_status", sa.String(32), nullable=False, server_default=sa.text("'open'")),
    # local_status: open, patched_locally, patched_upstream, not_applicable, mitigated
    sa.Column("local_patch_id", sa.Integer, sa.ForeignKey("kernel_patches.id", ondelete="SET NULL"), nullable=True),
    sa.Column("published_date", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_modified", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
)

KERNEL_CVE_HOSTS = sa.Table(
    "kernel_cve_hosts",
    METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("cve_id", sa.String(20), sa.ForeignKey("kernel_cves.cve_id", ondelete="CASCADE"), nullable=False),
    sa.Column("hostname", sa.String(256), nullable=False),
    sa.Column("kernel_version", sa.String(64), nullable=False),
    sa.Column("architecture", sa.String(32), nullable=True),  # x86_64, aarch64, etc.
    sa.Column("status", sa.String(32), nullable=False),  # vulnerable, mitigated, patched, not_applicable
    sa.Column("mitigation_notes", sa.Text, nullable=True),
    sa.Column("scanned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("cve_id", "hostname", name="uq_kernel_cve_host"),
)

KERNEL_RELEASES = sa.Table(
    "kernel_releases",
    METADATA,
    sa.Column("version", sa.String(32), primary_key=True),  # 6.12.5
    sa.Column("release_date", sa.DateTime(timezone=True), nullable=False),
    sa.Column("eol_date", sa.DateTime(timezone=True), nullable=True),
    sa.Column("track", sa.String(32), nullable=False),  # mainline, stable, longterm
    sa.Column("tarball_url", sa.Text, nullable=False),
    sa.Column("pgp_signature_url", sa.Text, nullable=True),
    sa.Column("changelog_url", sa.Text, nullable=True),
    sa.Column("git_sha", sa.String(40), nullable=True),
    sa.Column("security_fixes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("rust_version_required", sa.String(32), nullable=True),  # For Rust-for-Linux builds
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

KERNEL_SUBSYSTEM_CVES = sa.Table(
    "kernel_subsystem_cves",
    METADATA,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("subsystem", sa.String(64), nullable=False),  # drm, net, fs, security
    sa.Column("cve_id", sa.String(20), sa.ForeignKey("kernel_cves.cve_id", ondelete="CASCADE"), nullable=False),
    sa.Column("component", sa.String(128), nullable=True),  # e.g., drivers/gpu/drm/amd
    sa.Column("mailing_list", sa.String(256), nullable=True),  # dri-devel@lists.freedesktop.org
    sa.UniqueConstraint("subsystem", "cve_id", name="uq_subsystem_cve"),
)
