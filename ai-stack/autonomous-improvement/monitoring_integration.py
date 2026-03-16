"""
Monitoring Integration for Autonomous Improvement System

Tracks local LLM operations from autonomous improvement cycles
and records them in the monitoring system for value analysis.
"""

import asyncpg
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4


class MonitoringIntegration:
    """
    Integration layer between autonomous improvement and monitoring system.

    Tracks all local LLM operations with purpose, value, and contribution metadata.
    """

    def __init__(
        self,
        pg_host: str = "127.0.0.1",
        pg_port: int = 5432,
        pg_user: str = "postgres",
        pg_database: str = "ai_context",
        pg_password: Optional[str] = None,
    ):
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_database = pg_database
        self.pg_password = pg_password or os.getenv("POSTGRES_PASSWORD", "")

        self.conn: Optional[asyncpg.Connection] = None

    async def connect(self):
        """Establish async database connection."""
        if self.conn is None or self.conn.is_closed():
            self.conn = await asyncpg.connect(
                host=self.pg_host,
                port=self.pg_port,
                user=self.pg_user,
                database=self.pg_database,
                password=self.pg_password,
            )

    async def close(self):
        """Close database connection."""
        if self.conn and not self.conn.is_closed():
            await self.conn.close()

    async def track_llm_operation(
        self,
        operation_type: str,  # chat, embed, reasoning, analysis
        purpose: str,  # autonomous_trigger, hypothesis_generation, etc.
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        quality_score: float = 0.0,
        value_score: float = 0.0,
        contribution_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session_type: str = "autonomous",
    ) -> str:
        """
        Track a local LLM operation in monitoring system.

        Returns: operation_id
        """
        await self.connect()

        operation_id = str(uuid4())

        await self.conn.execute(
            """
            INSERT INTO local_llm_operations (
                operation_id, operation_type, purpose, input_tokens, output_tokens,
                latency_ms, quality_score, value_score, contribution_type, metadata, session_type
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            operation_id,
            operation_type,
            purpose,
            input_tokens,
            output_tokens,
            latency_ms,
            quality_score,
            value_score,
            contribution_type,
            json.dumps(metadata or {}),
            session_type,
        )

        return operation_id

    async def record_contribution(
        self,
        operation_id: str,
        contribution_type: str,  # hypothesis, pattern, summary, decision, data
        description: str,
        impact_score: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record a contribution made by local LLM.

        Returns: contribution_id
        """
        await self.connect()

        contribution_id = str(uuid4())

        await self.conn.execute(
            """
            INSERT INTO local_llm_contributions (
                contribution_id, operation_id, contribution_type, description, impact_score, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            contribution_id,
            operation_id,
            contribution_type,
            description,
            impact_score,
            json.dumps(metadata or {}),
        )

        return contribution_id

    async def mark_contribution_applied(
        self, contribution_id: str
    ) -> None:
        """Mark a contribution as applied to the system."""
        await self.connect()

        await self.conn.execute(
            """
            UPDATE local_llm_contributions
            SET status = 'applied', applied_at = NOW()
            WHERE contribution_id = $1
            """,
            contribution_id,
        )

    async def update_operation_value(
        self,
        operation_id: str,
        value_score: float,
        quality_score: Optional[float] = None,
    ) -> None:
        """Update operation value score after validation."""
        await self.connect()

        if quality_score is not None:
            await self.conn.execute(
                """
                UPDATE local_llm_operations
                SET value_score = $1, quality_score = $2
                WHERE operation_id = $3
                """,
                value_score,
                quality_score,
                operation_id,
            )
        else:
            await self.conn.execute(
                """
                UPDATE local_llm_operations
                SET value_score = $1
                WHERE operation_id = $2
                """,
                value_score,
                operation_id,
            )

    # Convenience methods for autonomous improvement system

    async def track_trigger_analysis(
        self,
        anomalies_analyzed: int,
        decision: bool,
        reasoning: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Track LLM trigger decision operation."""
        value_score = 0.8 if decision else 0.3  # High value if triggers improvement

        return await self.track_llm_operation(
            operation_type="reasoning",
            purpose="autonomous_trigger_decision",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            value_score=value_score,
            contribution_type="decision" if decision else None,
            metadata={
                "anomalies_analyzed": anomalies_analyzed,
                "should_trigger": decision,
                "reasoning": reasoning[:200],
                **(metadata or {}),
            },
            session_type="autonomous",
        )

    async def track_hypothesis_generation(
        self,
        hypotheses_count: int,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        hypotheses_summary: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Track hypothesis generation operation."""
        # Value based on number and quality of hypotheses
        value_score = min(0.5 + (hypotheses_count * 0.1), 1.0)

        return await self.track_llm_operation(
            operation_type="chat",
            purpose="hypothesis_generation",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            value_score=value_score,
            contribution_type="hypothesis",
            metadata={
                "hypotheses_count": hypotheses_count,
                "summary": hypotheses_summary[:200] if hypotheses_summary else None,
                **(metadata or {}),
            },
            session_type="autonomous",
        )

    async def track_hypothesis_as_contribution(
        self,
        operation_id: str,
        hypothesis_type: str,
        description: str,
        estimated_impact: float,
        priority: str,
    ) -> str:
        """Record a generated hypothesis as a contribution."""
        # Impact score based on priority and estimated impact
        impact_map = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.3}
        impact_score = impact_map.get(priority, 0.5) * estimated_impact

        return await self.record_contribution(
            operation_id=operation_id,
            contribution_type="hypothesis",
            description=f"[{hypothesis_type}] {description}",
            impact_score=impact_score,
            metadata={
                "hypothesis_type": hypothesis_type,
                "priority": priority,
                "estimated_impact": estimated_impact,
            },
        )

    async def track_pattern_extraction(
        self,
        patterns_found: int,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Track pattern extraction operation."""
        value_score = min(0.4 + (patterns_found * 0.15), 1.0)

        return await self.track_llm_operation(
            operation_type="analysis",
            purpose="pattern_extraction",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            value_score=value_score,
            contribution_type="pattern" if patterns_found > 0 else None,
            metadata={
                "patterns_found": patterns_found,
                **(metadata or {}),
            },
            session_type="autonomous",
        )

    async def track_summarization(
        self,
        source_type: str,  # logs, metrics, data
        summary_ratio: float,  # 0-1, how much was compressed
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Track summarization operation."""
        # Higher value for better compression
        value_score = 0.3 + (summary_ratio * 0.4)

        return await self.track_llm_operation(
            operation_type="chat",
            purpose=f"summarization_{source_type}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            value_score=value_score,
            contribution_type="summary",
            metadata={
                "source_type": source_type,
                "compression_ratio": summary_ratio,
                **(metadata or {}),
            },
            session_type="autonomous",
        )

    async def get_operation_stats(self, since_hours: int = 24) -> Dict[str, Any]:
        """Get operation statistics for monitoring."""
        await self.connect()

        stats = await self.conn.fetch(
            """
            SELECT
                COUNT(*) as total_operations,
                AVG(value_score) as avg_value_score,
                SUM(input_tokens + output_tokens) as total_tokens,
                COUNT(DISTINCT purpose) as unique_purposes,
                SUM(CASE WHEN contribution_type IS NOT NULL THEN 1 ELSE 0 END) as operations_with_contributions
            FROM local_llm_operations
            WHERE created_at >= NOW() - ($1 || ' hours')::interval
                AND session_type = 'autonomous'
            """,
            str(since_hours),
        )

        contrib_stats = await self.conn.fetch(
            """
            SELECT
                COUNT(*) as total_contributions,
                AVG(impact_score) as avg_impact_score,
                SUM(CASE WHEN status = 'applied' THEN 1 ELSE 0 END) as applied_count
            FROM local_llm_contributions
            WHERE created_at >= NOW() - ($1 || ' hours')::interval
            """,
            str(since_hours),
        )

        return {
            "operations": dict(stats[0]) if stats else {},
            "contributions": dict(contrib_stats[0]) if contrib_stats else {},
        }


# Helper functions for backward compatibility

async def track_autonomous_operation(
    operation_type: str,
    purpose: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    **kwargs
) -> str:
    """Helper function to track operation without class instantiation."""
    monitor = MonitoringIntegration()
    try:
        operation_id = await monitor.track_llm_operation(
            operation_type=operation_type,
            purpose=purpose,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            session_type="autonomous",
            **kwargs
        )
        return operation_id
    finally:
        await monitor.close()
