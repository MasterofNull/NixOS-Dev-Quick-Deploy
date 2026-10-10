#!/usr/bin/env python3
"""
Meta-Optimizer for Harness Self-Improvement

Analyzes harness performance and generates improvement proposals for:
- Routing rules and classification accuracy
- Hint template effectiveness
- Lesson library quality
- Tool discovery patterns
- Agent role assignments

Part of Phase 3: Meta-Optimization
"""

import asyncio
import asyncpg
import aiohttp
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from uuid import uuid4

_SHARED = Path(__file__).resolve().parents[2] / "ai-stack" / "mcp-servers" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
from llm_config import build_llama_payload, AGENT_TASK_MAX_TOKENS

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import routing_source

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("meta_optimizer")

# Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ai_context")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

LLAMA_CHAT_URL = os.getenv("LLAMA_CHAT_URL", "http://127.0.0.1:8080")


class OptimizationTarget(str, Enum):
    """Areas of harness that can be optimized"""
    ROUTING_RULES = "routing_rules"
    HINT_TEMPLATES = "hint_templates"
    LESSON_LIBRARY = "lesson_library"
    TOOL_DISCOVERY = "tool_discovery"
    AGENT_ROLES = "agent_roles"


class ProposalPriority(str, Enum):
    """Priority levels for improvement proposals"""
    CRITICAL = "critical"  # Immediate action needed
    HIGH = "high"          # Should be addressed soon
    MEDIUM = "medium"      # Moderate impact
    LOW = "low"            # Nice to have


@dataclass
class ImprovementProposal:
    """Structured improvement proposal for harness optimization"""
    id: str
    target: OptimizationTarget
    priority: ProposalPriority
    title: str
    description: str
    current_state: str
    proposed_change: str
    expected_impact: str
    estimated_improvement_pct: float
    confidence_score: float  # 0-1, how confident we are this will help
    evidence: Dict[str, Any]  # Supporting metrics/data
    implementation_steps: List[str]
    rollback_plan: str
    created_at: datetime
    created_by: str = "meta_optimizer"
    status: str = "pending"  # pending, approved, rejected, applied, rolled_back

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['target'] = self.target.value
        d['priority'] = self.priority.value
        d['created_at'] = self.created_at.isoformat()
        return d


class MetaOptimizer:
    """
    Analyzes harness performance and generates self-improvement proposals.
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
        # The local model is slow (minutes per long prompt) and may be serving another job; a short
        # timeout turns every analysis into a silent empty result.
        self.http_client = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=float(os.getenv("META_OPT_LLM_TIMEOUT_S", "900"))))

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
        await self.http_client.close()

    async def call_local_llm(
        self, prompt: str, max_tokens: int = 1500, temperature: float = 0.3
    ) -> str:
        """Call local LLM for analysis."""
        try:
            async with self.http_client.post(
                f"{self.llama_url}/v1/chat/completions",
                json=build_llama_payload(
                    [
                        {
                            "role": "system",
                            "content": "You are a system optimizer analyzing AI harness performance. "
                                       "Provide structured, actionable recommendations based on data."
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    task_type="reasoning",
                ),
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return result["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.error(f"LLM call failed: {type(exc).__name__}: {exc}")
            return ""

    async def _table_exists(self, name: str) -> bool:
        """True if a public table exists (to_regclass avoids an error on missing tables)."""
        return bool(await self.conn.fetchval("SELECT to_regclass($1) IS NOT NULL", f"public.{name}"))

    async def analyze_routing_accuracy(
        self, days: int = 7
    ) -> Optional[ImprovementProposal]:
        """
        Analyze routing classification accuracy and suggest improvements.
        """
        # Routing statistics come from the agent-run event log.
        try:
            routing_stats = await asyncio.to_thread(routing_source.aggregate_routing, days)
            switchboard = await asyncio.to_thread(routing_source.switchboard_decisions, days)

            if not routing_stats:
                logger.info("No routing data available for analysis")
                return None

            # Build analysis summary for LLM
            summary = self._format_routing_summary(routing_stats)

            # Ask LLM to analyze routing patterns
            prompt = f"""Analyze these routing statistics from the last {days} days:

