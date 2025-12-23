"""
CodeMachine-CLI Integration Client for AIDB MCP
Enables multi-agent workflow orchestration and spec-to-code generation
"""

import logging
import httpx
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """CodeMachine workflow execution states"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentEngine(Enum):
    """Supported AI engines for CodeMachine orchestration"""
    CLAUDE_CODE = "claude-code"
    OPENCODE = "opencode"
    CURSOR = "cursor"
    CODEX = "codex"
    CCR = "ccr"  # Claude Code Router
    AUGGIE = "auggie"
    # Local llama.cpp runtime (AMD ROCm compatible)
    QWEN_CODER = "qwen-coder"  # Qwen2.5-Coder-1.5B
    DEEPSEEK_R1 = "deepseek-r1"  # DeepSeek-R1-1.5B


@dataclass
class WorkflowSpec:
    """Specification for a CodeMachine workflow"""
    name: str
    description: str
    specification: str  # Markdown specification
    engines: List[AgentEngine]  # Which AI engines to use
    parallel: bool = True  # Enable parallel sub-agent execution
    timeout: int = 3600  # Workflow timeout in seconds


@dataclass
class WorkflowResult:
    """Result from CodeMachine workflow execution"""
    workflow_id: str
    status: WorkflowStatus
    generated_files: List[str]
    execution_time: float
    agent_metrics: Dict[str, Any]
    errors: Optional[List[str]] = None


class CodeMachineClient:
    """
    Client for interacting with CodeMachine-CLI orchestration engine

    Integrates with AIDB MCP for:
    - Storing workflow specifications and results in PostgreSQL
    - Caching intermediate artifacts in Redis
    - Tracking agent performance metrics
    - Coordinating with ML engine for intelligent agent selection
    """

    def __init__(self, base_url: str = "http://codemachine:3000"):
        self.base_url = base_url
        self.http_client = httpx.AsyncClient(timeout=300.0)

    async def health_check(self) -> bool:
        """Check if CodeMachine service is available"""
        try:
            response = await self.http_client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"CodeMachine health check failed: {e}")
            return False

    async def create_workflow(self, spec: WorkflowSpec) -> str:
        """
        Create a new CodeMachine workflow from specification

        Args:
            spec: Workflow specification with engines and parameters

        Returns:
            workflow_id: Unique identifier for tracking
        """
        logger.info(f"Creating CodeMachine workflow: {spec.name}")

        payload = {
            "name": spec.name,
            "description": spec.description,
            "specification": spec.specification,
            "engines": [e.value for e in spec.engines],
            "parallel_execution": spec.parallel,
            "timeout": spec.timeout
        }

        response = await self.http_client.post(
            f"{self.base_url}/workflows",
            json=payload
        )
        response.raise_for_status()

        result = response.json()
        workflow_id = result["workflow_id"]

        logger.info(f"Created workflow {workflow_id}")
        return workflow_id

    async def get_workflow_status(self, workflow_id: str) -> WorkflowStatus:
        """Get current status of a workflow"""
        response = await self.http_client.get(
            f"{self.base_url}/workflows/{workflow_id}/status"
        )
        response.raise_for_status()

        result = response.json()
        return WorkflowStatus(result["status"])

    async def get_workflow_result(self, workflow_id: str) -> WorkflowResult:
        """
        Retrieve complete workflow results including generated code

        Args:
            workflow_id: Workflow identifier

        Returns:
            WorkflowResult with generated files and metrics
        """
        response = await self.http_client.get(
            f"{self.base_url}/workflows/{workflow_id}"
        )
        response.raise_for_status()

        data = response.json()

        return WorkflowResult(
            workflow_id=workflow_id,
            status=WorkflowStatus(data["status"]),
            generated_files=data["generated_files"],
            execution_time=data["execution_time"],
            agent_metrics=data["agent_metrics"],
            errors=data.get("errors")
        )

    async def execute_workflow(
        self,
        spec: WorkflowSpec,
        poll_interval: int = 5
    ) -> WorkflowResult:
        """
        Execute a complete workflow and wait for results

        Args:
            spec: Workflow specification
            poll_interval: Status polling interval in seconds

        Returns:
            WorkflowResult when execution completes
        """
        workflow_id = await self.create_workflow(spec)

        while True:
            status = await self.get_workflow_status(workflow_id)

            if status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED):
                break

            await asyncio.sleep(poll_interval)

        return await self.get_workflow_result(workflow_id)

    async def list_workflows(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List recent workflows"""
        response = await self.http_client.get(
            f"{self.base_url}/workflows",
            params={"limit": limit}
        )
        response.raise_for_status()

        return response.json()["workflows"]

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow"""
        response = await self.http_client.post(
            f"{self.base_url}/workflows/{workflow_id}/cancel"
        )
        response.raise_for_status()

        return response.json()["cancelled"]

    async def get_agent_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics across all agents

        Useful for ML-based agent selection:
        - Success rates by agent engine
        - Average execution times
        - Task type affinity
        """
        response = await self.http_client.get(
            f"{self.base_url}/metrics/agents"
        )
        response.raise_for_status()

        return response.json()

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()


