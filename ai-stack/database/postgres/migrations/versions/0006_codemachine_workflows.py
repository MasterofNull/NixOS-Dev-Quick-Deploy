"""Add CodeMachine workflow tracking tables and views

Revision ID: 0006_codemachine_workflows
Revises: 0005_pgvector_embeddings
Create Date: 2025-11-29
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0006_codemachine_workflows"
down_revision = "0005_pgvector_embeddings"
branch_labels = None
depends_on = None


CREATE_TABLE_AND_VIEW = """
CREATE TABLE IF NOT EXISTS codemachine_workflows (
    workflow_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    specification TEXT NOT NULL,
    engines TEXT[] NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    generated_files TEXT[],
    execution_time FLOAT,
    agent_metrics JSONB,
    errors TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT valid_codemachine_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_codemachine_workflows_status ON codemachine_workflows(status);
CREATE INDEX IF NOT EXISTS idx_codemachine_workflows_created ON codemachine_workflows(created_at DESC);

CREATE MATERIALIZED VIEW IF NOT EXISTS codemachine_agent_performance AS
SELECT
    unnest(engines) AS engine,
    COUNT(*) AS total_workflows,
    COUNT(*) FILTER (WHERE status = 'completed') AS successful_workflows,
    AVG(execution_time) FILTER (WHERE status = 'completed') AS avg_execution_time,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY execution_time)
        FILTER (WHERE status = 'completed') AS median_execution_time
FROM codemachine_workflows
GROUP BY engine;

CREATE OR REPLACE FUNCTION refresh_codemachine_metrics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY codemachine_agent_performance;
END;
$$ LANGUAGE plpgsql;
"""


DROP_TABLE_AND_VIEW = """
DROP FUNCTION IF EXISTS refresh_codemachine_metrics();
DROP MATERIALIZED VIEW IF EXISTS codemachine_agent_performance;
DROP TABLE IF EXISTS codemachine_workflows;
"""


def upgrade():
    op.execute(CREATE_TABLE_AND_VIEW)


def downgrade():
    op.execute(DROP_TABLE_AND_VIEW)