{summary}

Identify:
1. Routing patterns with high latency or failure rates
2. Model/agent type mismatches (wrong model for task type)
3. Classification improvements that could reduce latency or cost
4. Specific routing rules that should be added or modified

Respond in JSON format:
{{
  "issues_found": ["issue 1", "issue 2", ...],
  "proposed_changes": ["change 1", "change 2", ...],
  "expected_improvement_pct": <number 0-100>,
  "confidence": <number 0-1>
}}

JSON:"""

            llm_response = await self.call_local_llm(prompt, max_tokens=1500)
            if not llm_response:
                logger.warning("Routing analysis skipped: local LLM returned nothing (see LLM call error)")
                return None

            # Parse LLM response
            analysis = self._parse_llm_json_response(llm_response)

            if not analysis or not analysis.get("issues_found"):
                logger.info("No routing optimization opportunities identified")
                return None

            # Create improvement proposal
            proposal = ImprovementProposal(
                id=str(uuid4()),
                target=OptimizationTarget.ROUTING_RULES,
                priority=self._determine_priority(analysis.get("expected_improvement_pct", 0)),
                title=f"Improve routing classification accuracy ({days}d analysis)",
                description="; ".join(analysis.get("issues_found", [])),
                current_state=summary,
                proposed_change="\n".join(analysis.get("proposed_changes", [])),
                expected_impact=f"Reduce latency and improve task routing accuracy",
                estimated_improvement_pct=float(analysis.get("expected_improvement_pct", 0)),
                confidence_score=float(analysis.get("confidence", 0.5)),
                evidence={
                    "routing_stats": routing_stats[:50],
                    "switchboard_decisions": switchboard,
                    "analysis_period_days": days,
                    "total_routes": sum(row["count"] for row in routing_stats),
                },
                implementation_steps=[
                    "Review proposed routing rule changes",
                    "Update route_handler.py classification logic",
                    "Deploy and monitor for 24 hours",
                    "Validate improvement metrics",
                ],
                rollback_plan="Revert route_handler.py to previous commit if accuracy degrades",
                created_at=datetime.now(),
            )

            return proposal

        except Exception as exc:
            logger.error(f"Error analyzing routing accuracy: {exc}")
            return None

    async def analyze_hint_effectiveness(
        self, days: int = 7
    ) -> Optional[ImprovementProposal]:
        """
        Analyze hint template effectiveness and suggest improvements.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        try:
            if not await self._table_exists("interaction_history"):
                logger.info("No data source for hint analysis: interaction_history table missing")
                return None
            # Query hint usage and effectiveness from interaction_history
            hint_stats = await self.conn.fetch(
                """
                SELECT
                    metadata->>'hint_template' as hint_template,
                    COUNT(*) as usage_count,
                    AVG(CASE WHEN outcome = 'success' THEN 1.0 ELSE 0.0 END)::float8 as success_rate,
                    AVG(latency_ms)::float8 as avg_completion_time,
                    AVG(COALESCE(tokens_in, 0) + COALESCE(tokens_out, 0))::float8 as avg_tokens
                FROM interaction_history
                WHERE created_at >= $1
                  AND metadata->>'hint_template' IS NOT NULL
                GROUP BY metadata->>'hint_template'
                HAVING COUNT(*) >= 5  -- Need statistical significance
                ORDER BY usage_count DESC
                """,
                since
            )

            if not hint_stats:
                logger.info("No hint usage data available")
                return None

            # Identify hints with low success rates or high token usage
            problematic_hints = [
                row for row in hint_stats
                if row["success_rate"] < 0.6 or row["avg_tokens"] > 1000
            ]

            if not problematic_hints:
                logger.info("All hints performing well")
                return None

            summary = self._format_hint_summary(hint_stats, problematic_hints)

            prompt = f"""Analyze hint template effectiveness:

{summary}

Identify:
1. Hints with low success rates that should be revised
2. Hints with high token usage that could be made more concise
3. Missing hint patterns that would improve guidance
4. Specific hint template improvements

Respond in JSON format:
{{
  "hints_to_revise": [{{"template": "name", "reason": "why", "suggested_improvement": "how"}}],
  "new_hints_needed": ["hint 1", "hint 2"],
  "expected_improvement_pct": <number>,
  "confidence": <number 0-1>
}}

JSON:"""

            llm_response = await self.call_local_llm(prompt, max_tokens=2000)
            if not llm_response:
                logger.warning("Hint analysis skipped: local LLM returned nothing (see LLM call error)")
                return None
            analysis = self._parse_llm_json_response(llm_response)

            if not analysis or not (analysis.get("hints_to_revise") or analysis.get("new_hints_needed")):
                return None

            proposal = ImprovementProposal(
                id=str(uuid4()),
                target=OptimizationTarget.HINT_TEMPLATES,
                priority=self._determine_priority(analysis.get("expected_improvement_pct", 0)),
                title=f"Improve hint template effectiveness ({days}d analysis)",
                description=f"Revise {len(analysis.get('hints_to_revise', []))} underperforming hints, "
                           f"add {len(analysis.get('new_hints_needed', []))} new patterns",
                current_state=summary,
                proposed_change=json.dumps(analysis, indent=2),
                expected_impact="Improve task success rates and reduce token usage",
                estimated_improvement_pct=float(analysis.get("expected_improvement_pct", 0)),
                confidence_score=float(analysis.get("confidence", 0.5)),
                evidence={
                    "hint_stats": [dict(row) for row in hint_stats],
                    "problematic_count": len(problematic_hints),
                },
                implementation_steps=[
                    "Review proposed hint template changes",
                    "Update hints_engine.py with revised templates",
                    "Add new hint patterns as identified",
                    "Deploy and monitor hint effectiveness",
                ],
                rollback_plan="Revert hints_engine.py to previous templates if success rates decline",
                created_at=datetime.now(),
            )

            return proposal

        except Exception as exc:
            logger.error(f"Error analyzing hint effectiveness: {exc}")
            return None

    async def analyze_lesson_library(
        self, days: int = 30
    ) -> Optional[ImprovementProposal]:
        """
        Analyze lesson library effectiveness and suggest curation.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        try:
            if not await self._table_exists("agent_patterns"):
                logger.info(
                    "No data source for lesson analysis: agent_patterns table missing "
                    "(only created by raw SQL 007_federated_learning.sql, not by alembic)"
                )
                return None
            # Query lesson usage and effectiveness from agent_patterns
            lesson_stats = await self.conn.fetch(
                """
                SELECT
                    pattern_type,
                    task_domain,
                    success_rate,
                    usage_count,
                    total_attempts,
                    avg_completion_time_ms,
                    avg_token_efficiency,
                    last_used
                FROM agent_patterns
                WHERE first_seen >= $1
                   OR last_used >= $1
                ORDER BY usage_count DESC
                """,
                since
            )

            if not lesson_stats:
                logger.info("No lesson data available")
                return None

            # Identify lessons to promote, demote, or remove
            high_value = [r for r in lesson_stats if r["success_rate"] > 0.8 and r["usage_count"] > 10]
            low_value = [r for r in lesson_stats if r["success_rate"] < 0.4 or r["usage_count"] == 0]
            stale = [r for r in lesson_stats if r["last_used"] and (datetime.now(timezone.utc) - r["last_used"]).days > 90]

            summary = f"""Lesson Library Analysis ({days} days):
