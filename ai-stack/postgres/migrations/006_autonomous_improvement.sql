-- Migration 006: Autonomous Improvement Loop System
-- Created: 2026-03-15
-- Purpose: Tables for autonomous self-improvement cycles, trend analysis, and design decisions

-- Note: TimescaleDB extension not available in this PostgreSQL instance
-- Using standard PostgreSQL tables instead

-- ============================================================================
-- IMPROVEMENT CYCLES
-- ============================================================================
-- Main tracking table for autonomous improvement cycles
CREATE TABLE IF NOT EXISTS improvement_cycles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_type TEXT NOT NULL,  -- autoresearch, anomaly_response, scheduled, manual
    triggered_by UUID,  -- FK to trigger_events (nullable for manual triggers)
    research_summary JSONB,  -- Discovered patterns and hypotheses
    experiments_run INTEGER DEFAULT 0,
    experiments_accepted INTEGER DEFAULT 0,
    experiments_rejected INTEGER DEFAULT 0,
    total_improvement_pct REAL,  -- Aggregate improvement across all experiments
    cost_tokens INTEGER DEFAULT 0,
    cost_dollars REAL DEFAULT 0.0,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
    error_message TEXT,  -- Populated if status = failed
    metadata JSONB,  -- Additional cycle-specific metadata

    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT valid_cycle_type CHECK (cycle_type IN ('autoresearch', 'anomaly_response', 'scheduled', 'manual'))
);

CREATE INDEX idx_improvement_cycles_status ON improvement_cycles(status);
CREATE INDEX idx_improvement_cycles_started_at ON improvement_cycles(started_at DESC);
CREATE INDEX idx_improvement_cycles_cycle_type ON improvement_cycles(cycle_type);

-- ============================================================================
-- TRIGGER EVENTS
-- ============================================================================
-- Records what triggered each improvement cycle
CREATE TABLE IF NOT EXISTS trigger_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_type TEXT NOT NULL,  -- anomaly, schedule, threshold, event
    trigger_source TEXT NOT NULL,  -- baseline_profiler, prometheus, manual, cron
    severity TEXT NOT NULL,  -- low, medium, high, critical
    metric_name TEXT,  -- The metric that triggered (if applicable)
    observed_value REAL,
    threshold_value REAL,
    context JSONB,  -- Additional context about the trigger
    improvement_cycle_id UUID REFERENCES improvement_cycles(id) ON DELETE SET NULL,
    triggered_at TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP,  -- When the issue was resolved

    CONSTRAINT valid_trigger_type CHECK (trigger_type IN ('anomaly', 'schedule', 'threshold', 'event')),
    CONSTRAINT valid_severity CHECK (severity IN ('low', 'medium', 'high', 'critical'))
);

CREATE INDEX idx_trigger_events_triggered_at ON trigger_events(triggered_at DESC);
CREATE INDEX idx_trigger_events_severity ON trigger_events(severity);
CREATE INDEX idx_trigger_events_cycle_id ON trigger_events(improvement_cycle_id);

-- Add FK from improvement_cycles to trigger_events (now that both tables exist)
ALTER TABLE improvement_cycles
    ADD CONSTRAINT fk_triggered_by
    FOREIGN KEY (triggered_by)
    REFERENCES trigger_events(id)
    ON DELETE SET NULL;

