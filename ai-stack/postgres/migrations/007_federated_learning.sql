-- Federated Learning Schema
-- Phase 2: Cross-Agent Knowledge Federation
--
-- Enables agents to learn from each other's successes:
-- - Pattern aggregation across agent types
-- - Cross-agent effectiveness metrics
-- - Recommendation engine for knowledge sharing
-- - Agent capability matrix for optimal routing

-- ============================================================================
-- Agent Patterns: Successful patterns discovered by each agent type
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type TEXT NOT NULL,  -- claude, qwen, codex, gemini, aider, continue, etc.
    task_domain TEXT NOT NULL, -- nixos, python, debugging, refactoring, testing, etc.
    pattern_type TEXT NOT NULL, -- solution, workflow, command, configuration, etc.
    pattern_content JSONB NOT NULL,
    success_rate REAL DEFAULT 0.0 CHECK (success_rate >= 0 AND success_rate <= 1),
    usage_count INTEGER DEFAULT 0,
    total_attempts INTEGER DEFAULT 0,
    avg_completion_time_ms INTEGER DEFAULT 0,
    avg_token_efficiency REAL DEFAULT 0.0,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    last_used TIMESTAMPTZ,
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',

    -- Pattern fingerprint for deduplication
    pattern_hash TEXT GENERATED ALWAYS AS (
        encode(sha256(convert_to(pattern_content::text, 'UTF8')), 'hex')
    ) STORED,

    UNIQUE(agent_type, task_domain, pattern_hash)
);

CREATE INDEX idx_agent_patterns_agent_type ON agent_patterns(agent_type);
CREATE INDEX idx_agent_patterns_task_domain ON agent_patterns(task_domain);
CREATE INDEX idx_agent_patterns_success_rate ON agent_patterns(success_rate DESC);
CREATE INDEX idx_agent_patterns_usage_count ON agent_patterns(usage_count DESC);
CREATE INDEX idx_agent_patterns_last_used ON agent_patterns(last_used DESC NULLS LAST);
CREATE INDEX idx_agent_patterns_tags ON agent_patterns USING gin(tags);

COMMENT ON TABLE agent_patterns IS 'Successful patterns discovered by agents, enabling cross-agent learning';
COMMENT ON COLUMN agent_patterns.agent_type IS 'Agent that discovered this pattern (claude, qwen, etc.)';
COMMENT ON COLUMN agent_patterns.task_domain IS 'Problem domain (nixos, python, debugging, etc.)';
COMMENT ON COLUMN agent_patterns.pattern_type IS 'Type of pattern (solution, workflow, command, etc.)';
COMMENT ON COLUMN agent_patterns.success_rate IS 'Success rate when this pattern is applied (0-1)';
COMMENT ON COLUMN agent_patterns.avg_token_efficiency IS 'Tokens per successful completion (lower is better)';

-- ============================================================================
-- Cross-Agent Recommendations: Suggest patterns from one agent to another
-- ============================================================================

CREATE TABLE IF NOT EXISTS cross_agent_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_agent TEXT NOT NULL,     -- Agent that discovered the pattern
    target_agent TEXT NOT NULL,     -- Agent recommended to try it
    pattern_id UUID NOT NULL REFERENCES agent_patterns(id) ON DELETE CASCADE,
    recommendation_reason TEXT,
    confidence_score REAL DEFAULT 0.0 CHECK (confidence_score >= 0 AND confidence_score <= 1),
    recommended_at TIMESTAMPTZ DEFAULT NOW(),
    adopted BOOLEAN DEFAULT false,
    adoption_result TEXT,           -- success, failure, no_data, rejected
    adopted_at TIMESTAMPTZ,
    result_metadata JSONB DEFAULT '{}',

    UNIQUE(pattern_id, target_agent, recommended_at)
);

CREATE INDEX idx_cross_agent_recs_source ON cross_agent_recommendations(source_agent);
CREATE INDEX idx_cross_agent_recs_target ON cross_agent_recommendations(target_agent);
CREATE INDEX idx_cross_agent_recs_pattern ON cross_agent_recommendations(pattern_id);
CREATE INDEX idx_cross_agent_recs_adopted ON cross_agent_recommendations(adopted);
CREATE INDEX idx_cross_agent_recs_result ON cross_agent_recommendations(adoption_result);

COMMENT ON TABLE cross_agent_recommendations IS 'Recommendations for agents to try patterns discovered by other agents';
COMMENT ON COLUMN cross_agent_recommendations.confidence_score IS 'Confidence that this pattern will work for target agent (0-1)';
COMMENT ON COLUMN cross_agent_recommendations.adoption_result IS 'Outcome when target agent tried the pattern';

