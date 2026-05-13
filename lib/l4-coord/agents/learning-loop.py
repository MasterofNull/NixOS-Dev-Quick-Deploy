#!/usr/bin/env python3
"""
Phase 4.2: Learning Loop Engine
Converts patterns into actionable hints and improves model behavior.

Features:
- Pattern-to-hint conversion
- Model parameter updates
- Agent routing improvements
- Gap detection
- Remediation playbook creation
- Quality metric tracking
- Continuous feedback incorporation
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

import structlog

logger = structlog.get_logger()


class HintType(Enum):
    """Type of hint"""
    ROUTING_PREFERENCE = "routing_preference"
    QUALITY_IMPROVEMENT = "quality_improvement"
    ERROR_AVOIDANCE = "error_avoidance"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    BEST_PRACTICE = "best_practice"


class Hint:
    """Represents a generated hint for improving agent behavior"""

    def __init__(
        self,
        hint_id: str,
        hint_type: HintType,
        title: str,
        description: str,
        target_agent: Optional[str] = None,
        priority: int = 1,  # 1=low, 5=critical
        effectiveness: float = 0.0,
        usage_count: int = 0,
        success_count: int = 0,
    ):
        self.hint_id = hint_id
        self.hint_type = hint_type
        self.title = title
        self.description = description
        self.target_agent = target_agent
        self.priority = priority
        self.effectiveness = effectiveness
        self.usage_count = usage_count
        self.success_count = success_count
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def update_effectiveness(self):
        """Update effectiveness based on usage and success"""
        if self.usage_count == 0:
            self.effectiveness = 0.0
        else:
            self.effectiveness = self.success_count / self.usage_count

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "hint_id": self.hint_id,
            "hint_type": self.hint_type.value,
            "title": self.title,
            "description": self.description,
            "target_agent": self.target_agent,
            "priority": self.priority,
            "effectiveness": round(self.effectiveness, 3),
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class GapDetection:
    """Represents a detected knowledge gap"""

    def __init__(
        self,
        gap_id: str,
        description: str,
        severity: int = 1,  # 1=minor, 5=critical
        affected_query_types: Optional[List[str]] = None,
        remediation_required: bool = True,
    ):
        self.gap_id = gap_id
        self.description = description
        self.severity = severity
        self.affected_query_types = affected_query_types or []
        self.remediation_required = remediation_required
        self.created_at = datetime.now(timezone.utc)
        self.remediation_status = "pending"  # pending, in_progress, resolved
        self.remediation_playbook: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "gap_id": self.gap_id,
            "description": self.description,
            "severity": self.severity,
            "affected_query_types": self.affected_query_types,
            "remediation_required": self.remediation_required,
            "remediation_status": self.remediation_status,
            "created_at": self.created_at.isoformat(),
        }


class LearningLoopEngine:
    """
    Processes patterns and generates hints for continuous improvement.

    Usage:
        engine = LearningLoopEngine()
        hints = await engine.generate_hints_from_patterns(patterns)
        gaps = await engine.detect_gaps(interactions)
    """

    def __init__(self, data_root: Optional[str] = None):
        """Initialize learning loop engine"""
        self.data_root = Path(
            os.path.expanduser(
                data_root or os.getenv("LEARNING_LOOP_DATA_ROOT")
                or os.getenv("DATA_DIR")
                or "~/.local/share/nixos-ai-stack/learning"
            )
        )
        self.data_root.mkdir(parents=True, exist_ok=True)

        # Hints and gaps storage
        self.hints: Dict[str, Hint] = {}
        self.gaps: Dict[str, GapDetection] = {}

        # Configuration
        self.min_pattern_confidence = 0.6
        self.min_pattern_frequency = 3

        logger.info("learning_loop_engine_initialized", root=str(self.data_root))

    async def generate_hints_from_patterns(
        self, patterns: Dict[str, List[Any]]
    ) -> List[Hint]:
        """Convert detected patterns into actionable hints"""
        hints: List[Hint] = []

        try:
            # Generate routing preference hints
            hints.extend(await self._generate_routing_hints(patterns))

            # Generate quality improvement hints
            hints.extend(await self._generate_quality_hints(patterns))

            # Generate error avoidance hints
            hints.extend(await self._generate_error_avoidance_hints(patterns))

            # Generate performance optimization hints
            hints.extend(await self._generate_performance_hints(patterns))

            # Store hints
            for hint in hints:
                self.hints[hint.hint_id] = hint

            logger.info("hints_generated", count=len(hints))
            return hints

        except Exception as e:
            logger.error("hint_generation_failed", error=str(e))
            return []

    async def _generate_routing_hints(self, patterns: Dict[str, List[Any]]) -> List[Hint]:
        """Generate hints for improving query routing"""
        hints: List[Hint] = []

        try:
            agent_perf = patterns.get("agent_performance", [])

            for pattern in agent_perf:
                if hasattr(pattern, "metadata") and "primary_query_types" in pattern.metadata:
                    agent = pattern.associated_agents[0] if pattern.associated_agents else "unknown"
                    primary_types = pattern.metadata["primary_query_types"]

                    if pattern.success_rate > 0.8:
                        hint_id = f"routing_preference_{agent}"
                        hint = Hint(
                            hint_id=hint_id,
                            hint_type=HintType.ROUTING_PREFERENCE,
                            title=f"Route {list(primary_types.keys())[0]} queries to {agent}",
                            description=f"Agent {agent} has {pattern.success_rate*100:.1f}% success rate for this query type",
                            target_agent=agent,
                            priority=3,
                        )
                        hint.effectiveness = pattern.success_rate
                        hints.append(hint)

            return hints
        except Exception as e:
            logger.error("routing_hint_generation_failed", error=str(e))
            return []

    async def _generate_quality_hints(self, patterns: Dict[str, List[Any]]) -> List[Hint]:
        """Generate hints for improving response quality"""
        hints: List[Hint] = []

        try:
            success_patterns = patterns.get("success_patterns", [])

            for pattern in success_patterns:
                if pattern.success_rate > 0.85:
                    hint_id = f"quality_improvement_{pattern.pattern_id}"
                    hint = Hint(
                        hint_id=hint_id,
                        hint_type=HintType.QUALITY_IMPROVEMENT,
                        title=f"Adopt successful pattern from {pattern.pattern_id}",
                        description=f"This pattern achieved {pattern.success_rate*100:.1f}% success rate",
                        priority=2,
                    )
                    hint.effectiveness = pattern.success_rate
                    hints.append(hint)

            return hints
        except Exception as e:
            logger.error("quality_hint_generation_failed", error=str(e))
            return []

    async def _generate_error_avoidance_hints(self, patterns: Dict[str, List[Any]]) -> List[Hint]:
        """Generate hints for avoiding common errors"""
        hints: List[Hint] = []

        try:
            failure_patterns = patterns.get("failure_patterns", [])

            for pattern in failure_patterns:
                if pattern.frequency > self.min_pattern_frequency:
                    hint_id = f"error_avoidance_{pattern.pattern_id}"
                    hint = Hint(
                        hint_id=hint_id,
                        hint_type=HintType.ERROR_AVOIDANCE,
                        title=f"Avoid error pattern: {pattern.description[:50]}",
                        description=f"This error occurred {pattern.frequency} times. Known mitigation: validate inputs before processing.",
                        priority=4,  # High priority for error avoidance
                    )
                    hints.append(hint)

            return hints
        except Exception as e:
            logger.error("error_avoidance_hint_generation_failed", error=str(e))
            return []

    async def _generate_performance_hints(self, patterns: Dict[str, List[Any]]) -> List[Hint]:
        """Generate hints for optimizing performance"""
        hints: List[Hint] = []

        try:
            agent_perf = patterns.get("agent_performance", [])

            for pattern in agent_perf:
                if hasattr(pattern, "metadata") and "avg_execution_time_ms" in pattern.metadata:
                    avg_time = pattern.metadata["avg_execution_time_ms"]
                    agent = pattern.associated_agents[0] if pattern.associated_agents else "unknown"

                    if avg_time > 5000:  # > 5 seconds
                        hint_id = f"perf_optimization_{agent}"
                        hint = Hint(
                            hint_id=hint_id,
                            hint_type=HintType.PERFORMANCE_OPTIMIZATION,
                            title=f"Optimize {agent} execution time",
                            description=f"Currently averaging {avg_time}ms. Consider caching or batching.",
                            target_agent=agent,
                            priority=2,
                        )
                        hints.append(hint)

            return hints
        except Exception as e:
            logger.error("performance_hint_generation_failed", error=str(e))
            return []

    async def detect_gaps(
        self, interactions: List[Dict[str, Any]]
    ) -> List[GapDetection]:
        """Detect knowledge gaps from interaction patterns"""
        gaps: List[GapDetection] = []

        try:
            # Analyze query type coverage
            query_types: Dict[str, int] = {}
            query_type_success: Dict[str, int] = {}

            for interaction in interactions:
                qtype = interaction.get("query_type", "unknown")
                query_types[qtype] = query_types.get(qtype, 0) + 1

                if interaction.get("status") == "success":
                    query_type_success[qtype] = query_type_success.get(qtype, 0) + 1

            # Identify gaps
            for qtype, count in query_types.items():
                success_count = query_type_success.get(qtype, 0)
                success_rate = success_count / count if count > 0 else 0

                if success_rate < 0.5:  # Less than 50% success
                    gap_id = f"gap_low_success_{qtype}"
                    gap = GapDetection(
                        gap_id=gap_id,
                        description=f"Low success rate ({success_rate*100:.1f}%) for {qtype} queries",
                        severity=4,
                        affected_query_types=[qtype],
                        remediation_required=True,
                    )

                    # Create remediation playbook
                    gap.remediation_playbook = {
                        "steps": [
                            "Analyze failures in this query type",
                            "Identify common error patterns",
                            "Propose routing changes or agent improvements",
                            "Test with 10 new queries",
                            "Validate success rate improvement",
                        ],
                        "success_criteria": "Achieve 70%+ success rate",
                    }

                    gaps.append(gap)
                    self.gaps[gap_id] = gap

            logger.info("gaps_detected", count=len(gaps))
            return gaps

        except Exception as e:
            logger.error("gap_detection_failed", error=str(e))
            return []

    async def apply_hint_feedback(self, hint_id: str, success: bool) -> bool:
        """Record feedback on hint effectiveness"""
        try:
            if hint_id not in self.hints:
                logger.warning("hint_not_found", hint_id=hint_id)
                return False

            hint = self.hints[hint_id]
            hint.usage_count += 1
            if success:
                hint.success_count += 1

            hint.update_effectiveness()
            hint.updated_at = datetime.now(timezone.utc)

            logger.info("hint_feedback_recorded", hint_id=hint_id, effectiveness=hint.effectiveness)
            return True

        except Exception as e:
            logger.error("hint_feedback_failed", error=str(e))
            return False

    async def resolve_gap(self, gap_id: str, resolution: Dict[str, Any]) -> bool:
        """Mark a gap as resolved with remediation details"""
        try:
            if gap_id not in self.gaps:
                logger.warning("gap_not_found", gap_id=gap_id)
                return False

            gap = self.gaps[gap_id]
            gap.remediation_status = "resolved"
            gap.remediation_playbook = resolution

            logger.info("gap_resolved", gap_id=gap_id)
            return True

        except Exception as e:
            logger.error("gap_resolution_failed", error=str(e))
            return False

    async def get_active_hints(
        self, min_effectiveness: float = 0.0, limit: int = 10
    ) -> List[Hint]:
        """Get active hints sorted by effectiveness"""
        try:
            active = [
                h for h in self.hints.values()
                if h.effectiveness >= min_effectiveness
            ]

            # Sort by priority (descending) and effectiveness (descending)
            active.sort(key=lambda h: (h.priority, h.effectiveness), reverse=True)

            return active[:limit]
        except Exception as e:
            logger.error("get_active_hints_failed", error=str(e))
            return []

    async def get_unresolved_gaps(self, limit: int = 10) -> List[GapDetection]:
        """Get unresolved gaps sorted by severity"""
        try:
            unresolved = [
                g for g in self.gaps.values()
                if g.remediation_status != "resolved"
            ]

            # Sort by severity (descending)
            unresolved.sort(key=lambda g: g.severity, reverse=True)

            return unresolved[:limit]
        except Exception as e:
            logger.error("get_unresolved_gaps_failed", error=str(e))
            return []

    async def get_learning_metrics(self) -> Dict[str, Any]:
        """Get learning loop metrics"""
        try:
            total_hints = len(self.hints)
            effective_hints = sum(1 for h in self.hints.values() if h.effectiveness > 0.6)
            high_priority_hints = sum(1 for h in self.hints.values() if h.priority >= 4)

            total_gaps = len(self.gaps)
            unresolved_gaps = sum(1 for g in self.gaps.values() if g.remediation_status != "resolved")
            critical_gaps = sum(1 for g in self.gaps.values() if g.severity >= 4)

            avg_hint_effectiveness = (
                sum(h.effectiveness for h in self.hints.values()) / total_hints
                if total_hints > 0 else 0.0
            )

            return {
                "total_hints": total_hints,
                "effective_hints": effective_hints,
                "high_priority_hints": high_priority_hints,
                "avg_hint_effectiveness": round(avg_hint_effectiveness, 3),
                "total_gaps": total_gaps,
                "unresolved_gaps": unresolved_gaps,
                "critical_gaps": critical_gaps,
                "learning_health": "good" if unresolved_gaps <= 5 else "degraded" if unresolved_gaps <= 10 else "critical",
            }
        except Exception as e:
            logger.error("metrics_computation_failed", error=str(e))
            return {}

    async def export_learning_state(self) -> Dict[str, Any]:
        """Export current learning state"""
        try:
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hints": {hid: h.to_dict() for hid, h in self.hints.items()},
                "gaps": {gid: g.to_dict() for gid, g in self.gaps.items()},
                "metrics": await self.get_learning_metrics(),
            }
        except Exception as e:
            logger.error("state_export_failed", error=str(e))
            return {}