-- ============================================================================
-- EXPERIMENT RESULTS HISTORY
-- ============================================================================
-- Historical record of all experiments run (extends experiments.sqlite)
CREATE TABLE IF NOT EXISTS experiment_results_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id UUID REFERENCES improvement_cycles(id) ON DELETE CASCADE,
    experiment_type TEXT NOT NULL,  -- prompt_optimization, config_tuning, architecture_change, etc.
    hypothesis TEXT NOT NULL,  -- The hypothesis being tested
    baseline_config JSONB NOT NULL,  -- Configuration of baseline variant
    variant_config JSONB NOT NULL,  -- Configuration of experimental variant
    baseline_metrics JSONB NOT NULL,  -- Baseline performance metrics
    variant_metrics JSONB NOT NULL,  -- Variant performance metrics
    improvement_pct REAL,  -- Percentage improvement (positive = better)
    statistical_significance REAL,  -- p-value from statistical test
    accepted BOOLEAN DEFAULT FALSE,  -- Whether experiment was accepted
    applied BOOLEAN DEFAULT FALSE,  -- Whether changes were applied to production
    application_timestamp TIMESTAMP,  -- When changes were applied
    rollback_timestamp TIMESTAMP,  -- When changes were rolled back (if applicable)
    rollback_reason TEXT,  -- Why the rollback occurred
    experiment_duration_seconds INTEGER,
    sample_size INTEGER,  -- Number of tasks/queries in the experiment
    metadata JSONB,  -- Additional experiment-specific data
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_experiment_type CHECK (experiment_type IN (
        'prompt_optimization', 'config_tuning', 'architecture_change',
        'model_selection', 'caching_strategy', 'routing_optimization',
        'hint_diversity', 'memory_tuning', 'other'
    ))
);

CREATE INDEX idx_experiment_results_cycle_id ON experiment_results_history(cycle_id);
CREATE INDEX idx_experiment_results_created_at ON experiment_results_history(created_at DESC);
CREATE INDEX idx_experiment_results_accepted ON experiment_results_history(accepted);
CREATE INDEX idx_experiment_results_experiment_type ON experiment_results_history(experiment_type);

-- ============================================================================
-- SYSTEM METRICS TIMESERIES (TimescaleDB Hypertable)
-- ============================================================================
-- High-frequency time-series metrics for trend analysis
CREATE TABLE IF NOT EXISTS system_metrics_timeseries (
    time TIMESTAMP NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    metric_unit TEXT,  -- ms, pct, count, bytes, etc.
    service TEXT,  -- Service that generated the metric
    component TEXT,  -- Component within the service
    metadata JSONB,  -- Additional context (tags, labels, etc.)

    -- Create composite index for efficient queries
    PRIMARY KEY (time, metric_name, service, component)
);

-- Standard PostgreSQL indexes (TimescaleDB hypertable features skipped)
CREATE INDEX idx_metrics_metric_name ON system_metrics_timeseries(metric_name, time DESC);
CREATE INDEX idx_metrics_service ON system_metrics_timeseries(service, time DESC);
CREATE INDEX idx_metrics_component ON system_metrics_timeseries(component, time DESC);
CREATE INDEX idx_metrics_time ON system_metrics_timeseries(time DESC);

-- Note: Manual cleanup needed for old data (no automatic retention policy without TimescaleDB)
-- Run periodically: DELETE FROM system_metrics_timeseries WHERE time < NOW() - INTERVAL '90 days';

-- Regular views for aggregates (TimescaleDB continuous aggregates not available)
CREATE OR REPLACE VIEW metrics_hourly AS
SELECT
    DATE_TRUNC('hour', time) AS bucket,
    metric_name,
    service,
    component,
    AVG(metric_value) AS avg_value,
    MIN(metric_value) AS min_value,
    MAX(metric_value) AS max_value,
    STDDEV(metric_value) AS stddev_value,
    COUNT(*) AS sample_count
FROM system_metrics_timeseries
GROUP BY DATE_TRUNC('hour', time), metric_name, service, component;

-- Daily aggregates for longer-term trends
CREATE OR REPLACE VIEW metrics_daily AS
SELECT
    DATE_TRUNC('day', time) AS bucket,
    metric_name,
    service,
    component,
    AVG(metric_value) AS avg_value,
    MIN(metric_value) AS min_value,
    MAX(metric_value) AS max_value,
    STDDEV(metric_value) AS stddev_value,
    COUNT(*) AS sample_count