-- ============================================================================
-- Agent Capability Matrix: Strengths and weaknesses by task domain
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_capability_matrix (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type TEXT NOT NULL,
    task_domain TEXT NOT NULL,
    capability_score REAL DEFAULT 0.5 CHECK (capability_score >= 0 AND capability_score <= 1),
    total_attempts INTEGER DEFAULT 0,
    successful_attempts INTEGER DEFAULT 0,
    avg_completion_time_ms INTEGER DEFAULT 0,
    avg_quality_score REAL DEFAULT 0.0,
    avg_token_usage INTEGER DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    sample_size INTEGER DEFAULT 0,  -- Number of data points used for calculation
    confidence_level REAL DEFAULT 0.0 CHECK (confidence_level >= 0 AND confidence_level <= 1),

    UNIQUE(agent_type, task_domain)
);

CREATE INDEX idx_agent_capability_agent_type ON agent_capability_matrix(agent_type);
CREATE INDEX idx_agent_capability_task_domain ON agent_capability_matrix(task_domain);
CREATE INDEX idx_agent_capability_score ON agent_capability_matrix(capability_score DESC);

COMMENT ON TABLE agent_capability_matrix IS 'Capability scores for each agent by task domain, enabling smart routing';
COMMENT ON COLUMN agent_capability_matrix.capability_score IS 'Overall capability score combining success rate, quality, and efficiency (0-1)';
COMMENT ON COLUMN agent_capability_matrix.confidence_level IS 'Statistical confidence in the capability score (0-1)';

-- ============================================================================
-- Pattern Application History: Track when patterns are used and their outcomes
-- ============================================================================

CREATE TABLE IF NOT EXISTS pattern_application_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_id UUID NOT NULL REFERENCES agent_patterns(id) ON DELETE CASCADE,
    agent_type TEXT NOT NULL,
    task_description TEXT,
    task_domain TEXT,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    success BOOLEAN,
    completion_time_ms INTEGER,
    quality_score REAL,
    token_usage INTEGER,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_pattern_history_pattern ON pattern_application_history(pattern_id);
CREATE INDEX idx_pattern_history_agent ON pattern_application_history(agent_type);
CREATE INDEX idx_pattern_history_domain ON pattern_application_history(task_domain);
CREATE INDEX idx_pattern_history_success ON pattern_application_history(success);
CREATE INDEX idx_pattern_history_applied_at ON pattern_application_history(applied_at DESC);

COMMENT ON TABLE pattern_application_history IS 'Historical record of pattern applications and outcomes';

-- ============================================================================
-- Federated Learning Sessions: Track cross-agent learning cycles
-- ============================================================================

CREATE TABLE IF NOT EXISTS federated_learning_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_type TEXT NOT NULL, -- pattern_synthesis, capability_update, recommendation_generation
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running', -- running, completed, failed
    patterns_analyzed INTEGER DEFAULT 0,
    recommendations_generated INTEGER DEFAULT 0,
    capability_updates INTEGER DEFAULT 0,
    insights TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_federated_sessions_status ON federated_learning_sessions(status);
CREATE INDEX idx_federated_sessions_started ON federated_learning_sessions(started_at DESC);

COMMENT ON TABLE federated_learning_sessions IS 'Federated learning cycles that synthesize cross-agent knowledge';

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- Top patterns by agent type
CREATE OR REPLACE VIEW top_patterns_by_agent AS
SELECT
    agent_type,
    task_domain,
    pattern_type,
    COUNT(*) as pattern_count,
    AVG(success_rate) as avg_success_rate,
    SUM(usage_count) as total_usage
FROM agent_patterns
GROUP BY agent_type, task_domain, pattern_type
ORDER BY total_usage DESC;

-- Cross-agent learning effectiveness
CREATE OR REPLACE VIEW cross_agent_learning_effectiveness AS
SELECT
    source_agent,
    target_agent,
    COUNT(*) as total_recommendations,
    SUM(CASE WHEN adopted THEN 1 ELSE 0 END) as adopted_count,
    SUM(CASE WHEN adoption_result = 'success' THEN 1 ELSE 0 END) as success_count,
    ROUND(
        SUM(CASE WHEN adoption_result = 'success' THEN 1 ELSE 0 END)::numeric /
        NULLIF(SUM(CASE WHEN adopted THEN 1 ELSE 0 END), 0) * 100,
        2
    ) as success_rate_pct
FROM cross_agent_recommendations
GROUP BY source_agent, target_agent
ORDER BY success_count DESC;

-- Agent capability rankings by domain
CREATE OR REPLACE VIEW agent_capability_rankings AS
SELECT
    task_domain,
    agent_type,
    capability_score,
    total_attempts,
    successful_attempts,
    ROUND(successful_attempts::numeric / NULLIF(total_attempts, 0) * 100, 2) as success_rate_pct,
    avg_completion_time_ms,
    ROW_NUMBER() OVER (PARTITION BY task_domain ORDER BY capability_score DESC) as rank
FROM agent_capability_matrix
WHERE sample_size >= 5  -- Only show capabilities with sufficient data
ORDER BY task_domain, capability_score DESC;

-- Recent pattern discoveries
CREATE OR REPLACE VIEW recent_pattern_discoveries AS
SELECT
    ap.agent_type,
    ap.task_domain,
    ap.pattern_type,
    ap.success_rate,
    ap.usage_count,
    ap.first_seen,
    ap.last_updated,
    COUNT(car.id) as recommendation_count
