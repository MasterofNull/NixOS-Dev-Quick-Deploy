-- Meta-Optimization Schema
-- Phase 3: Harness Self-Improvement
--
-- Enables the harness to analyze its own performance and generate
-- improvement proposals for routing, hints, lessons, tools, and agent roles.

-- ============================================================================
-- Harness Improvement Proposals
-- ============================================================================

CREATE TABLE IF NOT EXISTS harness_improvement_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target TEXT NOT NULL,  -- routing_rules, hint_templates, lesson_library, tool_discovery, agent_roles
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
);

CREATE INDEX idx_improvement_proposals_target ON harness_improvement_proposals(target);
CREATE INDEX idx_improvement_proposals_priority ON harness_improvement_proposals(priority);
CREATE INDEX idx_improvement_proposals_status ON harness_improvement_proposals(status);
CREATE INDEX idx_improvement_proposals_created_at ON harness_improvement_proposals(created_at DESC);

COMMENT ON TABLE harness_improvement_proposals IS 'Meta-optimization proposals for harness self-improvement';
COMMENT ON COLUMN harness_improvement_proposals.target IS 'What aspect of the harness to optimize';
COMMENT ON COLUMN harness_improvement_proposals.confidence_score IS 'LLM confidence this will improve performance (0-1)';

-- ============================================================================
-- Harness Evolution History
-- ============================================================================

CREATE TABLE IF NOT EXISTS harness_evolution_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES harness_improvement_proposals(id) ON DELETE CASCADE,
    change_type TEXT NOT NULL,  -- routing_rule_added, hint_template_revised, lesson_archived, etc.
    component_affected TEXT NOT NULL,  -- route_handler.py, hints_engine.py, etc.
    change_description TEXT NOT NULL,
    change_details JSONB DEFAULT '{}',
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    applied_by TEXT DEFAULT 'meta_optimizer',

    -- Impact metrics (measured after deployment)
    baseline_metrics JSONB DEFAULT '{}',
    impact_metrics JSONB DEFAULT '{}',
    actual_improvement_pct REAL,
    validation_status TEXT CHECK (validation_status IN ('pending', 'improved', 'degraded', 'neutral')),
    validated_at TIMESTAMPTZ,

    -- Rollback info
    rollback_commit TEXT,  -- Git commit hash to rollback to
    rolled_back BOOLEAN DEFAULT FALSE,
    rolled_back_at TIMESTAMPTZ,
    rollback_reason TEXT,

    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_evolution_history_proposal ON harness_evolution_history(proposal_id);
CREATE INDEX idx_evolution_history_component ON harness_evolution_history(component_affected);
CREATE INDEX idx_evolution_history_applied_at ON harness_evolution_history(applied_at DESC);
CREATE INDEX idx_evolution_history_validation ON harness_evolution_history(validation_status);

COMMENT ON TABLE harness_evolution_history IS 'Historical record of harness changes and their measured impact';
COMMENT ON COLUMN harness_evolution_history.actual_improvement_pct IS 'Measured improvement after deployment';

-- ============================================================================
-- Harness Performance Baselines
-- ============================================================================

CREATE TABLE IF NOT EXISTS harness_performance_baselines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    measurement_window_hours INTEGER NOT NULL,
    measured_at TIMESTAMPTZ DEFAULT NOW(),
    component TEXT,  -- Which harness component this metric applies to
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_performance_baselines_metric ON harness_performance_baselines(metric_name);
CREATE INDEX idx_performance_baselines_measured_at ON harness_performance_baselines(measured_at DESC);
CREATE INDEX idx_performance_baselines_component ON harness_performance_baselines(component);

COMMENT ON TABLE harness_performance_baselines IS 'Performance baselines for measuring improvement impact';

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- Active improvement proposals by priority
CREATE OR REPLACE VIEW active_improvement_proposals AS
SELECT
    id,
    target,
    priority,
    title,
    description,
    estimated_improvement_pct,
    confidence_score,
    created_at,
    created_by,
    status
FROM harness_improvement_proposals
WHERE status = 'pending'
ORDER BY
    CASE priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END,
    estimated_improvement_pct DESC,
    created_at DESC;

-- Harness evolution timeline
CREATE OR REPLACE VIEW harness_evolution_timeline AS
SELECT
    h.id,
    h.change_type,
    h.component_affected,
    h.change_description,
    h.actual_improvement_pct,
    h.validation_status,
    h.applied_at,
    h.rolled_back,
    p.title as proposal_title,
    p.target as proposal_target
FROM harness_evolution_history h
LEFT JOIN harness_improvement_proposals p ON h.proposal_id = p.id
ORDER BY h.applied_at DESC;

-- Meta-optimization impact summary
CREATE OR REPLACE VIEW meta_optimization_impact_summary AS
SELECT
    target,
    COUNT(*) as proposals_created,
    SUM(CASE WHEN status = 'applied' THEN 1 ELSE 0 END) as proposals_applied,
    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as proposals_rejected,
    AVG(estimated_improvement_pct) as avg_estimated_improvement,
    AVG(CASE WHEN status = 'applied' THEN confidence_score END) as avg_confidence_applied
FROM harness_improvement_proposals
GROUP BY target
ORDER BY proposals_applied DESC;

