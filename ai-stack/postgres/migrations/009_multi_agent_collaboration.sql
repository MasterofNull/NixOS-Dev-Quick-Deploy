-- Multi-Agent Collaboration Schema
-- Phase 4: Advanced Multi-Agent Collaboration
--
-- Tracks multi-agent collaborations, plans, consensus decisions,
-- and collaboration effectiveness metrics.

-- ============================================================================
-- Collaborations: Multi-agent collaboration sessions
-- ============================================================================

CREATE TABLE IF NOT EXISTS collaborations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collaboration_id TEXT UNIQUE NOT NULL,
    objective TEXT NOT NULL,
    collaboration_type TEXT NOT NULL,  -- planning, execution, review, research
    participating_agents JSONB NOT NULL DEFAULT '[]',  -- [agent_id, ...]
    coordination_pattern TEXT,  -- peer_to_peer, hub_and_spoke, hierarchical
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'failed', 'paused')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_collaborations_status ON collaborations(status);
CREATE INDEX idx_collaborations_started_at ON collaborations(started_at DESC);
CREATE INDEX idx_collaborations_type ON collaborations(collaboration_type);

COMMENT ON TABLE collaborations IS 'Multi-agent collaboration sessions';

-- ============================================================================
-- Collaboration Messages: Inter-agent communication
-- ============================================================================

CREATE TABLE IF NOT EXISTS collaboration_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id TEXT UNIQUE NOT NULL,
    collaboration_id TEXT REFERENCES collaborations(collaboration_id) ON DELETE CASCADE,
    sender_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,  -- agent_id or 'broadcast'
    message_type TEXT NOT NULL,
    content JSONB NOT NULL,
    priority INTEGER DEFAULT 3 CHECK (priority >= 1 AND priority <= 4),
    requires_response BOOLEAN DEFAULT FALSE,
    response_deadline TIMESTAMPTZ,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    received_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_collab_messages_collaboration ON collaboration_messages(collaboration_id);
CREATE INDEX idx_collab_messages_sender ON collaboration_messages(sender_id);
CREATE INDEX idx_collab_messages_recipient ON collaboration_messages(recipient_id);
CREATE INDEX idx_collab_messages_sent_at ON collaboration_messages(sent_at DESC);

COMMENT ON TABLE collaboration_messages IS 'Messages exchanged between agents in collaborations';

-- ============================================================================
-- Collaborative Plans: Multi-agent planning artifacts
-- ============================================================================

