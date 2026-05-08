#!/usr/bin/env python3
"""
Agent Learning Aggregator

Collects patterns from all agent types and aggregates them for cross-agent learning.
Part of Phase 2: Cross-Agent Knowledge Federation.

Features:
- Collects patterns from routing_log, interaction_history, and agent-specific logs
- Tags patterns by agent type and task domain
- Computes cross-agent effectiveness metrics
- Identifies successful patterns worth sharing

Usage:
    from agent_learning_aggregator import AgentLearningAggregator

    aggregator = AgentLearningAggregator()
    await aggregator.connect()

    # Aggregate patterns from last 24 hours
    patterns = await aggregator.aggregate_patterns(since_hours=24)

    # Update capability matrix
    await aggregator.update_capability_matrix()
"""

import asyncio
import asyncpg
import hashlib
import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_learning_aggregator")

# Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ai_context")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# Agent type detection patterns
AGENT_PATTERNS = {
    "claude": [r"claude", r"sonnet", r"opus", r"anthropic"],
    "qwen": [r"qwen", r"qwen2", r"qwen3"],
    "codex": [r"codex", r"openai-codex"],
    "gemini": [r"gemini", r"gemini-pro", r"google"],
    "aider": [r"aider", r"aider-chat"],
    "continue": [r"continue", r"continue-dev"],
    "gpt": [r"gpt-4", r"gpt-3", r"openai"],
}

# Task domain detection patterns
DOMAIN_PATTERNS = {
    "nixos": [r"nixos", r"nix", r"flake", r"derivation", r"nixpkgs"],
    "python": [r"python", r"\.py", r"pip", r"poetry", r"pytest"],
    "javascript": [r"javascript", r"\.js", r"\.ts", r"npm", r"node"],
    "debugging": [r"debug", r"error", r"exception", r"traceback", r"stacktrace"],
    "refactoring": [r"refactor", r"cleanup", r"improve", r"optimize"],
    "testing": [r"test", r"spec", r"assertion", r"coverage"],
    "configuration": [r"config", r"settings", r"yaml", r"json", r"toml"],
    "documentation": [r"docs", r"documentation", r"readme", r"comment"],
    "security": [r"security", r"vulnerability", r"cve", r"exploit", r"auth"],
    "performance": [r"performance", r"latency", r"optimize", r"cache", r"benchmark"],
}


