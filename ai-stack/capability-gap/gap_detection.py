#!/usr/bin/env python3
"""
Automated Capability Gap Detection

Continuous scanning and classification of capability gaps with priority scoring.
Part of Phase 9 Batch 9.1: Gap Detection Automation

Key Features:
- Continuous capability scanning
- Failure pattern analysis
- Gap classification (tool, knowledge, skill, pattern)
- Gap priority scoring
- Gap detection from user feedback
"""

import asyncio
import hashlib
import json
import logging
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class GapType(Enum):
    """Types of capability gaps"""
    TOOL = "tool"  # Missing tool/command
    KNOWLEDGE = "knowledge"  # Missing domain knowledge
    SKILL = "skill"  # Missing procedural skill
    PATTERN = "pattern"  # Missing workflow pattern
    INTEGRATION = "integration"  # Missing integration/connection


class GapSeverity(Enum):
    """Gap severity levels"""
    CRITICAL = 4  # Blocks core functionality
    HIGH = 3  # Significantly impacts quality
    MEDIUM = 2  # Causes workarounds
    LOW = 1  # Minor inconvenience


@dataclass
class CapabilityGap:
    """Detected capability gap"""
    gap_id: str
    gap_type: GapType
    severity: GapSeverity
    description: str
    detected_at: datetime = field(default_factory=datetime.now)

    # Evidence
    failure_count: int = 1
    failure_patterns: List[str] = field(default_factory=list)
    affected_tasks: List[str] = field(default_factory=list)
    user_feedback: List[str] = field(default_factory=list)

    # Scoring
    priority_score: float = 0.0
    impact_score: float = 0.0
    frequency_score: float = 0.0

    # Context
    context: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.gap_id)

    def __eq__(self, other):
        if not isinstance(other, CapabilityGap):
            return False
        return self.gap_id == other.gap_id