FROM system_metrics_timeseries
GROUP BY DATE_TRUNC('day', time), metric_name, service, component;

-- Note: These are regular views (not materialized) and may be slow on large datasets
-- Consider creating materialized views and refreshing them periodically if needed

-- ============================================================================
-- DESIGN DECISIONS
-- ============================================================================
-- Evidence-based architectural and design decision ledger
CREATE TABLE IF NOT EXISTS design_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_type TEXT NOT NULL,  -- architecture, configuration, tooling, model_selection, workflow
    decision TEXT NOT NULL,  -- The decision itself (e.g., "Increase hint diversity threshold")
    rationale TEXT,  -- Why this decision was made
    evidence JSONB,  -- Array of experiment IDs, metric trends, references
    confidence_score REAL NOT NULL,  -- 0.0-1.0 based on evidence strength
    impact_estimate TEXT,  -- low, medium, high
    status TEXT NOT NULL DEFAULT 'proposed',  -- proposed, accepted, rejected, applied, reverted
    proposed_by TEXT NOT NULL,  -- autonomous_agent, human, recommendation_engine
    proposed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    reviewed_by TEXT,  -- Who reviewed/accepted the decision
    reviewed_at TIMESTAMP,
    applied_at TIMESTAMP,
    reverted_at TIMESTAMP,
    revert_reason TEXT,
    implementation_notes TEXT,  -- Details about how it was implemented
    metadata JSONB,

    CONSTRAINT valid_decision_type CHECK (decision_type IN (
        'architecture', 'configuration', 'tooling', 'model_selection',
        'workflow', 'optimization', 'infrastructure', 'other'
    )),
    CONSTRAINT valid_status CHECK (status IN (
        'proposed', 'accepted', 'rejected', 'applied', 'reverted'
    )),
    CONSTRAINT valid_impact CHECK (impact_estimate IN ('low', 'medium', 'high', 'unknown')),
    CONSTRAINT valid_confidence CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0)
);

CREATE INDEX idx_design_decisions_status ON design_decisions(status);
CREATE INDEX idx_design_decisions_proposed_at ON design_decisions(proposed_at DESC);
CREATE INDEX idx_design_decisions_decision_type ON design_decisions(decision_type);
CREATE INDEX idx_design_decisions_confidence ON design_decisions(confidence_score DESC);

-- ============================================================================
-- METRIC TRENDS (Cached Analysis)
-- ============================================================================
-- Pre-computed trend analysis for common metrics
CREATE TABLE IF NOT EXISTS metric_trends (
    metric_name TEXT NOT NULL,
    time_window TEXT NOT NULL,  -- 1h, 24h, 7d, 30d (renamed from 'window' which is SQL reserved)
    current_value REAL NOT NULL,
    baseline_value REAL NOT NULL,  -- Value at start of window
    change_pct REAL NOT NULL,  -- Percentage change
    trend_direction TEXT NOT NULL,  -- improving, stable, degrading, volatile
    volatility REAL,  -- Standard deviation / mean (coefficient of variation)
    sample_count INTEGER,  -- Number of data points in window
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata JSONB,  -- Additional trend-specific data

    PRIMARY KEY (metric_name, time_window),
    CONSTRAINT valid_time_window CHECK (time_window IN ('1h', '6h', '24h', '7d', '30d', '90d')),
    CONSTRAINT valid_trend CHECK (trend_direction IN ('improving', 'stable', 'degrading', 'volatile', 'insufficient_data'))
);

CREATE INDEX idx_metric_trends_updated ON metric_trends(last_updated DESC);
CREATE INDEX idx_metric_trends_direction ON metric_trends(trend_direction);

