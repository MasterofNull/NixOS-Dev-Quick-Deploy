"""
Federated Learning Integration for Hybrid Coordinator

Integrates cross-agent learning into the routing and query handling flow.
Enables capability-based routing and pattern-aware responses.

Features:
- Capability-based agent selection for tasks
- Pattern recommendation injection into responses
- Automatic pattern tracking from successful interactions
- Cross-agent learning feedback loop

Usage:
    from federated_integration import FederatedIntegration

    fed = FederatedIntegration()
    await fed.connect()

    # Get best agent for a task
    best_agent = await fed.get_best_agent_for_task("nixos configuration")

    # Track successful pattern
    await fed.track_success_pattern(agent="claude", domain="nixos", ...)

    # Get recommendations for improvement
    recs = await fed.get_recommendations_for_agent("claude", domain="nixos")
"""

import asyncio
import asyncpg
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("federated_integration")

# Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ai_context")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# Task domain detection patterns (reused from aggregator)
DOMAIN_PATTERNS = {
    "nixos": [r"nixos", r"nix", r"flake", r"derivation"],
    "python": [r"python", r"\.py", r"pip", r"pytest"],
    "javascript": [r"javascript", r"\.js", r"\.ts", r"npm"],
    "debugging": [r"debug", r"error", r"exception", r"traceback"],
    "refactoring": [r"refactor", r"cleanup", r"improve", r"optimize"],
    "testing": [r"test", r"spec", r"assertion"],
    "configuration": [r"config", r"settings", r"yaml", r"json"],
    "documentation": [r"docs", r"documentation", r"readme"],
    "security": [r"security", r"vulnerability", r"cve", r"auth"],
    "performance": [r"performance", r"latency", r"cache", r"benchmark"],
}


