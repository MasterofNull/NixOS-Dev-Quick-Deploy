"""
Local LLM Operations Monitor

Tracks local LLM actions, contributions, and value delivery to the AI harness.
Ensures local models provide meaningful improvements between remote agent sessions.

Features:
- Operation tracking (chat, embedding, reasoning)
- Value scoring (quality, efficiency, impact)
- Contribution metrics (data created, improvements suggested, patterns extracted)
- Inter-session continuity (autonomous operation tracking)
- Dashboard-ready metrics export

Usage:
    # Monitor daemon
    python3 local_llm_monitor.py --daemon

    # Get metrics
    python3 local_llm_monitor.py --metrics

    # Value report
    python3 local_llm_monitor.py --value-report
"""

import asyncio
import asyncpg
import httpx
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

# Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ai_context")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

LLAMA_CHAT_URL = "http://localhost:8080"
LLAMA_EMBED_URL = "http://localhost:8081"

METRICS_FILE = Path("/var/log/nixos-ai-stack/local-llm-metrics.jsonl")
METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
)
logger = logging.getLogger("local_llm_monitor")


class LocalLLMMonitor:
    """Monitor local LLM operations and measure value contribution."""

    def __init__(self):
        self.db: Optional[asyncpg.Connection] = None
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.operation_counts = defaultdict(int)
        self.value_scores = []

    async def connect(self):
        """Establish database connection."""
        try:
            self.db = await asyncpg.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                database=POSTGRES_DB,
                password=POSTGRES_PASSWORD,
            )
            logger.info("Connected to PostgreSQL")
            await self._ensure_schema()
        except Exception as exc:
            logger.error(f"Database connection failed: {exc}")
            raise

    async def _ensure_schema(self):
        """Create local_llm_operations table if needed."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS local_llm_operations (
                id SERIAL PRIMARY KEY,
                operation_id UUID UNIQUE NOT NULL,
                operation_type VARCHAR(50) NOT NULL,  -- chat, embed, reasoning, analysis
                purpose VARCHAR(100),  -- autonomous_trigger, pattern_extraction, summarization
                input_tokens INT,
                output_tokens INT,
                latency_ms INT,
                quality_score FLOAT,  -- 0-1 based on validation
                value_score FLOAT,  -- 0-1 based on downstream impact
                contribution_type VARCHAR(50),  -- hypothesis, pattern, summary, decision
                metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                session_type VARCHAR(20) DEFAULT 'autonomous'  -- autonomous, remote, hybrid
            );

            CREATE INDEX IF NOT EXISTS idx_local_llm_ops_created ON local_llm_operations(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_local_llm_ops_type ON local_llm_operations(operation_type);
            CREATE INDEX IF NOT EXISTS idx_local_llm_ops_purpose ON local_llm_operations(purpose);
        """)

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS local_llm_contributions (
                id SERIAL PRIMARY KEY,
                contribution_id UUID UNIQUE NOT NULL,
                operation_id UUID REFERENCES local_llm_operations(operation_id),
                contribution_type VARCHAR(50) NOT NULL,  -- data, feature, improvement, test
                description TEXT,
                impact_score FLOAT,  -- 0-1 measured impact
                status VARCHAR(20) DEFAULT 'active',  -- active, applied, rejected, expired
                applied_at TIMESTAMPTZ,
                metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_local_llm_contrib_created ON local_llm_contributions(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_local_llm_contrib_status ON local_llm_contributions(status);
        """)

        logger.info("Schema ensured")

    async def track_operation(
        self,
        operation_type: str,
        purpose: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        quality_score: float = 0.0,
        value_score: float = 0.0,
        contribution_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session_type: str = "autonomous",
    ) -> str:
        """Track a local LLM operation."""
        operation_id = str(uuid4())

        await self.db.execute(
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

        # Append to metrics file for monitoring
        metric = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "purpose": purpose,
            "tokens": input_tokens + output_tokens,
            "latency_ms": latency_ms,
            "quality_score": quality_score,
            "value_score": value_score,
            "timestamp": datetime.now().isoformat(),
        }
        with open(METRICS_FILE, "a") as f:
            f.write(json.dumps(metric) + "\n")

        self.operation_counts[operation_type] += 1
        if value_score > 0:
            self.value_scores.append(value_score)

        logger.info(
            f"Tracked operation: {operation_type} purpose={purpose} "
            f"tokens={input_tokens + output_tokens} value={value_score:.2f}"
        )

        return operation_id

    async def record_contribution(
        self,
        operation_id: str,
        contribution_type: str,
        description: str,
        impact_score: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a contribution made by local LLM."""
        contribution_id = str(uuid4())

        await self.db.execute(
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

        logger.info(
            f"Recorded contribution: {contribution_type} impact={impact_score:.2f} desc={description[:50]}"
        )

        return contribution_id

    async def mark_contribution_applied(self, contribution_id: str):
        """Mark a contribution as applied to the system."""
        await self.db.execute(
            """
            UPDATE local_llm_contributions
            SET status = 'applied', applied_at = NOW()
            WHERE contribution_id = $1
            """,
            contribution_id,
        )
        logger.info(f"Marked contribution {contribution_id} as applied")

    async def get_metrics(self, since_hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive metrics for local LLM operations."""
        since_time = datetime.now() - timedelta(hours=since_hours)

        # Operation stats
        op_stats = await self.db.fetch(
            """
            SELECT
                operation_type,
                COUNT(*) as count,
                AVG(input_tokens + output_tokens) as avg_tokens,
                AVG(latency_ms) as avg_latency_ms,
                AVG(quality_score) as avg_quality,
                AVG(value_score) as avg_value,
                SUM(CASE WHEN session_type = 'autonomous' THEN 1 ELSE 0 END) as autonomous_count,
                SUM(CASE WHEN session_type = 'remote' THEN 1 ELSE 0 END) as remote_count
            FROM local_llm_operations
            WHERE created_at >= $1
            GROUP BY operation_type
            """,
            since_time,
        )

        # Purpose breakdown
        purpose_stats = await self.db.fetch(
            """
            SELECT
                purpose,
                COUNT(*) as count,
                AVG(value_score) as avg_value
            FROM local_llm_operations
            WHERE created_at >= $1 AND purpose IS NOT NULL
            GROUP BY purpose
            ORDER BY count DESC
            LIMIT 10
            """,
            since_time,
        )

        # Contribution stats
        contrib_stats = await self.db.fetch(
            """
            SELECT
                contribution_type,
                COUNT(*) as count,
                AVG(impact_score) as avg_impact,
                SUM(CASE WHEN status = 'applied' THEN 1 ELSE 0 END) as applied_count
            FROM local_llm_contributions
            WHERE created_at >= $1
            GROUP BY contribution_type
            """,
            since_time,
        )

        # Value trends (hourly)
        value_trends = await self.db.fetch(
            """
            SELECT
                DATE_TRUNC('hour', created_at) as hour,
                COUNT(*) as operations,
                AVG(value_score) as avg_value,
                SUM(input_tokens + output_tokens) as total_tokens
            FROM local_llm_operations
            WHERE created_at >= $1 AND value_score > 0
            GROUP BY hour
            ORDER BY hour DESC
            LIMIT 24
            """,
            since_time,
        )

        # Health check local LLM endpoints
        chat_health = await self._check_endpoint_health(f"{LLAMA_CHAT_URL}/health")
        embed_health = await self._check_endpoint_health(f"{LLAMA_EMBED_URL}/health")

        return {
            "period_hours": since_hours,
            "operations": [dict(row) for row in op_stats],
            "purposes": [dict(row) for row in purpose_stats],
            "contributions": [dict(row) for row in contrib_stats],
            "value_trends": [dict(row) for row in value_trends],
            "health": {
                "chat_model": chat_health,
                "embedding_model": embed_health,
            },
            "generated_at": datetime.now().isoformat(),
        }

    async def _check_endpoint_health(self, url: str) -> Dict[str, Any]:
        """Check health of local LLM endpoint."""
        try:
            start = datetime.now()
            resp = await self.http_client.get(url)
            latency = (datetime.now() - start).total_seconds() * 1000
            return {
                "status": "healthy" if resp.status_code == 200 else "unhealthy",
                "latency_ms": round(latency, 2),
                "response": resp.json() if resp.status_code == 200 else None,
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def get_value_report(self, since_hours: int = 24) -> Dict[str, Any]:
        """Generate value contribution report."""
        since_time = datetime.now() - timedelta(hours=since_hours)

        # High-value operations
        high_value_ops = await self.db.fetch(
            """
            SELECT
                operation_type,
                purpose,
                contribution_type,
                value_score,
                (input_tokens + output_tokens) as tokens,
                metadata->>'result_summary' as result_summary,
                created_at
            FROM local_llm_operations
            WHERE created_at >= $1 AND value_score >= 0.7
            ORDER BY value_score DESC, created_at DESC
            LIMIT 20
            """,
            since_time,
        )

        # Applied contributions
        applied_contribs = await self.db.fetch(
            """
            SELECT
                c.contribution_type,
                c.description,
                c.impact_score,
                c.applied_at,
                o.operation_type,
                o.purpose
            FROM local_llm_contributions c
            JOIN local_llm_operations o ON c.operation_id = o.operation_id
            WHERE c.created_at >= $1 AND c.status = 'applied'
            ORDER BY c.applied_at DESC
            LIMIT 20
            """,
            since_time,
        )

        # Inter-session continuity (autonomous operations)
        autonomous_ops = await self.db.fetchval(
            """
            SELECT COUNT(*)
            FROM local_llm_operations
            WHERE created_at >= $1 AND session_type = 'autonomous'
            """,
            since_time,
        )

        total_ops = await self.db.fetchval(
            "SELECT COUNT(*) FROM local_llm_operations WHERE created_at >= $1",
            since_time,
        )

        # Calculate overall value score
        avg_value = await self.db.fetchval(
            """
            SELECT AVG(value_score)
            FROM local_llm_operations
            WHERE created_at >= $1 AND value_score > 0
            """,
            since_time,
        )

        # Integration with autonomous improvement
        improvement_integration = await self._check_improvement_integration(since_time)

        return {
            "period_hours": since_hours,
            "summary": {
                "total_operations": total_ops or 0,
                "autonomous_operations": autonomous_ops or 0,
                "autonomy_ratio": (
                    round(autonomous_ops / total_ops, 2) if total_ops else 0
                ),
                "average_value_score": round(avg_value or 0, 3),
                "high_value_operations": len(high_value_ops),
                "applied_contributions": len(applied_contribs),
            },
            "high_value_operations": [dict(row) for row in high_value_ops],
            "applied_contributions": [dict(row) for row in applied_contribs],
            "autonomous_improvement_integration": improvement_integration,
            "generated_at": datetime.now().isoformat(),
        }

    async def _check_improvement_integration(
        self, since_time: datetime
    ) -> Dict[str, Any]:
        """Check integration with autonomous improvement system."""
        try:
            # Check if autonomous improvement cycles used local LLM
            cycles = await self.db.fetch(
                """
                SELECT
                    cycle_id,
                    trigger_reason,
                    status,
                    created_at
                FROM improvement_cycles
                WHERE created_at >= $1
                ORDER BY created_at DESC
                LIMIT 10
                """,
                since_time,
            )

            # Check trigger events from local LLM analysis
            triggers = await self.db.fetch(
                """
                SELECT
                    trigger_id,
                    trigger_source,
                    should_trigger,
                    reasoning,
                    created_at
                FROM trigger_events
                WHERE created_at >= $1
                ORDER BY created_at DESC
                LIMIT 10
                """,
                since_time,
            )

            # Check hypotheses generated by local LLM
            hypotheses = await self.db.fetch(
                """
                SELECT
                    hypothesis_id,
                    hypothesis_type,
                    description,
                    priority,
                    created_at
                FROM optimization_hypotheses
                WHERE created_at >= $1
                ORDER BY priority DESC, created_at DESC
                LIMIT 10
                """,
                since_time,
            )

            return {
                "improvement_cycles": len(cycles),
                "trigger_events": len(triggers),
                "hypotheses_generated": len(hypotheses),
                "recent_cycles": [dict(row) for row in cycles],
                "recent_triggers": [dict(row) for row in triggers],
                "recent_hypotheses": [dict(row) for row in hypotheses],
            }
        except Exception as exc:
            logger.warning(f"Could not check improvement integration: {exc}")
            return {"error": str(exc), "available": False}

    async def cleanup_old_metrics(self, days: int = 30):
        """Clean up old operation records."""
        cutoff = datetime.now() - timedelta(days=days)
        deleted_ops = await self.db.fetchval(
            "DELETE FROM local_llm_operations WHERE created_at < $1 RETURNING COUNT(*)",
            cutoff,
        )
        deleted_contribs = await self.db.fetchval(
            "DELETE FROM local_llm_contributions WHERE created_at < $1 RETURNING COUNT(*)",
            cutoff,
        )
        logger.info(
            f"Cleaned up {deleted_ops} operations and {deleted_contribs} contributions older than {days} days"
        )

    async def close(self):
        """Close connections."""
        if self.db:
            await self.db.close()
        await self.http_client.aclose()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Local LLM Monitor")
    parser.add_argument("--daemon", action="store_true", help="Run as monitoring daemon")
    parser.add_argument(
        "--metrics", action="store_true", help="Print current metrics"
    )
    parser.add_argument(
        "--value-report", action="store_true", help="Print value contribution report"
    )
    parser.add_argument(
        "--hours", type=int, default=24, help="Time window in hours (default: 24)"
    )
    parser.add_argument(
        "--cleanup", type=int, help="Clean up records older than N days"
    )

    args = parser.parse_args()

    monitor = LocalLLMMonitor()
    await monitor.connect()

    try:
        if args.cleanup:
            await monitor.cleanup_old_metrics(days=args.cleanup)
        elif args.metrics:
            metrics = await monitor.get_metrics(since_hours=args.hours)
            print(json.dumps(metrics, indent=2, default=str))
        elif args.value_report:
            report = await monitor.get_value_report(since_hours=args.hours)
            print(json.dumps(report, indent=2, default=str))
        elif args.daemon:
            logger.info("Starting monitoring daemon...")
            # In daemon mode, we'd set up periodic metric collection
            # For now, just run once
            while True:
                metrics = await monitor.get_metrics(since_hours=1)
                logger.info(f"Collected metrics: {len(metrics['operations'])} operation types")
                await asyncio.sleep(300)  # Every 5 minutes
        else:
            parser.print_help()
    finally:
        await monitor.close()


if __name__ == "__main__":
    asyncio.run(main())
