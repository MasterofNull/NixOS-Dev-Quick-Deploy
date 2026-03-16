-- Platform Maturity Schema
-- Phase 5: Platform Maturity & Ecosystem
--
-- Supports agent marketplace, federation protocol, and production hardening
-- with rate limiting, cost budgets, circuit breakers, and audit logging.

-- ============================================================================
-- Agent Marketplace
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_marketplace (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('free', 'community', 'professional', 'enterprise')),
    status TEXT NOT NULL CHECK (status IN ('active', 'maintenance', 'deprecated', 'beta')),
    description TEXT NOT NULL,
    capabilities JSONB DEFAULT '[]',
    supported_domains TEXT[] DEFAULT '{}',
    pricing JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_marketplace_tier ON agent_marketplace(tier);
CREATE INDEX idx_marketplace_status ON agent_marketplace(status);
CREATE INDEX idx_marketplace_domains ON agent_marketplace USING GIN(supported_domains);
CREATE INDEX idx_marketplace_tags ON agent_marketplace USING GIN(tags);

COMMENT ON TABLE agent_marketplace IS 'Registry of available agents with capabilities and pricing';

-- Agent Performance Benchmarks
CREATE TABLE IF NOT EXISTS agent_performance_benchmarks (
    benchmark_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL REFERENCES agent_marketplace(agent_id) ON DELETE CASCADE,
    task_domain TEXT NOT NULL,
    success_rate REAL NOT NULL CHECK (success_rate >= 0 AND success_rate <= 1),
    avg_quality_score REAL NOT NULL CHECK (avg_quality_score >= 0 AND avg_quality_score <= 1),
    avg_latency_ms INTEGER NOT NULL,
    avg_tokens_used INTEGER NOT NULL,
    avg_cost_usd REAL NOT NULL,
    sample_size INTEGER NOT NULL,
    measured_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_benchmarks_agent ON agent_performance_benchmarks(agent_id);
CREATE INDEX idx_benchmarks_domain ON agent_performance_benchmarks(task_domain);
CREATE INDEX idx_benchmarks_measured_at ON agent_performance_benchmarks(measured_at DESC);

COMMENT ON TABLE agent_performance_benchmarks IS 'Performance metrics for agents by task domain';

-- Cost/Quality Tradeoff Profiles
CREATE TABLE IF NOT EXISTS agent_cost_quality_profiles (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL REFERENCES agent_marketplace(agent_id) ON DELETE CASCADE,
    task_domain TEXT NOT NULL,
    cost_per_task_usd REAL NOT NULL,
    quality_score REAL NOT NULL CHECK (quality_score >= 0 AND quality_score <= 1),
    speed_score REAL NOT NULL CHECK (speed_score >= 0 AND speed_score <= 1),
    reliability_score REAL NOT NULL CHECK (reliability_score >= 0 AND reliability_score <= 1),
    value_score REAL NOT NULL,  -- quality / cost
    recommended_for TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(agent_id, task_domain)
);

CREATE INDEX idx_profiles_agent ON agent_cost_quality_profiles(agent_id);
CREATE INDEX idx_profiles_domain ON agent_cost_quality_profiles(task_domain);
CREATE INDEX idx_profiles_value ON agent_cost_quality_profiles(value_score DESC);

COMMENT ON TABLE agent_cost_quality_profiles IS 'Cost vs quality analysis for agent selection';

-- ============================================================================
-- Federation Protocol
-- ============================================================================

CREATE TABLE IF NOT EXISTS federated_patterns (
    pattern_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category TEXT NOT NULL CHECK (category IN ('code_solution', 'error_fix', 'optimization', 'best_practice', 'anti_pattern')),
    domain TEXT NOT NULL,
    problem_hash TEXT NOT NULL,  -- SHA256 hash for privacy
    solution_hash TEXT NOT NULL,  -- SHA256 hash for privacy
    effectiveness_score REAL NOT NULL CHECK (effectiveness_score >= 0 AND effectiveness_score <= 1),
    usage_count INTEGER NOT NULL DEFAULT 1,
    success_rate REAL NOT NULL CHECK (success_rate >= 0 AND success_rate <= 1),
    source_deployment_hash TEXT NOT NULL,  -- SHA256 of deployment ID
    sharing_level TEXT NOT NULL CHECK (sharing_level IN ('private', 'anonymous', 'consortium', 'public')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_fed_patterns_category ON federated_patterns(category);
CREATE INDEX idx_fed_patterns_domain ON federated_patterns(domain);
CREATE INDEX idx_fed_patterns_effectiveness ON federated_patterns(effectiveness_score DESC);
CREATE INDEX idx_fed_patterns_source ON federated_patterns(source_deployment_hash);
CREATE INDEX idx_fed_patterns_sharing ON federated_patterns(sharing_level);

COMMENT ON TABLE federated_patterns IS 'Anonymized patterns shared across deployments';

-- Federated Metric Contributions
CREATE TABLE IF NOT EXISTS federated_metric_contributions (
    contribution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name TEXT NOT NULL,
    source_deployment_hash TEXT NOT NULL,
    value REAL NOT NULL,
    aggregation_type TEXT NOT NULL CHECK (aggregation_type IN ('avg', 'sum', 'count', 'distribution')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fed_metrics_name ON federated_metric_contributions(metric_name);
CREATE INDEX idx_fed_metrics_source ON federated_metric_contributions(source_deployment_hash);
CREATE INDEX idx_fed_metrics_created_at ON federated_metric_contributions(created_at DESC);

COMMENT ON TABLE federated_metric_contributions IS 'Federated metric aggregation contributions';

-- Federation Nodes
CREATE TABLE IF NOT EXISTS federation_nodes (
    node_id TEXT NOT NULL,
    node_hash TEXT PRIMARY KEY,
    sharing_level TEXT NOT NULL CHECK (sharing_level IN ('private', 'anonymous', 'consortium', 'public')),
    trusted_nodes TEXT[] DEFAULT '{}',
    endpoints JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_fed_nodes_sharing ON federation_nodes(sharing_level);

COMMENT ON TABLE federation_nodes IS 'Registered federation network nodes';

-- ============================================================================
-- Production Hardening
-- ============================================================================

-- Cost Budgets
CREATE TABLE IF NOT EXISTS cost_budgets (
    budget_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL UNIQUE,
    daily_budget_usd REAL NOT NULL,
    monthly_budget_usd REAL NOT NULL,
    cost_per_token REAL NOT NULL DEFAULT 0.000015,
    alert_threshold_pct REAL NOT NULL DEFAULT 0.8,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_budgets_agent ON cost_budgets(agent_id);

COMMENT ON TABLE cost_budgets IS 'Cost budget configurations per agent';

-- Cost Tracking
CREATE TABLE IF NOT EXISTS cost_tracking (
    tracking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    cost_usd REAL NOT NULL,
    tokens_used INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_cost_tracking_agent ON cost_tracking(agent_id);
CREATE INDEX idx_cost_tracking_created_at ON cost_tracking(created_at DESC);

COMMENT ON TABLE cost_tracking IS 'Actual cost tracking per agent';

-- Audit Events
CREATE TABLE IF NOT EXISTS audit_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL CHECK (event_type IN (
        'agent_registration', 'task_submission', 'memory_store', 'memory_recall',
        'rate_limit_exceeded', 'budget_exceeded', 'circuit_opened', 'security_violation'
    )),
    agent_id TEXT NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_audit_events_type ON audit_events(event_type);
CREATE INDEX idx_audit_events_agent ON audit_events(agent_id);
CREATE INDEX idx_audit_events_created_at ON audit_events(created_at DESC);

COMMENT ON TABLE audit_events IS 'Compliance audit log for all system events';

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- Active marketplace listings with stats
CREATE OR REPLACE VIEW active_marketplace_listings AS
SELECT
    m.agent_id,
    m.name,
    m.provider,
    m.tier,
    m.status,
    m.description,
    m.supported_domains,
    COUNT(DISTINCT b.benchmark_id) as benchmark_count,
    AVG(b.success_rate) as avg_success_rate,
    AVG(b.avg_quality_score) as avg_quality,
    COUNT(DISTINCT p.profile_id) as profile_count,
    AVG(p.value_score) as avg_value_score
FROM agent_marketplace m
LEFT JOIN agent_performance_benchmarks b ON m.agent_id = b.agent_id
LEFT JOIN agent_cost_quality_profiles p ON m.agent_id = p.agent_id
WHERE m.status = 'active'
GROUP BY m.agent_id, m.name, m.provider, m.tier, m.status, m.description, m.supported_domains
ORDER BY avg_value_score DESC NULLS LAST;

-- Top performing agents by domain
CREATE OR REPLACE VIEW top_agents_by_domain AS
SELECT
    task_domain,
    agent_id,
    success_rate,
    avg_quality_score,
    avg_latency_ms,
    avg_cost_usd,
    sample_size,
    ROW_NUMBER() OVER (PARTITION BY task_domain ORDER BY success_rate DESC, avg_quality_score DESC) as rank
FROM agent_performance_benchmarks
WHERE measured_at > NOW() - INTERVAL '30 days';

-- Federation network health
CREATE OR REPLACE VIEW federation_network_health AS
SELECT
    COUNT(DISTINCT source_deployment_hash) as active_deployments,
    COUNT(*) as total_patterns,
    COUNT(DISTINCT domain) as domains_covered,
    AVG(effectiveness_score) as avg_effectiveness,
    AVG(success_rate) as avg_success_rate,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as patterns_last_7_days,
    COUNT(*) FILTER (WHERE sharing_level = 'public') as public_patterns,
    COUNT(*) FILTER (WHERE sharing_level = 'anonymous') as anonymous_patterns
FROM federated_patterns;

-- Budget utilization summary
CREATE OR REPLACE VIEW budget_utilization_summary AS
SELECT
    b.agent_id,
    b.daily_budget_usd,
    b.monthly_budget_usd,
    COALESCE(SUM(CASE WHEN t.created_at >= CURRENT_DATE THEN t.cost_usd ELSE 0 END), 0) as daily_spend,
    COALESCE(SUM(CASE WHEN t.created_at >= date_trunc('month', CURRENT_DATE) THEN t.cost_usd ELSE 0 END), 0) as monthly_spend,
    (COALESCE(SUM(CASE WHEN t.created_at >= CURRENT_DATE THEN t.cost_usd ELSE 0 END), 0) / NULLIF(b.daily_budget_usd, 0)) * 100 as daily_pct_used,
    (COALESCE(SUM(CASE WHEN t.created_at >= date_trunc('month', CURRENT_DATE) THEN t.cost_usd ELSE 0 END), 0) / NULLIF(b.monthly_budget_usd, 0)) * 100 as monthly_pct_used
FROM cost_budgets b
LEFT JOIN cost_tracking t ON b.agent_id = t.agent_id
GROUP BY b.agent_id, b.daily_budget_usd, b.monthly_budget_usd;

-- Audit event summary
CREATE OR REPLACE VIEW audit_event_summary AS
SELECT
    event_type,
    COUNT(*) as event_count,
    COUNT(DISTINCT agent_id) as unique_agents,
    MIN(created_at) as first_occurrence,
    MAX(created_at) as last_occurrence
FROM audit_events
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY event_type
ORDER BY event_count DESC;

-- ============================================================================
-- Functions for Common Operations
-- ============================================================================

-- Get agent recommendation by task domain
CREATE OR REPLACE FUNCTION get_agent_recommendation(
    p_task_domain TEXT,
    p_priority TEXT DEFAULT 'balanced'  -- quality, cost, speed, balanced
) RETURNS TABLE (
    agent_id TEXT,
    name TEXT,
    cost_per_task_usd REAL,
    quality_score REAL,
    speed_score REAL,
    value_score REAL,
    recommendation_score REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.agent_id,
        m.name,
        p.cost_per_task_usd,
        p.quality_score,
        p.speed_score,
        p.value_score,
        CASE
            WHEN p_priority = 'quality' THEN p.quality_score
            WHEN p_priority = 'cost' THEN 1.0 - (p.cost_per_task_usd / NULLIF((SELECT MAX(cost_per_task_usd) FROM agent_cost_quality_profiles WHERE task_domain = p_task_domain), 0))
            WHEN p_priority = 'speed' THEN p.speed_score
            ELSE p.value_score
        END as recommendation_score
    FROM agent_marketplace m
    JOIN agent_cost_quality_profiles p ON m.agent_id = p.agent_id
    WHERE m.status = 'active'
      AND p.task_domain = p_task_domain
    ORDER BY recommendation_score DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_agent_recommendation IS 'Get best agent recommendation for task domain';

-- Check budget availability
CREATE OR REPLACE FUNCTION check_budget_available(
    p_agent_id TEXT,
    p_estimated_cost REAL
) RETURNS BOOLEAN AS $$
DECLARE
    v_daily_budget REAL;
    v_monthly_budget REAL;
    v_daily_spend REAL;
    v_monthly_spend REAL;
BEGIN
    -- Get budget limits
    SELECT daily_budget_usd, monthly_budget_usd
    INTO v_daily_budget, v_monthly_budget
    FROM cost_budgets
    WHERE agent_id = p_agent_id;

    IF NOT FOUND THEN
        -- No budget set, allow operation
        RETURN TRUE;
    END IF;

    -- Get current spend
    SELECT
        COALESCE(SUM(CASE WHEN created_at >= CURRENT_DATE THEN cost_usd ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN created_at >= date_trunc('month', CURRENT_DATE) THEN cost_usd ELSE 0 END), 0)
    INTO v_daily_spend, v_monthly_spend
    FROM cost_tracking
    WHERE agent_id = p_agent_id;

    -- Check limits
    IF v_daily_spend + p_estimated_cost > v_daily_budget THEN
        RETURN FALSE;
    END IF;

    IF v_monthly_spend + p_estimated_cost > v_monthly_budget THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION check_budget_available IS 'Check if budget allows operation';

-- ============================================================================
-- Triggers
-- ============================================================================

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_platform_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_marketplace_timestamp
BEFORE UPDATE ON agent_marketplace
FOR EACH ROW
EXECUTE FUNCTION update_platform_timestamp();

CREATE TRIGGER trigger_update_profiles_timestamp
BEFORE UPDATE ON agent_cost_quality_profiles
FOR EACH ROW
EXECUTE FUNCTION update_platform_timestamp();

CREATE TRIGGER trigger_update_federation_nodes_timestamp
BEFORE UPDATE ON federation_nodes
FOR EACH ROW
EXECUTE FUNCTION update_platform_timestamp();

CREATE TRIGGER trigger_update_budgets_timestamp
BEFORE UPDATE ON cost_budgets
FOR EACH ROW
EXECUTE FUNCTION update_platform_timestamp();

COMMENT ON TRIGGER trigger_update_marketplace_timestamp ON agent_marketplace IS
    'Automatically update timestamp on marketplace updates';
COMMENT ON TRIGGER trigger_update_profiles_timestamp ON agent_cost_quality_profiles IS
    'Automatically update timestamp on profile updates';
COMMENT ON TRIGGER trigger_update_federation_nodes_timestamp ON federation_nodes IS
    'Automatically update timestamp on node updates';
COMMENT ON TRIGGER trigger_update_budgets_timestamp ON cost_budgets IS
    'Automatically update timestamp on budget updates';
