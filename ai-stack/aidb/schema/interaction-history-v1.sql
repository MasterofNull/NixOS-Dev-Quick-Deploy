-- Interaction History Schema v1.0
-- Created: 2026-05-14
-- Phase: 1 Slice 1.4
-- Purpose: Persistent metadata storage for interaction history

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Interaction history table
CREATE TABLE IF NOT EXISTS interaction_history (
    -- Primary key
    interaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Session/Context grouping
    session_id UUID,
    project VARCHAR(255),

    -- Core content
    query TEXT NOT NULL,
    response TEXT,

    -- Agent/Model metadata
    agent_type VARCHAR(50) NOT NULL, -- qwen, codex, claude, gemini, etc.
    model_used VARCHAR(100),
    role VARCHAR(50), -- implementer, reviewer, orchestrator

    -- Performance/Outcome metadata
    outcome VARCHAR(50) DEFAULT 'unknown', -- success, failure, timeout, error
    tokens_in INT DEFAULT 0,
    tokens_out INT DEFAULT 0,
    latency_ms INT DEFAULT 0,
    value_score FLOAT DEFAULT 0.0 CHECK (value_score >= 0.0 AND value_score <= 1.0),

    -- Additional flexible metadata
    metadata JSONB DEFAULT '{}',

    -- Audit trail
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX idx_interaction_history_agent_type ON interaction_history(agent_type);
CREATE INDEX idx_interaction_history_outcome ON interaction_history(outcome);
CREATE INDEX idx_interaction_history_created_at ON interaction_history(created_at);
CREATE INDEX idx_interaction_history_session_id ON interaction_history(session_id);
CREATE INDEX idx_interaction_history_project ON interaction_history(project);

-- GIN index for metadata JSONB search
CREATE INDEX idx_interaction_history_metadata ON interaction_history USING GIN (metadata);

-- Trigger: Update updated_at timestamp on changes
CREATE OR REPLACE FUNCTION update_interaction_history_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER interaction_history_update_timestamp
BEFORE UPDATE ON interaction_history
FOR EACH ROW EXECUTE FUNCTION update_interaction_history_timestamp();

-- Comments for documentation
COMMENT ON TABLE interaction_history IS
'Persistent storage for AI interaction history, enabling performance analysis and long-term context recovery.';

COMMENT ON COLUMN interaction_history.agent_type IS
'Type of agent that handled the query (e.g. qwen, claude).';

COMMENT ON COLUMN interaction_history.outcome IS
'The high-level result of the interaction (success/failure/etc).';

COMMENT ON COLUMN interaction_history.metadata IS
'Flexible JSON storage for extra interaction details like tool calls, validation results, or specific errors.';