class AgentLearningAggregator:
    """
    Aggregates learning data from all agents to enable cross-agent knowledge sharing.
    """

    def __init__(
        self,
        pg_host: str = POSTGRES_HOST,
        pg_port: int = POSTGRES_PORT,
        pg_user: str = POSTGRES_USER,
        pg_database: str = POSTGRES_DB,
        pg_password: str = POSTGRES_PASSWORD,
    ):
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_database = pg_database
        self.pg_password = pg_password

        self.conn: Optional[asyncpg.Connection] = None
        self.pattern_cache: Dict[str, Any] = {}

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

    def detect_agent_type(self, text: str) -> Optional[str]:
        """Detect agent type from text content."""
        text_lower = text.lower()
        for agent_type, patterns in AGENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return agent_type
        return None

    def detect_task_domain(self, text: str) -> Optional[str]:
        """Detect task domain from text content."""
        text_lower = text.lower()
        scores = defaultdict(int)

        for domain, patterns in DOMAIN_PATTERNS.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                scores[domain] += matches

        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return "general"

    def extract_pattern_content(
        self, query: str, response: str, outcome: str
    ) -> Dict[str, Any]:
        """Extract pattern content from successful interaction."""
        return {
            "query_pattern": query[:500],  # First 500 chars
            "solution_approach": response[:1000],  # First 1000 chars
            "outcome": outcome,
            "keywords": self._extract_keywords(query + " " + response),
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text."""
        # Simple keyword extraction - remove common words, keep significant ones
        words = re.findall(r'\b[a-z]{4,}\b', text.lower())
        common_words = {
            "that", "this", "with", "from", "have", "will", "would", "could",
            "should", "make", "just", "like", "about", "into", "through"
        }
        keywords = [w for w in words if w not in common_words]
        # Return top 10 most frequent
        from collections import Counter
        return [k for k, v in Counter(keywords).most_common(10)]

    async def aggregate_patterns(
        self, since_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Aggregate patterns from all data sources.

        Returns list of discovered patterns with metadata.
        """
        since_time = datetime.now() - timedelta(hours=since_hours)
        patterns = []

        # 1. Aggregate from routing_log (if table exists)
        try:
            routing_patterns = await self._aggregate_from_routing_log(since_time)
            patterns.extend(routing_patterns)
            logger.info(f"Aggregated {len(routing_patterns)} patterns from routing_log")
        except Exception as exc:
            logger.warning(f"Could not aggregate from routing_log: {exc}")

        # 2. Aggregate from interaction_history (Qdrant-backed, via coordinator)
        # This would require querying the hybrid coordinator's interaction tracking
        # For now, we'll focus on routing_log as the primary source

        # 3. Store patterns in database
        stored_count = 0
        for pattern in patterns:
            try:
                pattern_id = await self._store_pattern(pattern)
                if pattern_id:
                    stored_count += 1
            except Exception as exc:
                logger.warning(f"Failed to store pattern: {exc}")

        logger.info(f"Stored {stored_count}/{len(patterns)} patterns in database")
        return patterns

    async def _aggregate_from_routing_log(
        self, since_time: datetime
    ) -> List[Dict[str, Any]]:
        """Aggregate successful patterns from routing_log."""
        try:
            rows = await self.conn.fetch(
                """
                SELECT
                    query,
                    model_used,
                    agent_type,
                    status,
                    tokens_used,
                    latency_ms,
                    timestamp
                FROM routing_log
                WHERE timestamp >= $1
                  AND status = 'success'
                  AND query IS NOT NULL
                  AND LENGTH(query) > 10
                ORDER BY timestamp DESC
                LIMIT 1000
                """,
                since_time,
            )

            patterns = []
            for row in rows:
                # Detect agent type if not provided
                agent_type = row["agent_type"] or self.detect_agent_type(
                    row["model_used"] or ""
                )
                if not agent_type:
                    continue

                # Detect task domain
                task_domain = self.detect_task_domain(row["query"])

                # Create pattern
                pattern = {
                    "agent_type": agent_type,
                    "task_domain": task_domain,
                    "pattern_type": "routing_success",
                    "pattern_content": {
                        "query_pattern": row["query"][:500],
                        "model_used": row["model_used"],
                        "success_indicators": ["status_success"],
                    },
                    "success_rate": 1.0,  # This entry succeeded
                    "avg_completion_time_ms": row["latency_ms"],
                    "avg_token_efficiency": row["tokens_used"],
                    "metadata": {
                        "source": "routing_log",
                        "timestamp": row["timestamp"].isoformat(),
                    },
                }

                patterns.append(pattern)

            return patterns

        except Exception as exc:
            logger.error(f"Error aggregating from routing_log: {exc}")
            return []

    async def _store_pattern(self, pattern: Dict[str, Any]) -> Optional[str]:
        """Store pattern in agent_patterns table."""
        try:
            # Check if pattern already exists
            existing = await self.conn.fetchrow(
                """
                SELECT id FROM agent_patterns
                WHERE agent_type = $1
                  AND task_domain = $2
                  AND pattern_hash = encode(sha256(convert_to($3, 'UTF8')), 'hex')
                """,
                pattern["agent_type"],
                pattern["task_domain"],
                json.dumps(pattern["pattern_content"]),
            )

            if existing:
                # Update existing pattern
                await self.conn.execute(
                    """
                    UPDATE agent_patterns
                    SET
                        total_attempts = total_attempts + 1,
                        usage_count = usage_count + 1,
                        last_used = NOW(),
                        last_updated = NOW()
                    WHERE id = $1
                    """,
                    existing["id"],
                )
                return str(existing["id"])
            else:
                # Insert new pattern
                pattern_id = str(uuid4())
                await self.conn.execute(
                    """
                    INSERT INTO agent_patterns (
                        id, agent_type, task_domain, pattern_type, pattern_content,
                        success_rate, usage_count, total_attempts,
                        avg_completion_time_ms, avg_token_efficiency,
                        tags, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    pattern_id,
                    pattern["agent_type"],
                    pattern["task_domain"],
                    pattern.get("pattern_type", "general"),
                    json.dumps(pattern["pattern_content"]),
                    pattern.get("success_rate", 1.0),
                    1,  # usage_count
                    1,  # total_attempts
                    pattern.get("avg_completion_time_ms", 0),
                    pattern.get("avg_token_efficiency", 0),
                    pattern.get("tags", []),
                    json.dumps(pattern.get("metadata", {})),
                )
                return pattern_id

        except Exception as exc:
            logger.error(f"Error storing pattern: {exc}")
            return None

    async def update_capability_matrix(self) -> Dict[str, int]:
        """
        Update agent capability matrix based on aggregated patterns.

        Returns statistics about updates performed.
        """
        stats = {"agents_updated": 0, "domains_updated": 0, "errors": 0}

        try:
            # Get aggregated statistics per agent/domain
            rows = await self.conn.fetch(
                """
                SELECT
                    agent_type,
                    task_domain,
                    COUNT(*) as pattern_count,
                    AVG(success_rate) as avg_success_rate,
                    AVG(avg_completion_time_ms) as avg_time,
                    AVG(avg_token_efficiency) as avg_tokens
                FROM agent_patterns
                WHERE last_updated >= NOW() - INTERVAL '7 days'
                GROUP BY agent_type, task_domain
                HAVING COUNT(*) >= 3  -- Need at least 3 patterns for statistical significance
                """
            )

            for row in rows:
                try:
                    # Calculate capability score
                    capability_score = await self.conn.fetchval(
                        """
                        SELECT calculate_capability_score($1, $2, $3, $4)
                        """,
                        row["avg_success_rate"],
                        0.75,  # Default quality score
                        int(row["avg_time"]) if row["avg_time"] else 5000,
                        int(row["avg_tokens"]) if row["avg_tokens"] else 500,
                    )

                    # Upsert capability matrix entry
                    await self.conn.execute(
                        """
                        INSERT INTO agent_capability_matrix (
                            agent_type, task_domain, capability_score,
                            total_attempts, successful_attempts,
                            avg_completion_time_ms, avg_quality_score,
                            avg_token_usage, sample_size, confidence_level
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (agent_type, task_domain)
                        DO UPDATE SET
                            capability_score = $3,
                            total_attempts = agent_capability_matrix.total_attempts + $4,
                            successful_attempts = agent_capability_matrix.successful_attempts + $5,
                            avg_completion_time_ms = $6,
                            avg_quality_score = $7,
                            avg_token_usage = $8,
                            sample_size = $9,
                            confidence_level = $10,
                            last_updated = NOW()
                        """,
                        row["agent_type"],
                        row["task_domain"],
                        capability_score,
                        row["pattern_count"],
                        int(row["pattern_count"] * row["avg_success_rate"]),
                        int(row["avg_time"]) if row["avg_time"] else 5000,
                        0.75,  # Default quality
                        int(row["avg_tokens"]) if row["avg_tokens"] else 500,
                        row["pattern_count"],
                        min(row["pattern_count"] / 10.0, 1.0),  # Confidence
                    )

                    stats["agents_updated"] += 1
                    stats["domains_updated"] += 1

                except Exception as exc:
                    logger.warning(
                        f"Failed to update capability for {row['agent_type']}/{row['task_domain']}: {exc}"
                    )
                    stats["errors"] += 1

            logger.info(
                f"Updated capability matrix: {stats['agents_updated']} agents, "
                f"{stats['domains_updated']} domains, {stats['errors']} errors"
            )

        except Exception as exc:
            logger.error(f"Error updating capability matrix: {exc}")
            stats["errors"] += 1

        return stats

    async def get_top_patterns(
        self, agent_type: Optional[str] = None, task_domain: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top patterns by success rate and usage."""
        query = """
            SELECT
                id, agent_type, task_domain, pattern_type,
                pattern_content, success_rate, usage_count,
                avg_completion_time_ms, avg_token_efficiency,
                tags, metadata
            FROM agent_patterns
            WHERE 1=1
        """
        params = []

        if agent_type:
            params.append(agent_type)
            query += f" AND agent_type = ${len(params)}"

        if task_domain:
            params.append(task_domain)
            query += f" AND task_domain = ${len(params)}"

        params.append(limit)
        query += f"""
            ORDER BY success_rate DESC, usage_count DESC
            LIMIT ${len(params)}
        """

        rows = await self.conn.fetch(query, *params)
        return [dict(row) for row in rows]

    async def get_capability_matrix(self) -> List[Dict[str, Any]]:
        """Get full agent capability matrix."""
        rows = await self.conn.fetch(
            """
            SELECT * FROM agent_capability_rankings
            ORDER BY task_domain, rank
            """
        )
        return [dict(row) for row in rows]


async def main():
    """Main entry point for testing."""
    aggregator = AgentLearningAggregator()
    await aggregator.connect()

    try:
        # Aggregate patterns from last 24 hours
        print("Aggregating patterns...")
        patterns = await aggregator.aggregate_patterns(since_hours=24)
        print(f"Found {len(patterns)} patterns")

        # Update capability matrix
        print("\nUpdating capability matrix...")
        stats = await aggregator.update_capability_matrix()
        print(f"Stats: {stats}")

        # Get top patterns
        print("\nTop patterns:")
        top = await aggregator.get_top_patterns(limit=5)
        for p in top:
            print(f"  {p['agent_type']}/{p['task_domain']}: "
                  f"{p['success_rate']:.2f} success, {p['usage_count']} uses")

        # Get capability matrix
        print("\nCapability matrix:")
        matrix = await aggregator.get_capability_matrix()
        for entry in matrix[:10]:
            print(f"  #{entry['rank']} {entry['agent_type']} @ {entry['task_domain']}: "
                  f"{entry['capability_score']:.3f}")

    finally:
        await aggregator.close()


if __name__ == "__main__":
    asyncio.run(main())