class FederatedIntegration:
    """
    Integration layer for federated learning in hybrid coordinator.
    """

    def __init__(
        self,
        pg_host: str = POSTGRES_HOST,
        pg_port: int = POSTGRES_PORT,
        pg_user: str = POSTGRES_USER,
        pg_database: str = POSTGRES_DB,
        pg_password: str = POSTGRES_PASSWORD,
        enable_capability_routing: bool = True,
        enable_pattern_injection: bool = True,
    ):
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_database = pg_database
        self.pg_password = pg_password

        self.enable_capability_routing = enable_capability_routing
        self.enable_pattern_injection = enable_pattern_injection

        self.conn: Optional[asyncpg.Connection] = None
        self._capability_cache: Dict[str, Dict[str, float]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes

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
            logger.info("Federated integration connected to PostgreSQL")
        except Exception as exc:
            logger.warning(f"Federated integration DB connection failed: {exc}")
            # Non-fatal - degrade gracefully
            self.conn = None

    async def close(self):
        """Close database connection."""
        if self.conn and not self.conn.is_closed():
            await self.conn.close()

    def detect_task_domain(self, query: str) -> str:
        """Detect task domain from query text."""
        query_lower = query.lower()
        scores = {}

        for domain, patterns in DOMAIN_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, query_lower))
                score += matches
            if score > 0:
                scores[domain] = score

        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return "general"

    async def get_best_agent_for_task(
        self, query: str, available_agents: Optional[List[str]] = None
    ) -> Tuple[Optional[str], float, str]:
        """
        Get the best agent for a task based on capability matrix.

        Returns: (agent_name, capability_score, reasoning)
        """
        if not self.enable_capability_routing or not self.conn:
            return None, 0.0, "Capability routing disabled or DB unavailable"

        # Detect task domain
        domain = self.detect_task_domain(query)

        # Get capabilities from cache or database
        capabilities = await self._get_capabilities_for_domain(domain)

        if not capabilities:
            return None, 0.0, f"No capability data for domain '{domain}'"

        # Filter to available agents if specified
        if available_agents:
            capabilities = {
                agent: score
                for agent, score in capabilities.items()
                if agent in available_agents
            }

        if not capabilities:
            return None, 0.0, f"No available agents have capability data for '{domain}'"

        # Select best agent
        best_agent = max(capabilities.items(), key=lambda x: x[1])
        agent_name, score = best_agent

        reasoning = (
            f"Selected {agent_name} for {domain} tasks "
            f"(capability score: {score:.2f}, domain: {domain})"
        )

        logger.info(reasoning)
        return agent_name, score, reasoning

    async def _get_capabilities_for_domain(
        self, domain: str
    ) -> Dict[str, float]:
        """Get agent capabilities for a specific domain."""
        # Check cache first
        if (
            self._cache_timestamp
            and (datetime.now() - self._cache_timestamp).total_seconds() < self._cache_ttl_seconds
            and domain in self._capability_cache
        ):
            return self._capability_cache[domain]

        # Query database
        try:
            rows = await self.conn.fetch(
                """
                SELECT agent_type, capability_score
                FROM agent_capability_matrix
                WHERE task_domain = $1
                  AND sample_size >= 3
                  AND confidence_level >= 0.3
                ORDER BY capability_score DESC
                """,
                domain,
            )

            capabilities = {row["agent_type"]: row["capability_score"] for row in rows}

            # Update cache
            if domain not in self._capability_cache:
                self._capability_cache[domain] = {}
            self._capability_cache[domain] = capabilities
            self._cache_timestamp = datetime.now()

            return capabilities

        except Exception as exc:
            logger.warning(f"Error fetching capabilities for {domain}: {exc}")
            return {}

    async def get_recommendations_for_agent(
        self, agent: str, domain: Optional[str] = None, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get pattern recommendations for an agent.

        Returns list of recommendations with pattern details.
        """
        if not self.enable_pattern_injection or not self.conn:
            return []

        try:
            query = """
                SELECT
                    r.source_agent,
                    r.confidence_score,
                    r.recommendation_reason,
                    p.pattern_content,
                    p.success_rate,
                    p.usage_count,
                    p.task_domain
                FROM cross_agent_recommendations r
                JOIN agent_patterns p ON r.pattern_id = p.id
                WHERE r.target_agent = $1
                  AND r.adopted = false
                  AND r.confidence_score >= 0.6
            """
            params = [agent]

            if domain:
                query += " AND p.task_domain = $2"
                params.append(domain)

            query += " ORDER BY r.confidence_score DESC LIMIT $" + str(len(params) + 1)
            params.append(limit)

            rows = await self.conn.fetch(query, *params)

            recommendations = []
            for row in rows:
                recommendations.append({
                    "source_agent": row["source_agent"],
                    "confidence": row["confidence_score"],
                    "reason": row["recommendation_reason"],
                    "pattern": row["pattern_content"],
                    "success_rate": row["success_rate"],
                    "usage_count": row["usage_count"],
                    "domain": row["task_domain"],
                })

            return recommendations

        except Exception as exc:
            logger.warning(f"Error fetching recommendations: {exc}")
            return []

    async def track_success_pattern(
        self,
        agent: str,
        query: str,
        response: str,
        success: bool,
        completion_time_ms: int,
        token_usage: int,
    ) -> bool:
        """
        Track a successful interaction as a pattern for future learning.

        Returns True if pattern was tracked, False otherwise.
        """
        if not self.conn:
            return False

        try:
            # Detect domain
            domain = self.detect_task_domain(query)

            # Create pattern content
            pattern_content = {
                "query_pattern": query[:500],
                "solution_approach": response[:1000],
                "success": success,
                "tokens_used": token_usage,
                "completion_time_ms": completion_time_ms,
            }

            # Store or update pattern
            await self.conn.execute(
                """
                INSERT INTO agent_patterns (
                    agent_type, task_domain, pattern_type, pattern_content,
                    success_rate, usage_count, total_attempts,
                    avg_completion_time_ms, avg_token_efficiency
                ) VALUES ($1, $2, $3, $4, $5, 1, 1, $6, $7)
                ON CONFLICT (agent_type, task_domain, pattern_hash)
                DO UPDATE SET
                    total_attempts = agent_patterns.total_attempts + 1,
                    usage_count = agent_patterns.usage_count + CASE WHEN $5 > 0.5 THEN 1 ELSE 0 END,
                    success_rate = (
                        (agent_patterns.success_rate * agent_patterns.total_attempts + $5) /
                        (agent_patterns.total_attempts + 1)
                    ),
                    avg_completion_time_ms = (
                        (agent_patterns.avg_completion_time_ms * agent_patterns.total_attempts + $6) /
                        (agent_patterns.total_attempts + 1)
                    ),
                    avg_token_efficiency = (
                        (agent_patterns.avg_token_efficiency * agent_patterns.usage_count + $7) /
                        (agent_patterns.usage_count + 1)
                    ),
                    last_used = NOW(),
                    last_updated = NOW()
                """,
                agent,
                domain,
                "interaction_success" if success else "interaction_failure",
                json.dumps(pattern_content),
                1.0 if success else 0.0,
                completion_time_ms,
                token_usage,
            )

            # Invalidate cache for this domain
            if domain in self._capability_cache:
                del self._capability_cache[domain]

            logger.debug(f"Tracked pattern: {agent}/{domain}, success={success}")
            return True

        except Exception as exc:
            logger.warning(f"Error tracking pattern: {exc}")
            return False

    async def get_cross_agent_insights(
        self, domain: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get cross-agent learning insights for a domain.

        Returns insights from federated synthesis sessions.
        """
        if not self.conn:
            return []

        try:
            rows = await self.conn.fetch(
                """
                SELECT
                    session_type,
                    patterns_analyzed,
                    insights,
                    started_at
                FROM federated_learning_sessions
                WHERE metadata->>'task_domain' = $1
                  AND status = 'completed'
                ORDER BY started_at DESC
                LIMIT $2
                """,
                domain,
                limit,
            )

            insights = []
            for row in rows:
                insight_data = json.loads(row["insights"]) if row["insights"] else []
                insights.extend(insight_data)

            return insights[:limit]

        except Exception as exc:
            logger.warning(f"Error fetching insights: {exc}")
            return []

    def format_recommendation_for_display(
        self, recommendation: Dict[str, Any]
    ) -> str:
        """Format a recommendation for injection into response."""
        return (
            f"\n\n💡 **Learning from {recommendation['source_agent']}**: "
            f"{recommendation['reason']} "
            f"(Success rate: {recommendation['success_rate']:.0%}, "
            f"Used {recommendation['usage_count']} times)"
        )

    async def get_statistics(self) -> Dict[str, Any]:
        """Get federated learning statistics."""
        if not self.conn:
            return {"enabled": False, "error": "Database not connected"}

        try:
            stats = {}

            # Pattern count by agent
            stats["patterns_by_agent"] = dict(
                await self.conn.fetch(
                    """
                    SELECT agent_type, COUNT(*) as count
                    FROM agent_patterns
                    GROUP BY agent_type
                    ORDER BY count DESC
                    """
                )
            )

            # Recommendation statistics
            rec_stats = await self.conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN adopted THEN 1 ELSE 0 END) as adopted,
                    SUM(CASE WHEN adoption_result = 'success' THEN 1 ELSE 0 END) as successful
                FROM cross_agent_recommendations
                """
            )
            stats["recommendations"] = dict(rec_stats) if rec_stats else {}

            # Capability matrix coverage
            stats["capability_coverage"] = dict(
                await self.conn.fetch(
                    """
                    SELECT
                        task_domain,
                        COUNT(DISTINCT agent_type) as agents_with_capability
                    FROM agent_capability_matrix
                    WHERE confidence_level >= 0.3
                    GROUP BY task_domain
                    ORDER BY agents_with_capability DESC
                    """
                )
            )

            return stats

        except Exception as exc:
            logger.error(f"Error getting statistics: {exc}")
            return {"enabled": True, "error": str(exc)}