CREATE TABLE IF NOT EXISTS collaborative_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id TEXT UNIQUE NOT NULL,
    collaboration_id TEXT REFERENCES collaborations(collaboration_id) ON DELETE CASCADE,
    objective TEXT NOT NULL,
    contributions_count INTEGER DEFAULT 0,
    synthesized_phases_count INTEGER DEFAULT 0,
    overall_strategy TEXT,
    estimated_timeline TEXT,
    critical_risks JSONB DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'collecting' CHECK (status IN ('collecting', 'synthesized', 'approved', 'executing', 'completed')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synthesized_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_collab_plans_collaboration ON collaborative_plans(collaboration_id);
CREATE INDEX idx_collab_plans_status ON collaborative_plans(status);
CREATE INDEX idx_collab_plans_created_at ON collaborative_plans(created_at DESC);

COMMENT ON TABLE collaborative_plans IS 'Plans created through multi-agent collaboration';

-- ============================================================================
-- Plan Contributions: Individual agent contributions to plans
-- ============================================================================

CREATE TABLE IF NOT EXISTS plan_contributions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contribution_id TEXT UNIQUE NOT NULL,
    plan_id TEXT REFERENCES collaborative_plans(plan_id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    agent_capability_score REAL NOT NULL CHECK (agent_capability_score >= 0 AND agent_capability_score <= 1),
    phase_type TEXT NOT NULL,  -- research, design, implementation, testing, review, deployment
    description TEXT NOT NULL,
    approach TEXT NOT NULL,
    estimated_effort TEXT,
    dependencies JSONB DEFAULT '[]',
    risks JSONB DEFAULT '[]',
    confidence REAL DEFAULT 0.8 CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_plan_contributions_plan ON plan_contributions(plan_id);
CREATE INDEX idx_plan_contributions_agent ON plan_contributions(agent_id);
CREATE INDEX idx_plan_contributions_phase ON plan_contributions(phase_type);

COMMENT ON TABLE plan_contributions IS 'Individual agent contributions to collaborative plans';

-- ============================================================================
-- Consensus Decisions: Multi-agent consensus on decisions
-- ============================================================================

CREATE TABLE IF NOT EXISTS consensus_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id TEXT UNIQUE NOT NULL,
    collaboration_id TEXT REFERENCES collaborations(collaboration_id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,  -- ID of item being reviewed
    final_verdict TEXT NOT NULL,  -- approve, approve_with_changes, reject, needs_revision, abstain
    consensus_score REAL NOT NULL CHECK (consensus_score >= 0 AND consensus_score <= 1),
    total_reviews INTEGER DEFAULT 0,
    approval_rate REAL DEFAULT 0.0,
    weighted_average_score REAL DEFAULT 0.0,
    escalated BOOLEAN DEFAULT FALSE,
    escalation_reason TEXT,
    decision_method TEXT,  -- weighted_voting, majority, unanimous, expert_override
    decided_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_consensus_decisions_collaboration ON consensus_decisions(collaboration_id);
CREATE INDEX idx_consensus_decisions_item ON consensus_decisions(item_id);
CREATE INDEX idx_consensus_decisions_escalated ON consensus_decisions(escalated);
CREATE INDEX idx_consensus_decisions_decided_at ON consensus_decisions(decided_at DESC);

COMMENT ON TABLE consensus_decisions IS 'Consensus decisions reached by multiple agents';

-- ============================================================================
-- Consensus Reviews: Individual agent reviews contributing to consensus
-- ============================================================================

CREATE TABLE IF NOT EXISTS consensus_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id TEXT UNIQUE NOT NULL,
    decision_id TEXT REFERENCES consensus_decisions(decision_id) ON DELETE CASCADE,
    reviewer_id TEXT NOT NULL,
    reviewer_capability REAL NOT NULL CHECK (reviewer_capability >= 0 AND reviewer_capability <= 1),
    reviewer_reliability REAL NOT NULL CHECK (reviewer_reliability >= 0 AND reviewer_reliability <= 1),
    verdict TEXT NOT NULL,
    overall_score REAL NOT NULL CHECK (overall_score >= 0 AND overall_score <= 1),
    criteria_scores JSONB DEFAULT '{}',
    feedback TEXT,
    suggested_improvements JSONB DEFAULT '[]',
    confidence REAL DEFAULT 0.8 CHECK (confidence >= 0 AND confidence <= 1),
    review_time_ms INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_consensus_reviews_decision ON consensus_reviews(decision_id);
CREATE INDEX idx_consensus_reviews_reviewer ON consensus_reviews(reviewer_id);
CREATE INDEX idx_consensus_reviews_verdict ON consensus_reviews(verdict);

COMMENT ON TABLE consensus_reviews IS 'Individual reviews contributing to consensus decisions';

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- Active collaborations summary
CREATE OR REPLACE VIEW active_collaborations_summary AS
SELECT
    c.collaboration_id,
    c.objective,
    c.collaboration_type,
    c.coordination_pattern,
    jsonb_array_length(c.participating_agents) as agent_count,
    COUNT(DISTINCT cm.id) as total_messages,
    COUNT(DISTINCT CASE WHEN cm.sent_at >= NOW() - INTERVAL '1 hour' THEN cm.id END) as messages_last_hour,
    c.started_at,
    EXTRACT(EPOCH FROM (NOW() - c.started_at))/3600 as duration_hours
FROM collaborations c
LEFT JOIN collaboration_messages cm ON c.collaboration_id = cm.collaboration_id
WHERE c.status = 'active'
GROUP BY c.id, c.collaboration_id, c.objective, c.collaboration_type, c.coordination_pattern, c.participating_agents, c.started_at
ORDER BY c.started_at DESC;

-- Collaboration effectiveness
CREATE OR REPLACE VIEW collaboration_effectiveness AS
SELECT
    c.collaboration_id,
    c.objective,
    c.collaboration_type,
    jsonb_array_length(c.participating_agents) as team_size,
    COUNT(DISTINCT cp.id) as plans_created,
    COUNT(DISTINCT cd.id) as decisions_made,
    AVG(cd.consensus_score) as avg_consensus_score,
    SUM(CASE WHEN cd.escalated THEN 1 ELSE 0 END) as escalations_count,
    EXTRACT(EPOCH FROM (COALESCE(c.completed_at, NOW()) - c.started_at))/3600 as duration_hours
FROM collaborations c
LEFT JOIN collaborative_plans cp ON c.collaboration_id = cp.collaboration_id
LEFT JOIN consensus_decisions cd ON c.collaboration_id = cd.collaboration_id
GROUP BY c.id, c.collaboration_id, c.objective, c.collaboration_type, c.participating_agents, c.started_at, c.completed_at
ORDER BY c.started_at DESC;

-- Agent collaboration metrics
CREATE OR REPLACE VIEW agent_collaboration_metrics AS
SELECT
    agent_id,
    COUNT(DISTINCT collaboration_id) as collaborations_participated,
    COUNT(DISTINCT contribution_id) as total_contributions,
    AVG(agent_capability_score) as avg_capability_score,
    AVG(confidence) as avg_contribution_confidence,
    COUNT(DISTINCT CASE WHEN phase_type = 'implementation' THEN contribution_id END) as implementation_contributions,
    COUNT(DISTINCT CASE WHEN phase_type = 'review' THEN contribution_id END) as review_contributions
FROM (
    SELECT
        jsonb_array_elements_text(c.participating_agents) as agent_id,
        c.collaboration_id
    FROM collaborations c
) agents
LEFT JOIN plan_contributions pc ON agents.agent_id = pc.agent_id
GROUP BY agent_id
ORDER BY collaborations_participated DESC;

-- Consensus decision summary
CREATE OR REPLACE VIEW consensus_decision_summary AS
SELECT
    cd.decision_id,
    cd.item_id,
    cd.final_verdict,
    cd.consensus_score,
    cd.total_reviews,
    cd.approval_rate,
    cd.weighted_average_score,
    cd.escalated,
    cd.escalation_reason,
    cd.decision_method,
    cd.decided_at,
    COUNT(cr.id) as review_count,
    AVG(cr.overall_score) as avg_review_score,
    AVG(cr.confidence) as avg_reviewer_confidence
FROM consensus_decisions cd
LEFT JOIN consensus_reviews cr ON cd.decision_id = cr.decision_id
GROUP BY cd.id, cd.decision_id, cd.item_id, cd.final_verdict, cd.consensus_score,
         cd.total_reviews, cd.approval_rate, cd.weighted_average_score,
         cd.escalated, cd.escalation_reason, cd.decision_method, cd.decided_at
ORDER BY cd.decided_at DESC;

-- ============================================================================
-- Functions for Common Operations
-- ============================================================================

-- Record collaboration completion
CREATE OR REPLACE FUNCTION complete_collaboration(
    p_collaboration_id TEXT,
    p_status TEXT DEFAULT 'completed'
) RETURNS VOID AS $$
BEGIN
    UPDATE collaborations
    SET
        status = p_status,
        completed_at = NOW()
    WHERE collaboration_id = p_collaboration_id
      AND status = 'active';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION complete_collaboration IS 'Mark a collaboration as completed';

-- Get collaboration statistics
CREATE OR REPLACE FUNCTION get_collaboration_stats(
    p_collaboration_id TEXT
) RETURNS TABLE (
    total_messages BIGINT,
    total_plans BIGINT,
    total_decisions BIGINT,
    avg_consensus_score REAL,
    escalation_count BIGINT,
    duration_hours NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(DISTINCT cm.id)::BIGINT as total_messages,
        COUNT(DISTINCT cp.id)::BIGINT as total_plans,
        COUNT(DISTINCT cd.id)::BIGINT as total_decisions,
        AVG(cd.consensus_score)::REAL as avg_consensus_score,
        SUM(CASE WHEN cd.escalated THEN 1 ELSE 0 END)::BIGINT as escalation_count,
        EXTRACT(EPOCH FROM (COALESCE(c.completed_at, NOW()) - c.started_at))::NUMERIC/3600 as duration_hours
    FROM collaborations c
    LEFT JOIN collaboration_messages cm ON c.collaboration_id = cm.collaboration_id
    LEFT JOIN collaborative_plans cp ON c.collaboration_id = cp.collaboration_id
    LEFT JOIN consensus_decisions cd ON c.collaboration_id = cd.collaboration_id
    WHERE c.collaboration_id = p_collaboration_id
    GROUP BY c.started_at, c.completed_at;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_collaboration_stats IS 'Get statistics for a collaboration';

-- ============================================================================
-- Triggers for Automatic Updates
-- ============================================================================

-- Auto-update collaboration metadata
CREATE OR REPLACE FUNCTION update_collaboration_timestamp()
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

CREATE TRIGGER trigger_update_collaboration_timestamp
BEFORE UPDATE ON collaborations
FOR EACH ROW
EXECUTE FUNCTION update_collaboration_timestamp();

CREATE TRIGGER trigger_update_plan_timestamp
BEFORE UPDATE ON collaborative_plans
FOR EACH ROW
EXECUTE FUNCTION update_collaboration_timestamp();

COMMENT ON TRIGGER trigger_update_collaboration_timestamp ON collaborations IS
    'Automatically update metadata timestamp on collaboration updates';

COMMENT ON TRIGGER trigger_update_plan_timestamp ON collaborative_plans IS
    'Automatically update metadata timestamp on plan updates';
