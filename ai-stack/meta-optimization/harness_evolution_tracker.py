#!/usr/bin/env python3
"""
Harness Evolution Tracker

Tracks changes to harness configuration/code and measures their impact.
Enables rollback if meta-optimization degrades performance.

Part of Phase 3: Meta-Optimization
"""

import asyncio
import asyncpg
import json
import logging
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("harness_evolution_tracker")

# Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ai_context")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

REPO_ROOT = Path(os.getenv("REPO_ROOT", "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy"))


class HarnessEvolutionTracker:
    """
    Tracks harness changes and measures their impact over time.
    """

    def __init__(
        self,
        pg_host: str = POSTGRES_HOST,
        pg_port: int = POSTGRES_PORT,
        pg_user: str = POSTGRES_USER,
        pg_database: str = POSTGRES_DB,
        pg_password: str = POSTGRES_PASSWORD,
        repo_root: Path = REPO_ROOT,
    ):
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_database = pg_database
        self.pg_password = pg_password
        self.repo_root = repo_root

        self.conn: Optional[asyncpg.Connection] = None

    async def connect(self):
        """Establish database connection."""
        try:
            self.conn = await asyncpg.connect(
                host=self.pg_host,
                port=self.pg_port,
                user=self.pg_user,
                database=self.pg_database,
                password=self.pg_password,
            )
            logger.info("Connected to PostgreSQL")
        except Exception as exc:
            logger.error(f"Database connection failed: {exc}")
            raise

    async def close(self):
        """Close database connection."""
        if self.conn and not self.conn.is_closed():
            await self.conn.close()

    def get_current_commit(self) -> Optional[str]:
        """Get current Git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to get current commit: {exc}")
            return None

    async def capture_baseline(
        self,
        metric_name: str,
        component: Optional[str] = None,
        window_hours: int = 24,
    ) -> Optional[str]:
        """
        Capture performance baseline before applying changes.

        Returns baseline_id if successful.
        """
        try:
            # Get current metric value
            metric_value = await self._measure_metric(metric_name, window_hours)

            if metric_value is None:
                logger.warning(f"Could not measure {metric_name}")
                return None

            # Store baseline
            baseline_id = await self.conn.fetchval(
                "SELECT record_performance_baseline($1, $2, $3, $4)",
                metric_name,
                metric_value,
                window_hours,
                component,
            )

            logger.info(
                f"Captured baseline: {metric_name}={metric_value:.4f} "
                f"(window={window_hours}h, component={component})"
            )

            return str(baseline_id)

        except Exception as exc:
            logger.error(f"Error capturing baseline: {exc}")
            return None

    async def _measure_metric(
        self, metric_name: str, window_hours: int
    ) -> Optional[float]:
        """
        Measure a specific performance metric.

        Metrics:
        - routing_accuracy: % of routes that completed successfully
        - avg_route_latency_ms: Average routing latency
        - hint_success_rate: % of hints leading to successful outcomes
        - lesson_retrieval_relevance: Average relevance score of retrieved lessons
        """
        since = datetime.now() - timedelta(hours=window_hours)

        try:
            if metric_name == "routing_accuracy":
                result = await self.conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successes
                    FROM routing_log
                    WHERE timestamp >= $1
                    """,
                    since
                )
                if result and result["total"] > 0:
                    return (result["successes"] / result["total"]) * 100.0
                return None

            elif metric_name == "avg_route_latency_ms":
                result = await self.conn.fetchval(
                    """
                    SELECT AVG(latency_ms)
                    FROM routing_log
                    WHERE timestamp >= $1
                      AND status = 'success'
                    """,
                    since
                )
                return float(result) if result else None

            elif metric_name == "hint_success_rate":
                result = await self.conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN outcome_success THEN 1 ELSE 0 END) as successes
                    FROM interaction_history
                    WHERE timestamp >= $1
                      AND metadata->>'hint_template' IS NOT NULL
                    """,
                    since
                )
                if result and result["total"] > 0:
                    return (result["successes"] / result["total"]) * 100.0
                return None

            elif metric_name == "lesson_retrieval_relevance":
                # This would query pattern retrieval scores
                # For now, return None as this requires additional instrumentation
                return None

            else:
                logger.warning(f"Unknown metric: {metric_name}")
                return None

        except Exception as exc:
            logger.error(f"Error measuring {metric_name}: {exc}")
            return None

    async def apply_change(
        self,
        proposal_id: str,
        change_type: str,
        component_affected: str,
        change_description: str,
        change_details: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Apply an improvement change and record in evolution history.

        Returns history_id if successful.
        """
        try:
            # Get current commit for rollback reference
            rollback_commit = self.get_current_commit()

            # Apply the change using database function
            history_id = await self.conn.fetchval(
                "SELECT apply_improvement_proposal($1, $2, $3, $4, $5, $6)",
                proposal_id,
                change_type,
                component_affected,
                change_description,
                json.dumps(change_details or {}),
                rollback_commit,
            )

            logger.info(
                f"Applied change: {change_type} to {component_affected} "
                f"(proposal={proposal_id}, history={history_id})"
            )

            return str(history_id)

        except Exception as exc:
            logger.error(f"Error applying change: {exc}")
            return None

    async def validate_impact(
        self,
        history_id: str,
        validation_window_hours: int = 24,
    ) -> Tuple[bool, float]:
        """
        Validate impact of applied change after deployment.

        Returns: (improvement_detected, actual_improvement_pct)
        """
        try:
            # Get the change details
            change = await self.conn.fetchrow(
                """
                SELECT
                    h.component_affected,
                    h.applied_at,
                    p.target,
                    p.estimated_improvement_pct
                FROM harness_evolution_history h
                JOIN harness_improvement_proposals p ON h.proposal_id = p.id
                WHERE h.id = $1
                """,
                history_id
            )

            if not change:
                logger.error(f"History record not found: {history_id}")
                return False, 0.0

            # Determine which metrics to validate based on target
            metrics_to_check = self._get_validation_metrics(change["target"])

            # Measure current performance
            impact_metrics = {}
            total_improvement = 0.0
            measurements_count = 0

            for metric_name in metrics_to_check:
                # Get baseline
                baseline = await self._get_baseline_for_component(
                    metric_name,
                    change["component_affected"]
                )

                if baseline is None:
                    logger.warning(f"No baseline for {metric_name}, skipping")
                    continue

                # Measure current value
                current_value = await self._measure_metric(
                    metric_name, validation_window_hours
                )

                if current_value is None:
                    logger.warning(f"Could not measure {metric_name}, skipping")
                    continue

                # Calculate improvement
                improvement_pct = ((current_value - baseline) / baseline) * 100.0

                impact_metrics[metric_name] = {
                    "baseline": baseline,
                    "current": current_value,
                    "improvement_pct": improvement_pct,
                }

                total_improvement += improvement_pct
                measurements_count += 1

            if measurements_count == 0:
                logger.warning("No metrics available for validation")
                return False, 0.0

            # Calculate average improvement
            avg_improvement = total_improvement / measurements_count

            # Store validation results
            await self.conn.execute(
                "SELECT validate_improvement_impact($1, $2, $3)",
                history_id,
                avg_improvement,
                json.dumps(impact_metrics),
            )

            logger.info(
                f"Validated impact: {avg_improvement:+.2f}% improvement "
                f"(expected: {change['estimated_improvement_pct']:.2f}%)"
            )

            # Consider it improved if >3% better
            improvement_detected = avg_improvement > 3.0

            return improvement_detected, avg_improvement

        except Exception as exc:
            logger.error(f"Error validating impact: {exc}")
            return False, 0.0

    async def rollback_change(
        self,
        history_id: str,
        reason: str,
    ) -> bool:
        """
        Rollback a change that degraded performance.

        Returns True if rollback successful.
        """
        try:
            # Get rollback commit
            change = await self.conn.fetchrow(
                """
                SELECT rollback_commit, component_affected, change_description
                FROM harness_evolution_history
                WHERE id = $1
                """,
                history_id
            )

            if not change:
                logger.error(f"History record not found: {history_id}")
                return False

            rollback_commit = change["rollback_commit"]

            if not rollback_commit:
                logger.error("No rollback commit recorded")
                return False

            logger.info(
                f"Rolling back {change['component_affected']} to {rollback_commit}: {reason}"
            )

            # Record rollback in database
            await self.conn.execute(
                "SELECT rollback_improvement($1, $2)",
                history_id,
                reason,
            )

            # Note: Actual git revert should be done manually or via automation
            # We don't auto-revert code here to prevent unintended consequences

            logger.warning(
                f"⚠️  Rollback recorded. Manual action required: "
                f"git revert {rollback_commit} or git checkout {rollback_commit} -- {change['component_affected']}"
            )

            return True

        except Exception as exc:
            logger.error(f"Error recording rollback: {exc}")
            return False

    async def _get_baseline_for_component(
        self,
        metric_name: str,
        component: Optional[str],
    ) -> Optional[float]:
        """Get most recent baseline for metric/component."""
        try:
            result = await self.conn.fetchval(
                """
                SELECT metric_value
                FROM harness_performance_baselines
                WHERE metric_name = $1
                  AND (component = $2 OR ($2 IS NULL AND component IS NULL))
                ORDER BY measured_at DESC
                LIMIT 1
                """,
                metric_name,
                component,
            )
            return float(result) if result else None
        except Exception as exc:
            logger.error(f"Error getting baseline: {exc}")
            return None

    def _get_validation_metrics(self, target: str) -> List[str]:
        """Get list of metrics to validate for each optimization target."""
        metric_map = {
            "routing_rules": ["routing_accuracy", "avg_route_latency_ms"],
            "hint_templates": ["hint_success_rate"],
            "lesson_library": ["lesson_retrieval_relevance"],
            "tool_discovery": [],
            "agent_roles": ["routing_accuracy"],
        }
        return metric_map.get(target, [])

    async def get_evolution_summary(
        self, days: int = 30
    ) -> Dict[str, Any]:
        """
        Get summary of harness evolution over time period.
        """
        since = datetime.now() - timedelta(days=days)

        try:
            # Get evolution statistics
            summary = await self.conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_changes,
                    SUM(CASE WHEN validation_status = 'improved' THEN 1 ELSE 0 END) as improvements,
                    SUM(CASE WHEN validation_status = 'degraded' THEN 1 ELSE 0 END) as degradations,
                    SUM(CASE WHEN validation_status = 'neutral' THEN 1 ELSE 0 END) as neutral,
                    SUM(CASE WHEN rolled_back THEN 1 ELSE 0 END) as rollbacks,
                    AVG(actual_improvement_pct) as avg_actual_improvement
                FROM harness_evolution_history
                WHERE applied_at >= $1
                """,
                since
            )

            # Get changes by component
            by_component = await self.conn.fetch(
                """
                SELECT
                    component_affected,
                    COUNT(*) as changes,
                    AVG(actual_improvement_pct) as avg_improvement
                FROM harness_evolution_history
                WHERE applied_at >= $1
                GROUP BY component_affected
                ORDER BY changes DESC
                """,
                since
            )

            return {
                "period_days": days,
                "summary": dict(summary) if summary else {},
                "by_component": [dict(row) for row in by_component],
            }

        except Exception as exc:
            logger.error(f"Error getting evolution summary: {exc}")
            return {"error": str(exc)}


async def main():
    """Main entry point for testing."""
    tracker = HarnessEvolutionTracker()
    await tracker.connect()

    try:
        # Example: Capture baselines
        print("Capturing performance baselines...")
        await tracker.capture_baseline("routing_accuracy", component="route_handler", window_hours=24)
        await tracker.capture_baseline("avg_route_latency_ms", component="route_handler", window_hours=24)
        await tracker.capture_baseline("hint_success_rate", component="hints_engine", window_hours=24)

        # Get evolution summary
        print("\nHarness Evolution Summary (last 30 days):")
        summary = await tracker.get_evolution_summary(days=30)
        print(json.dumps(summary, indent=2, default=str))

    finally:
        await tracker.close()


if __name__ == "__main__":
    asyncio.run(main())