FROM agent_patterns ap
LEFT JOIN cross_agent_recommendations car ON ap.id = car.pattern_id
WHERE ap.first_seen >= NOW() - INTERVAL '7 days'
GROUP BY ap.id, ap.agent_type, ap.task_domain, ap.pattern_type,
         ap.success_rate, ap.usage_count, ap.first_seen, ap.last_updated
ORDER BY ap.first_seen DESC;

-- ============================================================================
-- Functions for Common Operations
-- ============================================================================

-- Update pattern metrics after application
CREATE OR REPLACE FUNCTION update_pattern_metrics(
    p_pattern_id UUID,
    p_success BOOLEAN,
    p_completion_time_ms INTEGER,
    p_token_usage INTEGER
) RETURNS VOID AS $$
BEGIN
    UPDATE agent_patterns
    SET
        total_attempts = total_attempts + 1,
        usage_count = CASE WHEN p_success THEN usage_count + 1 ELSE usage_count END,
        success_rate = (
            (success_rate * total_attempts + CASE WHEN p_success THEN 1 ELSE 0 END) /
            (total_attempts + 1)
        ),
        avg_completion_time_ms = (
            (avg_completion_time_ms * total_attempts + p_completion_time_ms) /
            (total_attempts + 1)
        ),
        avg_token_efficiency = CASE
            WHEN p_success THEN (
                (avg_token_efficiency * usage_count + p_token_usage) /
                (usage_count + 1)
            )
            ELSE avg_token_efficiency
        END,
        last_used = NOW(),
        last_updated = NOW()
    WHERE id = p_pattern_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_pattern_metrics IS 'Update pattern metrics after an application attempt';

-- Calculate capability score
CREATE OR REPLACE FUNCTION calculate_capability_score(
    p_success_rate REAL,
    p_avg_quality REAL,
    p_avg_time_ms INTEGER,
    p_avg_tokens INTEGER
) RETURNS REAL AS $$
DECLARE
    time_penalty REAL;
    token_penalty REAL;
BEGIN
    -- Normalize time penalty (assuming 30s is baseline)
    time_penalty := LEAST(1.0, 30000.0 / GREATEST(p_avg_time_ms, 1000));

    -- Normalize token penalty (assuming 500 tokens is baseline)
    token_penalty := LEAST(1.0, 500.0 / GREATEST(p_avg_tokens, 100));

    -- Weighted combination: 50% success, 25% quality, 15% speed, 10% efficiency
    RETURN (
        p_success_rate * 0.5 +
        p_avg_quality * 0.25 +
        time_penalty * 0.15 +
        token_penalty * 0.10
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_capability_score IS 'Calculate overall capability score from component metrics';

-- ============================================================================
-- Triggers for Automatic Updates
-- ============================================================================

-- Automatically update capability matrix when patterns change
CREATE OR REPLACE FUNCTION update_capability_matrix_from_patterns()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO agent_capability_matrix (
        agent_type,
        task_domain,
        capability_score,
        total_attempts,
        successful_attempts,
        avg_completion_time_ms,
        avg_quality_score,
        avg_token_usage,
        sample_size,
        confidence_level
    )
    SELECT
        NEW.agent_type,
        NEW.task_domain,
        calculate_capability_score(
            NEW.success_rate,
            0.75,  -- Default quality score
            NEW.avg_completion_time_ms,
            NEW.avg_token_efficiency::integer
        ),
        NEW.total_attempts,
        (NEW.total_attempts * NEW.success_rate)::integer,
        NEW.avg_completion_time_ms,
        0.75,  -- Default quality score
        NEW.avg_token_efficiency::integer,
        1,
        LEAST(NEW.total_attempts / 10.0, 1.0)  -- Confidence increases with attempts
    ON CONFLICT (agent_type, task_domain)
    DO UPDATE SET
        total_attempts = agent_capability_matrix.total_attempts + 1,
        successful_attempts = (
            agent_capability_matrix.successful_attempts +
            (NEW.total_attempts * NEW.success_rate)::integer
        ),
        capability_score = calculate_capability_score(
            (agent_capability_matrix.successful_attempts::real /
             GREATEST(agent_capability_matrix.total_attempts, 1)),
            agent_capability_matrix.avg_quality_score,
            agent_capability_matrix.avg_completion_time_ms,
            agent_capability_matrix.avg_token_usage
        ),
        sample_size = agent_capability_matrix.sample_size + 1,
        confidence_level = LEAST(agent_capability_matrix.sample_size / 10.0, 1.0),
        last_updated = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_capability_matrix
AFTER INSERT OR UPDATE ON agent_patterns
FOR EACH ROW
WHEN (NEW.total_attempts > 0)
EXECUTE FUNCTION update_capability_matrix_from_patterns();

COMMENT ON TRIGGER trigger_update_capability_matrix ON agent_patterns IS
    'Automatically update capability matrix when patterns are added or updated';