-- ============================================================================
-- HYPOTHESES
-- ============================================================================
-- Generated optimization hypotheses from research phase
CREATE TABLE IF NOT EXISTS optimization_hypotheses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id TEXT UNIQUE NOT NULL,  -- Human-readable ID (h-2026-03-15-001)
    cycle_id UUID REFERENCES improvement_cycles(id) ON DELETE CASCADE,
    hypothesis_type TEXT NOT NULL,  -- PROMPT_OPTIMIZATION, CONFIG_TUNING, etc.
    description TEXT NOT NULL,
    evidence JSONB NOT NULL,  -- Supporting metrics, trends, observations
    experiment_config JSONB NOT NULL,  -- Baseline/variant configuration
    estimated_impact TEXT,  -- Expected improvement estimate
    risk_level TEXT NOT NULL,  -- low, medium, high
    priority_score REAL,  -- 0.0-1.0 for ranking
    generated_by TEXT NOT NULL,  -- llama-cpp-local, qwen-coder, manual
    generated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    tested BOOLEAN DEFAULT FALSE,
    test_result_id UUID REFERENCES experiment_results_history(id),
    metadata JSONB,

    CONSTRAINT valid_risk CHECK (risk_level IN ('low', 'medium', 'high', 'unknown'))
);

CREATE INDEX idx_hypotheses_cycle_id ON optimization_hypotheses(cycle_id);
CREATE INDEX idx_hypotheses_generated_at ON optimization_hypotheses(generated_at DESC);
CREATE INDEX idx_hypotheses_tested ON optimization_hypotheses(tested);
CREATE INDEX idx_hypotheses_priority ON optimization_hypotheses(priority_score DESC NULLS LAST);

-- ============================================================================
-- RECOMMENDATIONS
-- ============================================================================
-- High-level design recommendations from recommendation engine
CREATE TABLE IF NOT EXISTS improvement_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id TEXT UNIQUE NOT NULL,  -- r-2026-03-15-001
    recommendation_type TEXT NOT NULL,  -- ARCHITECTURE, OPTIMIZATION, CONFIGURATION
    priority TEXT NOT NULL,  -- low, medium, high, critical
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    evidence JSONB NOT NULL,  -- Links to experiments, trends, metrics
    estimated_impact JSONB,  -- Structured impact estimates
    implementation_plan JSONB,  -- Steps, effort, risk
    generated_by TEXT NOT NULL,
    generated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    status TEXT DEFAULT 'pending',  -- pending, accepted, rejected, implemented
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    implemented_at TIMESTAMP,
    metadata JSONB,

    CONSTRAINT valid_priority CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT valid_rec_status CHECK (status IN ('pending', 'accepted', 'rejected', 'implemented', 'deferred'))
);

CREATE INDEX idx_recommendations_priority ON improvement_recommendations(priority);
CREATE INDEX idx_recommendations_status ON improvement_recommendations(status);
CREATE INDEX idx_recommendations_generated_at ON improvement_recommendations(generated_at DESC);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Active improvement cycles with trigger context
CREATE OR REPLACE VIEW active_improvement_cycles AS
SELECT
    ic.*,
    te.trigger_type,
    te.trigger_source,
    te.severity,
    te.metric_name AS trigger_metric
FROM improvement_cycles ic
LEFT JOIN trigger_events te ON ic.triggered_by = te.id
WHERE ic.status IN ('pending', 'running')
ORDER BY ic.started_at DESC;

-- Recent experiment summary
CREATE OR REPLACE VIEW recent_experiments AS
SELECT
    e.id,
    e.cycle_id,
    e.experiment_type,
    e.hypothesis,
    e.improvement_pct,
    e.statistical_significance,
    e.accepted,
    e.applied,
    e.created_at,
    ic.cycle_type
FROM experiment_results_history e
JOIN improvement_cycles ic ON e.cycle_id = ic.id
ORDER BY e.created_at DESC
LIMIT 100;

-- Top recommendations by impact
CREATE OR REPLACE VIEW top_recommendations AS
SELECT
    r.*,
    (r.estimated_impact->>'confidence')::REAL AS confidence