# ============================================================================
# Integration with AIDB MCP Database
# ============================================================================

async def store_workflow_in_db(
    conn,
    workflow_id: str,
    spec: WorkflowSpec,
    result: Optional[WorkflowResult] = None
):
    """
    Store CodeMachine workflow in AIDB PostgreSQL for persistence

    Enables:
    - Workflow history tracking
    - Cross-session context maintenance
    - ML-based workflow optimization
    """
    await conn.execute(
        """
        INSERT INTO codemachine_workflows (
            workflow_id, name, description, specification,
            engines, status, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
        ON CONFLICT (workflow_id) DO UPDATE
        SET status = EXCLUDED.status
        """,
        workflow_id,
        spec.name,
        spec.description,
        spec.specification,
        [e.value for e in spec.engines],
        result.status.value if result else WorkflowStatus.PENDING.value
    )

    if result:
        await conn.execute(
            """
            UPDATE codemachine_workflows
            SET
                status = $2,
                generated_files = $3,
                execution_time = $4,
                agent_metrics = $5,
                errors = $6,
                completed_at = NOW()
            WHERE workflow_id = $1
            """,
            workflow_id,
            result.status.value,
            result.generated_files,
            result.execution_time,
            result.agent_metrics,
            result.errors
        )


async def get_optimal_agent_for_task(
    conn,
    task_type: str,
    language: Optional[str] = None
) -> AgentEngine:
    """
    Use ML to select optimal agent engine for task

    Queries historical performance from database and uses
    scikit-learn models to predict best engine
    """
    # Query historical performance
    rows = await conn.fetch(
        """
        SELECT
            engines,
            AVG(execution_time) as avg_time,
            COUNT(*) FILTER (WHERE status = 'completed') as success_count,
            COUNT(*) as total_count
        FROM codemachine_workflows
        WHERE
            description LIKE $1
            AND ($2 IS NULL OR specification LIKE $2)
        GROUP BY engines
        ORDER BY success_count DESC, avg_time ASC
        LIMIT 5
        """,
        f"%{task_type}%",
        f"%{language}%" if language else None
    )

    if not rows:
        # Default to Claude Code for unknown tasks
        return AgentEngine.CLAUDE_CODE

    # Return engine with best historical performance
    best_engines = rows[0]["engines"]
    return AgentEngine(best_engines[0]) if best_engines else AgentEngine.CLAUDE_CODE


# ============================================================================
# Database Schema Migration for CodeMachine Integration
# ============================================================================

CODEMACHINE_SCHEMA = """
-- CodeMachine workflow tracking table
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
);

-- Index for performance queries
CREATE INDEX IF NOT EXISTS idx_codemachine_workflows_status ON codemachine_workflows(status);
CREATE INDEX IF NOT EXISTS idx_codemachine_workflows_created ON codemachine_workflows(created_at DESC);

-- Agent performance metrics materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS codemachine_agent_performance AS
SELECT
    unnest(engines) as engine,
    COUNT(*) as total_workflows,
    COUNT(*) FILTER (WHERE status = 'completed') as successful_workflows,
    AVG(execution_time) FILTER (WHERE status = 'completed') as avg_execution_time,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY execution_time)
        FILTER (WHERE status = 'completed') as median_execution_time
FROM codemachine_workflows
GROUP BY engine;

-- Refresh function for materialized view
CREATE OR REPLACE FUNCTION refresh_codemachine_metrics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY codemachine_agent_performance;
END;
$$ LANGUAGE plpgsql;
"""
