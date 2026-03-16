#!/usr/bin/env python3
"""
Federated Pattern Synthesis

Uses local LLM to synthesize patterns across agents and generate optimization insights.
Part of Phase 2: Cross-Agent Knowledge Federation.

Features:
- Analyzes patterns from multiple agents
- Identifies commonalities and differences in approaches
- Generates agent-specific optimizations
- Recommends patterns for cross-agent adoption

Usage:
    from federated_pattern_synthesis import FederatedPatternSynthesis

    synthesizer = FederatedPatternSynthesis()
    await synthesizer.connect()

    # Synthesize patterns for a specific domain
    insights = await synthesizer.synthesize_patterns(task_domain="nixos")

    # Generate recommendations for an agent
    recs = await synthesizer.generate_recommendations(target_agent="claude")
"""

import asyncio
import asyncpg
import httpx
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("federated_pattern_synthesis")

# Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ai_context")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

LLAMA_CHAT_URL = os.getenv("LLAMA_CHAT_URL", "http://127.0.0.1:8080")


class FederatedPatternSynthesis:
    """
    Synthesizes patterns across agents using local LLM to generate insights and recommendations.
    """

    def __init__(
        self,
        pg_host: str = POSTGRES_HOST,
        pg_port: int = POSTGRES_PORT,
        pg_user: str = POSTGRES_USER,
        pg_database: str = POSTGRES_DB,
        pg_password: str = POSTGRES_PASSWORD,
        llama_url: str = LLAMA_CHAT_URL,
    ):
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_database = pg_database
        self.pg_password = pg_password
        self.llama_url = llama_url

        self.conn: Optional[asyncpg.Connection] = None
        self.http_client = httpx.AsyncClient(timeout=120.0)

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
        """Close connections."""
        if self.conn and not self.conn.is_closed():
            await self.conn.close()
        await self.http_client.aclose()

    async def call_local_llm(
        self, prompt: str, max_tokens: int = 1000, temperature: float = 0.3
    ) -> str:
        """Call local LLM for pattern synthesis."""
        try:
            response = await self.http_client.post(
                f"{self.llama_url}/chat/completions",
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.error(f"LLM call failed: {exc}")
            return ""

    async def synthesize_patterns(
        self,
        task_domain: Optional[str] = None,
        agent_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesize patterns across agents for a specific domain.

        Returns insights and recommended optimizations.
        """
        # 1. Gather patterns from database
        patterns = await self._get_patterns_for_synthesis(task_domain, agent_types)

        if not patterns:
            logger.warning(f"No patterns found for domain={task_domain}, agents={agent_types}")
            return {"insights": [], "patterns_analyzed": 0}

        # 2. Group patterns by agent type
        patterns_by_agent = {}
        for pattern in patterns:
            agent = pattern["agent_type"]
            if agent not in patterns_by_agent:
                patterns_by_agent[agent] = []
            patterns_by_agent[agent].append(pattern)

        # 3. Use LLM to synthesize insights
        insights = await self._generate_synthesis_insights(
            task_domain, patterns_by_agent
        )

        # 4. Store synthesis session
        session_id = await self._store_synthesis_session(
            task_domain, len(patterns), insights
        )

        return {
            "session_id": session_id,
            "task_domain": task_domain,
            "patterns_analyzed": len(patterns),
            "agents_involved": list(patterns_by_agent.keys()),
            "insights": insights,
            "timestamp": datetime.now().isoformat(),
        }

    async def _get_patterns_for_synthesis(
        self, task_domain: Optional[str], agent_types: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Get patterns for synthesis from database."""
        query = """
            SELECT
                agent_type, task_domain, pattern_type, pattern_content,
                success_rate, usage_count, avg_completion_time_ms,
                avg_token_efficiency
            FROM agent_patterns
            WHERE success_rate >= 0.6  -- Only successful patterns
        """
        params = []

        if task_domain:
            params.append(task_domain)
            query += f" AND task_domain = ${len(params)}"

        if agent_types:
            params.append(agent_types)
            query += f" AND agent_type = ANY(${len(params)})"

        query += " ORDER BY success_rate DESC, usage_count DESC LIMIT 50"

        try:
            rows = await self.conn.fetch(query, *params)
            return [dict(row) for row in rows]
        except Exception as exc:
            logger.error(f"Error fetching patterns: {exc}")
            return []

    async def _generate_synthesis_insights(
        self, task_domain: str, patterns_by_agent: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, str]]:
        """Use local LLM to generate synthesis insights."""
        # Build summary for LLM
        summary = f"Task Domain: {task_domain}\n\n"
        for agent_type, patterns in patterns_by_agent.items():
            summary += f"{agent_type.upper()} Patterns ({len(patterns)}):\n"
            for i, pattern in enumerate(patterns[:5], 1):  # Top 5 per agent
                summary += f"  {i}. Success rate: {pattern['success_rate']:.1%}, "
                summary += f"Uses: {pattern['usage_count']}, "
                summary += f"Type: {pattern['pattern_type']}\n"
            summary += "\n"

        prompt = f"""Analyze these patterns from different AI agents working on {task_domain} tasks:

{summary}

Identify:
1. Common successful approaches across agents
2. Unique strengths of each agent
3. Optimization opportunities (e.g., "Qwen solves X faster, Claude could adopt this approach")
4. Patterns worth sharing between agents

Respond with 3-5 actionable insights in JSON format:
[
  {{
    "insight": "brief description",
    "agents_involved": ["agent1", "agent2"],
    "recommendation": "specific action to take",
    "potential_impact": "high/medium/low"
  }}
]

JSON:"""

        try:
            response = await self.call_local_llm(prompt, max_tokens=1500, temperature=0.4)

            # Extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "[" in response and "]" in response:
                start = response.index("[")
                end = response.rindex("]") + 1
                json_str = response[start:end]
            else:
                logger.warning("Could not extract JSON from LLM response")
                return []

            insights = json.loads(json_str)
            logger.info(f"Generated {len(insights)} synthesis insights")
            return insights

        except Exception as exc:
            logger.error(f"Error generating insights: {exc}")
            return []

    async def _store_synthesis_session(
        self, task_domain: str, patterns_analyzed: int, insights: List[Dict[str, Any]]
    ) -> str:
        """Store synthesis session in database."""
        session_id = str(uuid4())

        try:
            await self.conn.execute(
                """
                INSERT INTO federated_learning_sessions (
                    id, session_type, status, patterns_analyzed,
                    insights, metadata, completed_at
                ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
                """,
                session_id,
                "pattern_synthesis",
                "completed",
                patterns_analyzed,
                json.dumps(insights),
                json.dumps({"task_domain": task_domain}),
            )
            logger.info(f"Stored synthesis session: {session_id}")
            return session_id

        except Exception as exc:
            logger.error(f"Error storing synthesis session: {exc}")
            return session_id

    async def generate_recommendations(
        self, target_agent: str, task_domain: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generate cross-agent recommendations for a specific agent.

        Recommends patterns from other agents that could benefit target_agent.
        """
        # 1. Get target agent's capability scores
        target_capabilities = await self._get_agent_capabilities(target_agent)

        # 2. Get patterns from other agents with higher success rates
        candidate_patterns = await self._get_candidate_patterns_for_recommendation(
            target_agent, task_domain, limit * 3
        )

        if not candidate_patterns:
            logger.warning(f"No candidate patterns for {target_agent}")
            return []

        # 3. Score and rank recommendations
        recommendations = []
        for pattern in candidate_patterns:
            confidence = self._calculate_recommendation_confidence(
                pattern, target_capabilities
            )

            recommendation = {
                "pattern_id": pattern["id"],
                "source_agent": pattern["agent_type"],
                "target_agent": target_agent,
                "task_domain": pattern["task_domain"],
                "pattern_type": pattern["pattern_type"],
                "confidence_score": confidence,
                "reason": self._generate_recommendation_reason(pattern, target_agent),
                "pattern_summary": {
                    "success_rate": pattern["success_rate"],
                    "usage_count": pattern["usage_count"],
                    "avg_time_ms": pattern["avg_completion_time_ms"],
                },
            }
            recommendations.append(recommendation)

        # 4. Sort by confidence and limit
        recommendations.sort(key=lambda x: x["confidence_score"], reverse=True)
        recommendations = recommendations[:limit]

        # 5. Store recommendations in database
        for rec in recommendations:
            await self._store_recommendation(rec)

        logger.info(f"Generated {len(recommendations)} recommendations for {target_agent}")
        return recommendations

    async def _get_agent_capabilities(self, agent_type: str) -> Dict[str, float]:
        """Get capability scores for an agent."""
        try:
            rows = await self.conn.fetch(
                """
                SELECT task_domain, capability_score
                FROM agent_capability_matrix
                WHERE agent_type = $1
                """,
                agent_type,
            )
            return {row["task_domain"]: row["capability_score"] for row in rows}
        except Exception as exc:
            logger.error(f"Error getting capabilities: {exc}")
            return {}

    async def _get_candidate_patterns_for_recommendation(
        self, target_agent: str, task_domain: Optional[str], limit: int
    ) -> List[Dict[str, Any]]:
        """Get patterns from other agents that could benefit target agent."""
        query = """
            SELECT
                id, agent_type, task_domain, pattern_type, pattern_content,
                success_rate, usage_count, avg_completion_time_ms,
                avg_token_efficiency
            FROM agent_patterns
            WHERE agent_type != $1
              AND success_rate >= 0.7
              AND usage_count >= 3
        """
        params = [target_agent]

        if task_domain:
            params.append(task_domain)
            query += f" AND task_domain = ${len(params)}"

        params.append(limit)
        query += f"""
            ORDER BY success_rate DESC, usage_count DESC
            LIMIT ${len(params)}
        """

        try:
            rows = await self.conn.fetch(query, *params)
            return [dict(row) for row in rows]
        except Exception as exc:
            logger.error(f"Error getting candidate patterns: {exc}")
            return []

    def _calculate_recommendation_confidence(
        self, pattern: Dict[str, Any], target_capabilities: Dict[str, float]
    ) -> float:
        """Calculate confidence score for recommendation."""
        # Base confidence from pattern success rate
        confidence = pattern["success_rate"] * 0.5

        # Boost if target agent has low capability in this domain
        domain = pattern["task_domain"]
        if domain in target_capabilities:
            capability_gap = 0.8 - target_capabilities[domain]  # Target 0.8 capability
            if capability_gap > 0:
                confidence += capability_gap * 0.3

        # Boost for high usage count (proven pattern)
        usage_factor = min(pattern["usage_count"] / 10.0, 1.0) * 0.2
        confidence += usage_factor

        return min(confidence, 1.0)

    def _generate_recommendation_reason(
        self, pattern: Dict[str, Any], target_agent: str
    ) -> str:
        """Generate human-readable reason for recommendation."""
        source = pattern["agent_type"]
        domain = pattern["task_domain"]
        success = pattern["success_rate"]

        return (
            f"{source} has {success:.0%} success rate in {domain} tasks. "
            f"This pattern has been used {pattern['usage_count']} times successfully. "
            f"Consider adopting for {target_agent}."
        )

    async def _store_recommendation(self, rec: Dict[str, Any]):
        """Store recommendation in database."""
        try:
            rec_id = str(uuid4())
            await self.conn.execute(
                """
                INSERT INTO cross_agent_recommendations (
                    id, source_agent, target_agent, pattern_id,
                    recommendation_reason, confidence_score
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT DO NOTHING
                """,
                rec_id,
                rec["source_agent"],
                rec["target_agent"],
                rec["pattern_id"],
                rec["reason"],
                rec["confidence_score"],
            )
        except Exception as exc:
            logger.debug(f"Could not store recommendation: {exc}")


async def main():
    """Main entry point for testing."""
    synthesizer = FederatedPatternSynthesis()
    await synthesizer.connect()

    try:
        # Synthesize patterns for NixOS domain
        print("Synthesizing patterns for NixOS domain...")
        results = await synthesizer.synthesize_patterns(task_domain="nixos")
        print(f"\nResults: {json.dumps(results, indent=2)}")

        # Generate recommendations for Claude
        print("\nGenerating recommendations for Claude...")
        recs = await synthesizer.generate_recommendations(
            target_agent="claude", task_domain="nixos", limit=3
        )
        for i, rec in enumerate(recs, 1):
            print(f"\n{i}. From {rec['source_agent']} (confidence: {rec['confidence_score']:.2f})")
            print(f"   {rec['reason']}")

    finally:
        await synthesizer.close()


if __name__ == "__main__":
    asyncio.run(main())