FROM improvement_recommendations r
WHERE r.status = 'pending'
ORDER BY
    CASE r.priority
        WHEN 'critical' THEN 4
        WHEN 'high' THEN 3
        WHEN 'medium' THEN 2
        ELSE 1
    END DESC,
    (r.estimated_impact->>'confidence')::REAL DESC NULLS LAST
LIMIT 20;

-- System health summary from latest trends
CREATE OR REPLACE VIEW system_health_summary AS
SELECT
    metric_name,
    time_window,
    current_value,
    baseline_value,
    change_pct,
    trend_direction,
    last_updated
FROM metric_trends
WHERE time_window = '24h'
AND metric_name IN (
    'eval_score', 'cache_hit_rate', 'token_efficiency',
    'local_routing_pct', 'hint_diversity', 'tool_success_rate'
)
ORDER BY
    CASE trend_direction
        WHEN 'degrading' THEN 1
        WHEN 'volatile' THEN 2
        WHEN 'stable' THEN 3
        WHEN 'improving' THEN 4
        ELSE 5
    END,
    metric_name;

-- ============================================================================
-- INITIAL DATA / SEED
-- ============================================================================

-- Insert initial metric trend entries (will be updated by trend analysis jobs)
INSERT INTO metric_trends (metric_name, time_window, current_value, baseline_value, change_pct, trend_direction, volatility, sample_count)
VALUES
    ('eval_score', '24h', 0.0, 0.0, 0.0, 'insufficient_data', 0.0, 0),
    ('cache_hit_rate', '24h', 0.0, 0.0, 0.0, 'insufficient_data', 0.0, 0),
    ('token_efficiency', '24h', 0.0, 0.0, 0.0, 'insufficient_data', 0.0, 0),
    ('local_routing_pct', '24h', 0.0, 0.0, 0.0, 'insufficient_data', 0.0, 0),
    ('hint_diversity', '24h', 0.0, 0.0, 0.0, 'insufficient_data', 0.0, 0),
    ('tool_success_rate', '24h', 0.0, 0.0, 0.0, 'insufficient_data', 0.0, 0)
ON CONFLICT (metric_name, time_window) DO NOTHING;

-- ============================================================================
-- COMMENTS / DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE improvement_cycles IS 'Autonomous improvement cycle tracking - each cycle represents one complete trigger → research → execute → validate flow';
COMMENT ON TABLE trigger_events IS 'Events that triggered improvement cycles - anomalies, thresholds, schedules';
COMMENT ON TABLE experiment_results_history IS 'Historical record of all A/B experiments with statistical results';
COMMENT ON TABLE system_metrics_timeseries IS 'High-frequency time-series metrics (standard PostgreSQL table without TimescaleDB)';
COMMENT ON TABLE design_decisions IS 'Evidence-based architectural and design decision ledger';
COMMENT ON TABLE metric_trends IS 'Pre-computed trend analysis cache for dashboard and recommendation engine';
COMMENT ON TABLE optimization_hypotheses IS 'Generated optimization hypotheses from autonomous research phase';
COMMENT ON TABLE improvement_recommendations IS 'High-level design recommendations synthesized from trend data';

COMMENT ON VIEW active_improvement_cycles IS 'Currently running or pending improvement cycles with trigger context';
COMMENT ON VIEW recent_experiments IS 'Last 100 experiments with cycle context';
COMMENT ON VIEW top_recommendations IS 'Top pending recommendations ranked by priority and confidence';
COMMENT ON VIEW system_health_summary IS 'Current health status based on 24h metric trends';

-- ============================================================================
-- GRANTS (create user if needed, grant permissions)
-- ============================================================================

-- Create ai_user if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'aidb') THEN
        -- Role aidb is the default user for this database
        NULL;
    END IF;
END
$$;

-- Grant permissions to database owner (aidb)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aidb;
GRANT SELECT ON ALL VIEWS IN SCHEMA public TO aidb;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO aidb;

-- Migration complete
