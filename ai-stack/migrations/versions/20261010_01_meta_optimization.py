"""Create meta-optimization tables (harness proposals, evolution history, baselines).

Revision ID: 20261010_01
Revises: 20260125_01
Create Date: 2026-10-10

Ports ai-stack/postgres/migrations/008_meta_optimization.sql (raw SQL that no
runner applied) onto the alembic aidb chain. Only the objects the Python code
and scripts/ai/aq-meta-optimize call are included: the three tables, their
indexes, the five SQL functions, and the impact-summary view. Idempotent.
"""

from alembic import op

revision = "20261010_01"
down_revision = "20260125_01"
branch_labels = None  # inherits the "aidb" branch label via down_revision
depends_on = None

TABLES = (
    "harness_improvement_proposals",
    "harness_evolution_history",
    "harness_performance_baselines",
)

UPGRADE_SQL = [
    """
CREATE TABLE IF NOT EXISTS harness_improvement_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    current_state TEXT,
    proposed_change TEXT NOT NULL,
    expected_impact TEXT,
    estimated_improvement_pct REAL DEFAULT 0.0,
    confidence_score REAL DEFAULT 0.0 CHECK (confidence_score >= 0 AND confidence_score <= 1),
    evidence JSONB DEFAULT '{}',
    implementation_steps JSONB DEFAULT '[]',
    rollback_plan TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'meta_optimizer',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'applied', 'rolled_back')),
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    applied_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
)
""",
    "CREATE INDEX IF NOT EXISTS idx_improvement_proposals_target ON harness_improvement_proposals(target)",
    "CREATE INDEX IF NOT EXISTS idx_improvement_proposals_priority ON harness_improvement_proposals(priority)",
    "CREATE INDEX IF NOT EXISTS idx_improvement_proposals_status ON harness_improvement_proposals(status)",
    "CREATE INDEX IF NOT EXISTS idx_improvement_proposals_created_at ON harness_improvement_proposals(created_at DESC)",
    """
CREATE TABLE IF NOT EXISTS harness_evolution_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES harness_improvement_proposals(id) ON DELETE CASCADE,
    change_type TEXT NOT NULL,
    component_affected TEXT NOT NULL,
    change_description TEXT NOT NULL,
    change_details JSONB DEFAULT '{}',
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    applied_by TEXT DEFAULT 'meta_optimizer',
    baseline_metrics JSONB DEFAULT '{}',
    impact_metrics JSONB DEFAULT '{}',
    actual_improvement_pct REAL,
    validation_status TEXT CHECK (validation_status IN ('pending', 'improved', 'degraded', 'neutral')),
    validated_at TIMESTAMPTZ,
    rollback_commit TEXT,
    rolled_back BOOLEAN DEFAULT FALSE,
    rolled_back_at TIMESTAMPTZ,
    rollback_reason TEXT,
    metadata JSONB DEFAULT '{}'
)
""",
    "CREATE INDEX IF NOT EXISTS idx_evolution_history_proposal ON harness_evolution_history(proposal_id)",
    "CREATE INDEX IF NOT EXISTS idx_evolution_history_component ON harness_evolution_history(component_affected)",
    "CREATE INDEX IF NOT EXISTS idx_evolution_history_applied_at ON harness_evolution_history(applied_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_evolution_history_validation ON harness_evolution_history(validation_status)",
    """
CREATE TABLE IF NOT EXISTS harness_performance_baselines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    measurement_window_hours INTEGER NOT NULL,
    measured_at TIMESTAMPTZ DEFAULT NOW(),
    component TEXT,
    metadata JSONB DEFAULT '{}'
)
""",
    "CREATE INDEX IF NOT EXISTS idx_performance_baselines_metric ON harness_performance_baselines(metric_name)",
    "CREATE INDEX IF NOT EXISTS idx_performance_baselines_measured_at ON harness_performance_baselines(measured_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_performance_baselines_component ON harness_performance_baselines(component)",
    """
CREATE OR REPLACE VIEW meta_optimization_impact_summary AS
SELECT
    target,
    COUNT(*) AS proposals_created,
    SUM(CASE WHEN status = 'applied' THEN 1 ELSE 0 END) AS proposals_applied,
    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS proposals_rejected,
    AVG(estimated_improvement_pct) AS avg_estimated_improvement,
    AVG(CASE WHEN status = 'applied' THEN confidence_score END) AS avg_confidence_applied
FROM harness_improvement_proposals
GROUP BY target
ORDER BY proposals_applied DESC
""",
    """
CREATE OR REPLACE FUNCTION record_performance_baseline(
    p_metric_name TEXT,
    p_metric_value REAL,
    p_window_hours INTEGER,
    p_component TEXT DEFAULT NULL
) RETURNS UUID AS $fn$
DECLARE
    baseline_id UUID;
BEGIN
    INSERT INTO harness_performance_baselines (metric_name, metric_value, measurement_window_hours, component)
    VALUES (p_metric_name, p_metric_value, p_window_hours, p_component)
    RETURNING id INTO baseline_id;
    RETURN baseline_id;
END;
$fn$ LANGUAGE plpgsql
""",
    """
CREATE OR REPLACE FUNCTION approve_improvement_proposal(
    p_proposal_id UUID,
    p_reviewed_by TEXT
) RETURNS VOID AS $fn$
BEGIN
    UPDATE harness_improvement_proposals
    SET status = 'approved', reviewed_by = p_reviewed_by, reviewed_at = NOW()
    WHERE id = p_proposal_id AND status = 'pending';
END;
$fn$ LANGUAGE plpgsql
""",
    """
CREATE OR REPLACE FUNCTION apply_improvement_proposal(
    p_proposal_id UUID,
    p_change_type TEXT,
    p_component_affected TEXT,
    p_change_description TEXT,
    p_change_details JSONB DEFAULT '{}'::jsonb,
    p_rollback_commit TEXT DEFAULT NULL
) RETURNS UUID AS $fn$
DECLARE
    history_id UUID;
BEGIN
    UPDATE harness_improvement_proposals
    SET status = 'applied', applied_at = NOW()
    WHERE id = p_proposal_id;

    INSERT INTO harness_evolution_history (
        proposal_id, change_type, component_affected, change_description,
        change_details, rollback_commit, validation_status
    ) VALUES (
        p_proposal_id, p_change_type, p_component_affected, p_change_description,
        p_change_details, p_rollback_commit, 'pending'
    ) RETURNING id INTO history_id;

    RETURN history_id;
END;
$fn$ LANGUAGE plpgsql
""",
    """
CREATE OR REPLACE FUNCTION validate_improvement_impact(
    p_history_id UUID,
    p_actual_improvement_pct REAL,
    p_impact_metrics JSONB DEFAULT '{}'::jsonb
) RETURNS VOID AS $fn$
DECLARE
    v_validation_status TEXT;
BEGIN
    IF p_actual_improvement_pct > 3.0 THEN
        v_validation_status := 'improved';
    ELSIF p_actual_improvement_pct < -3.0 THEN
        v_validation_status := 'degraded';
    ELSE
        v_validation_status := 'neutral';
    END IF;

    UPDATE harness_evolution_history
    SET actual_improvement_pct = p_actual_improvement_pct,
        impact_metrics = p_impact_metrics,
        validation_status = v_validation_status,
        validated_at = NOW()
    WHERE id = p_history_id;
END;
$fn$ LANGUAGE plpgsql
""",
    """
CREATE OR REPLACE FUNCTION rollback_improvement(
    p_history_id UUID,
    p_rollback_reason TEXT
) RETURNS VOID AS $fn$
DECLARE
    v_proposal_id UUID;
BEGIN
    UPDATE harness_evolution_history
    SET rolled_back = TRUE, rolled_back_at = NOW(), rollback_reason = p_rollback_reason
    WHERE id = p_history_id
    RETURNING proposal_id INTO v_proposal_id;

    UPDATE harness_improvement_proposals
    SET status = 'rolled_back'
    WHERE id = v_proposal_id;
END;
$fn$ LANGUAGE plpgsql
""",
]

DOWNGRADE_SQL = [
    "DROP VIEW IF EXISTS meta_optimization_impact_summary",
    "DROP FUNCTION IF EXISTS rollback_improvement(UUID, TEXT)",
    "DROP FUNCTION IF EXISTS validate_improvement_impact(UUID, REAL, JSONB)",
    "DROP FUNCTION IF EXISTS apply_improvement_proposal(UUID, TEXT, TEXT, TEXT, JSONB, TEXT)",
    "DROP FUNCTION IF EXISTS approve_improvement_proposal(UUID, TEXT)",
    "DROP FUNCTION IF EXISTS record_performance_baseline(TEXT, REAL, INTEGER, TEXT)",
    "DROP TABLE IF EXISTS harness_performance_baselines",
    "DROP TABLE IF EXISTS harness_evolution_history",
    "DROP TABLE IF EXISTS harness_improvement_proposals",
]


def upgrade() -> None:
    for stmt in UPGRADE_SQL:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in DOWNGRADE_SQL:
        op.execute(stmt)