Total Lessons: {len(lesson_stats)}
High-Value (>80% success, >10 uses): {len(high_value)}
Low-Value (<40% success or unused): {len(low_value)}
Stale (not used in 90+ days): {len(stale)}

Sample High-Value:
{json.dumps([dict(r) for r in high_value[:5]], indent=2, default=str)}

Sample Low-Value:
{json.dumps([dict(r) for r in low_value[:5]], indent=2, default=str)}
"""

            prompt = f"""{summary}

Recommend lesson library curation:
1. Lessons to promote (make more visible/prioritized)
2. Lessons to revise or merge
3. Lessons to archive (low value, stale)
4. New lesson patterns needed

Respond in JSON format:
{{
  "promote": ["pattern 1", "pattern 2"],
  "revise": ["pattern 1", "pattern 2"],
  "archive": ["pattern 1", "pattern 2"],
  "new_needed": ["pattern 1", "pattern 2"],
  "expected_improvement_pct": <number>,
  "confidence": <number 0-1>
}}

JSON:"""

            llm_response = await self.call_local_llm(prompt, max_tokens=2000)
            if not llm_response:
                logger.warning("Lesson analysis skipped: local LLM returned nothing (see LLM call error)")
                return None
            analysis = self._parse_llm_json_response(llm_response)

            if not analysis:
                return None

            proposal = ImprovementProposal(
                id=str(uuid4()),
                target=OptimizationTarget.LESSON_LIBRARY,
                priority=self._determine_priority(analysis.get("expected_improvement_pct", 0)),
                title=f"Curate lesson library ({days}d analysis)",
                description=f"Promote {len(analysis.get('promote', []))}, "
                           f"revise {len(analysis.get('revise', []))}, "
                           f"archive {len(analysis.get('archive', []))} lessons",
                current_state=summary,
                proposed_change=json.dumps(analysis, indent=2),
                expected_impact="Improve lesson retrieval relevance and reduce noise",
                estimated_improvement_pct=float(analysis.get("expected_improvement_pct", 0)),
                confidence_score=float(analysis.get("confidence", 0.5)),
                evidence={
                    "total_lessons": len(lesson_stats),
                    "high_value_count": len(high_value),
                    "low_value_count": len(low_value),
                    "stale_count": len(stale),
                },
                implementation_steps=[
                    "Review proposed lesson curation changes",
                    "Update lesson priorities in database",
                    "Archive low-value patterns",
                    "Monitor lesson retrieval effectiveness",
                ],
                rollback_plan="Restore archived lessons if retrieval quality degrades",
                created_at=datetime.now(),
            )

            return proposal

        except Exception as exc:
            logger.error(f"Error analyzing lesson library: {exc}")
            return None

    async def analyze_tool_discovery(
        self, days: int = 7
    ) -> Optional[ImprovementProposal]:
        """
        Analyze tool discovery patterns and surface underutilized capabilities.
        """
        # This would analyze MCP tool usage patterns
        # For now, return None as this requires integration with capability_discovery module
        logger.info("Tool discovery analysis not yet implemented")
        return None

    async def generate_all_proposals(
        self, days: int = 7
    ) -> List[ImprovementProposal]:
        """
        Generate improvement proposals across all optimization targets.
        """
        proposals = []

        # Sequential: the analyses share one asyncpg connection (concurrent use raises
        # "another operation is in progress") and the local model serves one slot.
        for analyze in (self.analyze_routing_accuracy, self.analyze_hint_effectiveness,
                        self.analyze_lesson_library, self.analyze_tool_discovery):
            try:
                result = await analyze(days)
            except Exception as exc:
                logger.error(f"Analysis failed: {exc}")
                continue
            if result is not None:
                proposals.append(result)

        return proposals

    async def store_proposal(self, proposal: ImprovementProposal) -> bool:
        """
        Store improvement proposal in database.
        """
        try:
            await self.conn.execute(
                """
                INSERT INTO harness_improvement_proposals (
                    id, target, priority, title, description,
                    current_state, proposed_change, expected_impact,
                    estimated_improvement_pct, confidence_score,
                    evidence, implementation_steps, rollback_plan,
                    created_at, created_by, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                """,
                proposal.id,
                proposal.target.value,
                proposal.priority.value,
                proposal.title,
                proposal.description,
                proposal.current_state,
                proposal.proposed_change,
                proposal.expected_impact,
                proposal.estimated_improvement_pct,
                proposal.confidence_score,
                json.dumps(proposal.evidence),
                json.dumps(proposal.implementation_steps),
                proposal.rollback_plan,
                proposal.created_at,
                proposal.created_by,
                proposal.status,
            )
            logger.info(f"Stored proposal: {proposal.id} - {proposal.title}")
            return True
        except Exception as exc:
            logger.error(f"Error storing proposal: {exc}")
            return False

    def _format_routing_summary(self, stats: List[Dict]) -> str:
        """Format routing statistics for LLM analysis."""
        lines = ["Routing Statistics:"]
        for row in stats[:20]:  # Top 20 routes
            lines.append(
                f"- {row['model_used']} ({row['agent_type']}): "
                f"{row['count']} routes, {row['status']}, "
                f"avg latency {row['avg_latency']:.0f}ms"
            )
        return "\n".join(lines)

    def _format_hint_summary(
        self, all_stats: List[Dict], problematic: List[Dict]
    ) -> str:
        """Format hint statistics for LLM analysis."""
        lines = [
            f"Hint Template Analysis:",
            f"Total templates tracked: {len(all_stats)}",
            f"Problematic (low success or high tokens): {len(problematic)}",
            "",
            "Problematic Hints:"
        ]
        for row in problematic:
            lines.append(
                f"- {row['hint_template']}: "
                f"success {row['success_rate']:.1%}, "
                f"{row['usage_count']} uses, "
                f"avg {row['avg_tokens']:.0f} tokens"
            )
        return "\n".join(lines)

    def _parse_llm_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response."""
        if not response:
            return None

        try:
            # Try direct parse first
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting from code blocks
        if "```json" in response:
            try:
                json_str = response.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (IndexError, json.JSONDecodeError):
                pass

        # Try finding JSON object
        if "{" in response and "}" in response:
            try:
                start = response.index("{")
                end = response.rindex("}") + 1
                json_str = response[start:end]
                return json.loads(json_str)
            except (ValueError, json.JSONDecodeError):
                pass

        logger.warning("Could not parse LLM JSON response")
        return None

    def _determine_priority(self, expected_improvement_pct: float) -> ProposalPriority:
        """Determine proposal priority based on expected improvement."""
        if expected_improvement_pct >= 20:
            return ProposalPriority.CRITICAL
        elif expected_improvement_pct >= 10:
            return ProposalPriority.HIGH
        elif expected_improvement_pct >= 5:
            return ProposalPriority.MEDIUM
        else:
            return ProposalPriority.LOW


def parse_args(argv: Optional[List[str]] = None):
    """CLI flags passed by nix/modules/services/meta-optimization.nix."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate harness improvement proposals")
    parser.add_argument("--days", type=int, default=int(os.getenv("ANALYSIS_WINDOW_DAYS", "7")),
                        help="analysis window in days (default: $ANALYSIS_WINDOW_DAYS or 7)")
    parser.add_argument("--output-dir", default=None,
                        help="directory where a proposals-<timestamp>.json dump is written")
    return parser.parse_args(argv)


def dump_proposals(proposals: List[ImprovementProposal], output_dir: str) -> Path:
    """Write generated proposals as JSON into output_dir; returns the file path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"proposals-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps([asdict(p) for p in proposals], indent=2, default=str))
    return path


async def main(args=None):
    """Main entry point for testing."""
    args = args or parse_args([])
    optimizer = MetaOptimizer()
    await optimizer.connect()

    try:
        print("Generating improvement proposals...")
        proposals = await optimizer.generate_all_proposals(days=args.days)

        print(f"\nGenerated {len(proposals)} proposals:")
        for i, proposal in enumerate(proposals, 1):
            print(f"\n{i}. [{proposal.priority.value.upper()}] {proposal.title}")
            print(f"   Target: {proposal.target.value}")
            print(f"   Expected improvement: {proposal.estimated_improvement_pct:.1f}%")
            print(f"   Confidence: {proposal.confidence_score:.2f}")
            print(f"   Description: {proposal.description}")

            # Store proposal
            await optimizer.store_proposal(proposal)

        if args.output_dir:
            print(f"\nProposals JSON written to {dump_proposals(proposals, args.output_dir)}")

        if not proposals:
            print("\nNo optimization opportunities identified at this time.")

    finally:
        await optimizer.close()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