class FailurePatternAnalyzer:
    """Analyze failure patterns to detect gaps"""

    def __init__(self):
        self.failure_history: deque = deque(maxlen=1000)
        self.pattern_cache: Dict[str, List[str]] = defaultdict(list)

        # Known failure patterns
        self.tool_patterns = [
            r"command not found:\s+(\S+)",
            r"(\S+):\s+not found",
            r"No such file or directory:\s+(\S+)",
            r"ModuleNotFoundError:\s+No module named '(\S+)'",
            r"ImportError:\s+cannot import name '(\S+)'",
        ]

        self.knowledge_patterns = [
            r"I don't know (how to|about|the) (.+)",
            r"I'm not (familiar|aware|sure) (.+)",
            r"no documentation (found|available) for (.+)",
            r"unclear (how|what|why) (.+)",
        ]

        self.skill_patterns = [
            r"unable to (perform|execute|complete) (.+)",
            r"failed to (implement|create|build) (.+)",
            r"don't know how to (.+)",
            r"missing (procedure|workflow) for (.+)",
        ]

        logger.info("Failure Pattern Analyzer initialized")

    def analyze_failure(self, error_text: str, task: str) -> List[Tuple[GapType, str]]:
        """Analyze failure text and extract potential gaps"""
        gaps = []

        # Check tool patterns
        for pattern in self.tool_patterns:
            matches = re.findall(pattern, error_text, re.IGNORECASE)
            for match in matches:
                tool_name = match if isinstance(match, str) else match[0]
                gaps.append((GapType.TOOL, f"Missing tool: {tool_name}"))

        # Check knowledge patterns
        for pattern in self.knowledge_patterns:
            matches = re.findall(pattern, error_text, re.IGNORECASE)
            for match in matches:
                knowledge = match if isinstance(match, str) else match[-1]
                gaps.append((GapType.KNOWLEDGE, f"Missing knowledge: {knowledge}"))

        # Check skill patterns
        for pattern in self.skill_patterns:
            matches = re.findall(pattern, error_text, re.IGNORECASE)
            for match in matches:
                skill = match if isinstance(match, str) else match[-1]
                gaps.append((GapType.SKILL, f"Missing skill: {skill}"))

        # Record failure
        self.failure_history.append({
            "timestamp": datetime.now(),
            "task": task,
            "error": error_text,
            "detected_gaps": gaps,
        })

        # Update pattern cache
        for gap_type, description in gaps:
            self.pattern_cache[gap_type.value].append(description)

        return gaps

    def get_failure_frequency(self, gap_description: str) -> int:
        """Get frequency of specific gap appearing in failures"""
        count = 0
        for failures in self.pattern_cache.values():
            count += failures.count(gap_description)
        return count

    def get_recent_failures(self, hours: int = 24) -> List[Dict]:
        """Get failures from recent time window"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [
            f for f in self.failure_history
            if f["timestamp"] > cutoff
        ]
        return recent


class GapClassifier:
    """Classify gaps by type and characteristics"""

    def __init__(self):
        # Classification rules
        self.tool_keywords = {"command", "tool", "binary", "executable", "package", "module"}
        self.knowledge_keywords = {"know", "understand", "familiar", "aware", "documentation"}
        self.skill_keywords = {"how to", "procedure", "workflow", "implement", "create"}
        self.pattern_keywords = {"pattern", "template", "framework", "approach", "method"}

        logger.info("Gap Classifier initialized")

    def classify(self, description: str, context: Dict = None) -> GapType:
        """Classify gap type from description and context"""
        desc_lower = description.lower()

        # Check for explicit type
        if "missing tool" in desc_lower or "command not found" in desc_lower:
            return GapType.TOOL

        if "missing knowledge" in desc_lower:
            return GapType.KNOWLEDGE

        if "missing skill" in desc_lower:
            return GapType.SKILL

        if "missing pattern" in desc_lower:
            return GapType.PATTERN

        # Keyword-based classification
        desc_words = set(desc_lower.split())

        tool_score = len(desc_words & self.tool_keywords)
        knowledge_score = len(desc_words & self.knowledge_keywords)
        skill_score = len(desc_words & self.skill_keywords)
        pattern_score = len(desc_words & self.pattern_keywords)

        scores = [
            (tool_score, GapType.TOOL),
            (knowledge_score, GapType.KNOWLEDGE),
            (skill_score, GapType.SKILL),
            (pattern_score, GapType.PATTERN),
        ]

        scores.sort(reverse=True)

        if scores[0][0] > 0:
            return scores[0][1]

        # Default: integration gap if unclear
        return GapType.INTEGRATION

    def determine_severity(
        self,
        gap_type: GapType,
        failure_count: int,
        affected_tasks: List[str],
    ) -> GapSeverity:
        """Determine gap severity"""
        # Critical if many failures or affects many tasks
        if failure_count > 10 or len(affected_tasks) > 5:
            return GapSeverity.CRITICAL

        # High if moderately frequent
        if failure_count > 5 or len(affected_tasks) > 2:
            return GapSeverity.HIGH

        # Medium if occasional
        if failure_count > 2:
            return GapSeverity.MEDIUM

        # Low otherwise
        return GapSeverity.LOW


class PriorityScorer:
    """Score gap priority for remediation"""

    def __init__(self):
        # Scoring weights
        self.weights = {
            "severity": 0.4,
            "frequency": 0.3,
            "impact": 0.2,
            "recency": 0.1,
        }

        logger.info("Priority Scorer initialized")

    def score_gap(self, gap: CapabilityGap) -> float:
        """Calculate priority score for gap"""
        # Severity score (0-1)
        severity_map = {
            GapSeverity.CRITICAL: 1.0,
            GapSeverity.HIGH: 0.75,
            GapSeverity.MEDIUM: 0.5,
            GapSeverity.LOW: 0.25,
        }
        severity_score = severity_map[gap.severity]

        # Frequency score (0-1, log scale)
        import math
        frequency_score = min(1.0, math.log(gap.failure_count + 1) / math.log(20))

        # Impact score (0-1, based on affected tasks)
        impact_score = min(1.0, len(gap.affected_tasks) / 10.0)

        # Recency score (0-1, exponential decay)
        hours_old = (datetime.now() - gap.detected_at).total_seconds() / 3600
        recency_score = math.exp(-hours_old / 24.0)  # Half-life of 1 day

        # Weighted sum
        priority = (
            severity_score * self.weights["severity"] +
            frequency_score * self.weights["frequency"] +
            impact_score * self.weights["impact"] +
            recency_score * self.weights["recency"]
        )

        # Update gap scores
        gap.priority_score = priority
        gap.frequency_score = frequency_score
        gap.impact_score = impact_score

        return priority


class GapDetector:
    """Main gap detection system"""

    def __init__(self):
        self.analyzer = FailurePatternAnalyzer()
        self.classifier = GapClassifier()
        self.scorer = PriorityScorer()

        self.detected_gaps: Dict[str, CapabilityGap] = {}
        self.gap_history: deque = deque(maxlen=5000)

        logger.info("Gap Detector initialized")

    def detect_from_failure(
        self,
        error_text: str,
        task: str,
        context: Optional[Dict] = None,
    ) -> List[CapabilityGap]:
        """Detect gaps from failure"""
        # Analyze failure patterns
        gaps_found = self.analyzer.analyze_failure(error_text, task)

        detected_gaps = []

        for gap_type, description in gaps_found:
            # Generate gap ID
            gap_id = self._generate_gap_id(gap_type, description)

            # Check if gap already exists
            if gap_id in self.detected_gaps:
                gap = self.detected_gaps[gap_id]
                gap.failure_count += 1
                if task not in gap.affected_tasks:
                    gap.affected_tasks.append(task)
                gap.failure_patterns.append(error_text[:200])
            else:
                # Create new gap
                gap = CapabilityGap(
                    gap_id=gap_id,
                    gap_type=gap_type,
                    severity=GapSeverity.MEDIUM,  # Will be updated
                    description=description,
                    affected_tasks=[task],
                    failure_patterns=[error_text[:200]],
                    context=context or {},
                )

                # Classify and score
                gap.gap_type = self.classifier.classify(description, context)
                gap.severity = self.classifier.determine_severity(
                    gap.gap_type,
                    gap.failure_count,
                    gap.affected_tasks,
                )

                self.detected_gaps[gap_id] = gap

            # Update priority score
            self.scorer.score_gap(gap)

            # Add to history
            self.gap_history.append({
                "timestamp": datetime.now(),
                "gap_id": gap_id,
                "task": task,
                "gap_type": gap.gap_type.value,
            })

            detected_gaps.append(gap)

            logger.info(
                f"Gap detected: {gap.gap_type.value} - {description} "
                f"(priority={gap.priority_score:.2f})"
            )

        return detected_gaps

    def detect_from_feedback(
        self,
        feedback: str,
        task: str,
        context: Optional[Dict] = None,
    ) -> Optional[CapabilityGap]:
        """Detect gap from user feedback"""
        # Simple feedback analysis
        feedback_lower = feedback.lower()

        # Look for gap indicators
        gap_indicators = {
            "missing": GapType.TOOL,
            "don't know": GapType.KNOWLEDGE,
            "can't": GapType.SKILL,
            "unable": GapType.SKILL,
            "lacking": GapType.KNOWLEDGE,
        }

        for indicator, gap_type in gap_indicators.items():
            if indicator in feedback_lower:
                description = f"User reported: {feedback}"
                gap_id = self._generate_gap_id(gap_type, description)

                if gap_id in self.detected_gaps:
                    gap = self.detected_gaps[gap_id]
                    gap.user_feedback.append(feedback)
                    gap.failure_count += 1
                else:
                    gap = CapabilityGap(
                        gap_id=gap_id,
                        gap_type=gap_type,
                        severity=GapSeverity.MEDIUM,
                        description=description,
                        affected_tasks=[task],
                        user_feedback=[feedback],
                        context=context or {},
                    )

                    gap.severity = self.classifier.determine_severity(
                        gap.gap_type,
                        gap.failure_count,
                        gap.affected_tasks,
                    )

                    self.detected_gaps[gap_id] = gap

                self.scorer.score_gap(gap)

                logger.info(f"Gap detected from feedback: {gap.gap_type.value} - {description}")

                return gap

        return None

    def get_top_gaps(self, limit: int = 10) -> List[CapabilityGap]:
        """Get top priority gaps"""
        gaps = list(self.detected_gaps.values())
        gaps.sort(key=lambda g: g.priority_score, reverse=True)
        return gaps[:limit]

    def get_gaps_by_type(self, gap_type: GapType) -> List[CapabilityGap]:
        """Get all gaps of specific type"""
        return [g for g in self.detected_gaps.values() if g.gap_type == gap_type]

    def get_critical_gaps(self) -> List[CapabilityGap]:
        """Get all critical severity gaps"""
        return [g for g in self.detected_gaps.values() if g.severity == GapSeverity.CRITICAL]

    def _generate_gap_id(self, gap_type: GapType, description: str) -> str:
        """Generate unique gap ID"""
        content = f"{gap_type.value}:{description}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


async def main():
    """Test gap detection system"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Automated Capability Gap Detection Test")
    logger.info("=" * 60)

    # Initialize detector
    detector = GapDetector()

    # Test 1: Tool gap detection
    logger.info("\n1. Tool Gap Detection:")

    detector.detect_from_failure(
        "command not found: podman",
        "container_deployment",
        {"system": "nixos"},
    )

    detector.detect_from_failure(
        "ModuleNotFoundError: No module named 'tensorflow'",
        "ml_training",
    )

    # Test 2: Knowledge gap detection
    logger.info("\n2. Knowledge Gap Detection:")

    detector.detect_from_failure(
        "I don't know how to configure AppArmor profiles",
        "security_hardening",
    )

    # Test 3: User feedback gap detection
    logger.info("\n3. User Feedback Gap Detection:")

    detector.detect_from_feedback(
        "System is missing documentation for the deployment workflow",
        "deployment",
    )

    # Test 4: Get top priority gaps
    logger.info("\n4. Top Priority Gaps:")

    top_gaps = detector.get_top_gaps(limit=5)

    for gap in top_gaps:
        logger.info(f"\nGap ID: {gap.gap_id}")
        logger.info(f"  Type: {gap.gap_type.value}")
        logger.info(f"  Severity: {gap.severity.name}")
        logger.info(f"  Description: {gap.description}")
        logger.info(f"  Priority Score: {gap.priority_score:.2f}")
        logger.info(f"  Failure Count: {gap.failure_count}")
        logger.info(f"  Affected Tasks: {len(gap.affected_tasks)}")

    # Test 5: Get gaps by type
    logger.info("\n5. Tool Gaps:")

    tool_gaps = detector.get_gaps_by_type(GapType.TOOL)
    logger.info(f"  Found {len(tool_gaps)} tool gaps")

    for gap in tool_gaps:
        logger.info(f"    - {gap.description}")


if __name__ == "__main__":
    asyncio.run(main())