-- Component evolution frequency
CREATE OR REPLACE VIEW component_evolution_frequency AS
SELECT
    component_affected,
    COUNT(*) as total_changes,
    SUM(CASE WHEN validation_status = 'improved' THEN 1 ELSE 0 END) as improvements,
    SUM(CASE WHEN validation_status = 'degraded' THEN 1 ELSE 0 END) as degradations,
    SUM(CASE WHEN rolled_back THEN 1 ELSE 0 END) as rollbacks,
    AVG(actual_improvement_pct) as avg_actual_improvement_pct,
    MAX(applied_at) as last_changed_at
FROM harness_evolution_history
GROUP BY component_affected
ORDER BY total_changes DESC;

-- ============================================================================
-- Functions for Common Operations
-- ============================================================================

-- Record performance baseline
CREATE OR REPLACE FUNCTION record_performance_baseline(
    p_metric_name TEXT,
    p_metric_value REAL,
    p_window_hours INTEGER,
    p_component TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    baseline_id UUID;
BEGIN
    INSERT INTO harness_performance_baselines (
        metric_name,
        metric_value,
        measurement_window_hours,
        component
    ) VALUES (
        p_metric_name,
        p_metric_value,
        p_window_hours,
        p_component
    ) RETURNING id INTO baseline_id;

    RETURN baseline_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION record_performance_baseline IS 'Record a performance baseline before applying changes';

-- Approve improvement proposal
CREATE OR REPLACE FUNCTION approve_improvement_proposal(
    p_proposal_id UUID,
    p_reviewed_by TEXT
) RETURNS VOID AS $$
BEGIN
    UPDATE harness_improvement_proposals
    SET
        status = 'approved',
        reviewed_by = p_reviewed_by,
        reviewed_at = NOW()
    WHERE id = p_proposal_id
      AND status = 'pending';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION approve_improvement_proposal IS 'Approve a pending improvement proposal';

-- Apply improvement proposal
CREATE OR REPLACE FUNCTION apply_improvement_proposal(
    p_proposal_id UUID,
    p_change_type TEXT,
    p_component_affected TEXT,
    p_change_description TEXT,
    p_change_details JSONB DEFAULT '{}'::jsonb,
    p_rollback_commit TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    history_id UUID;
BEGIN
    -- Update proposal status
    UPDATE harness_improvement_proposals
    SET
        status = 'applied',
        applied_at = NOW()
    WHERE id = p_proposal_id;

    -- Create evolution history record
    INSERT INTO harness_evolution_history (
        proposal_id,
        change_type,
        component_affected,
        change_description,
        change_details,
        rollback_commit,
        validation_status
    ) VALUES (
        p_proposal_id,
        p_change_type,
        p_component_affected,
        p_change_description,
        p_change_details,
        p_rollback_commit,
        'pending'
    ) RETURNING id INTO history_id;

    RETURN history_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION apply_improvement_proposal IS 'Apply an approved improvement proposal and track in evolution history';

-- Validate improvement impact
CREATE OR REPLACE FUNCTION validate_improvement_impact(
    p_history_id UUID,
    p_actual_improvement_pct REAL,
    p_impact_metrics JSONB DEFAULT '{}'::jsonb
) RETURNS VOID AS $$
DECLARE
    v_validation_status TEXT;
BEGIN
    -- Determine validation status
    IF p_actual_improvement_pct > 3.0 THEN
        v_validation_status := 'improved';
    ELSIF p_actual_improvement_pct < -3.0 THEN
        v_validation_status := 'degraded';
    ELSE
        v_validation_status := 'neutral';
    END IF;

    -- Update evolution history
    UPDATE harness_evolution_history
    SET
        actual_improvement_pct = p_actual_improvement_pct,
        impact_metrics = p_impact_metrics,
        validation_status = v_validation_status,
        validated_at = NOW()
    WHERE id = p_history_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION validate_improvement_impact IS 'Validate measured impact of an applied improvement';

-- Rollback improvement
CREATE OR REPLACE FUNCTION rollback_improvement(
    p_history_id UUID,
    p_rollback_reason TEXT
) RETURNS VOID AS $$
DECLARE
    v_proposal_id UUID;
BEGIN
    -- Mark evolution history as rolled back
    UPDATE harness_evolution_history
    SET
        rolled_back = TRUE,
        rolled_back_at = NOW(),
        rollback_reason = p_rollback_reason
    WHERE id = p_history_id
    RETURNING proposal_id INTO v_proposal_id;

    -- Mark proposal as rolled back
    UPDATE harness_improvement_proposals
    SET status = 'rolled_back'
    WHERE id = v_proposal_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION rollback_improvement IS 'Rollback an applied improvement that degraded performance';

-- ============================================================================
-- Triggers
-- ============================================================================

-- Auto-update metadata timestamps
CREATE OR REPLACE FUNCTION update_meta_optimization_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.metadata = jsonb_set(
        COALESCE(NEW.metadata, '{}'::jsonb),
        '{last_updated_at}',
        to_jsonb(NOW())
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_proposal_timestamp
BEFORE UPDATE ON harness_improvement_proposals
FOR EACH ROW
EXECUTE FUNCTION update_meta_optimization_timestamp();

CREATE TRIGGER trigger_update_evolution_timestamp
BEFORE UPDATE ON harness_evolution_history
FOR EACH ROW
EXECUTE FUNCTION update_meta_optimization_timestamp();

COMMENT ON TRIGGER trigger_update_proposal_timestamp ON harness_improvement_proposals IS
    'Automatically update metadata timestamp on proposal updates';

COMMENT ON TRIGGER trigger_update_evolution_timestamp ON harness_evolution_history IS
    'Automatically update metadata timestamp on evolution history updates';
