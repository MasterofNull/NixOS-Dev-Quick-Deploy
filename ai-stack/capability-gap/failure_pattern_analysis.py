#!/usr/bin/env python3
"""
Failure Pattern Analysis

Advanced failure pattern analysis with clustering, automatic discovery,
and user feedback integration for capability gap detection.
Part of Phase 9 Batch 9.1: Gap Detection Automation

Key Features:
- Failure pattern clustering and discovery
- Temporal pattern analysis (recurring failures)
- User feedback integration and sentiment analysis
- Automatic pattern generalization
- Root cause inference
- Gap classification from patterns
- Priority scoring with multiple factors

Reference: Anomaly detection, log analysis patterns
"""

import asyncio
import hashlib
import json
import logging
import math
import os
import re
import statistics
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Runtime writable state
FAILURE_ANALYSIS_STATE = Path(os.getenv(
    "FAILURE_ANALYSIS_STATE",
    "/var/lib/ai-stack/hybrid/failure-analysis"
))


class FailureCategory(Enum):
    """Categories of failures"""
    EXECUTION = "execution"  # Runtime errors
    RESOURCE = "resource"  # Missing resources/dependencies
    PERMISSION = "permission"  # Access denied
    VALIDATION = "validation"  # Input/output validation
    TIMEOUT = "timeout"  # Operation timeouts
    CONFIGURATION = "configuration"  # Config issues
    NETWORK = "network"  # Network/API failures
    LOGIC = "logic"  # Incorrect logic/behavior
    UNKNOWN = "unknown"


class PatternStatus(Enum):
    """Pattern lifecycle status"""
    ACTIVE = "active"  # Currently occurring
    RESOLVED = "resolved"  # Fixed
    RECURRING = "recurring"  # Comes back after resolution
    DORMANT = "dormant"  # No recent occurrences


class FeedbackSentiment(Enum):
    """User feedback sentiment"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    CONFUSED = "confused"


@dataclass
class FailureInstance:
    """A single failure instance"""
    id: str
    timestamp: datetime
    error_message: str
    error_type: str
    stack_trace: Optional[str]
    task_context: str
    category: FailureCategory
    metadata: Dict = field(default_factory=dict)


@dataclass
class FailurePattern:
    """A detected failure pattern"""
    pattern_id: str
    name: str
    description: str
    category: FailureCategory
    regex_pattern: str
    instances: List[str]  # Instance IDs
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int
    status: PatternStatus
    severity_score: float  # 0-1
    frequency_score: float  # 0-1
    impact_score: float  # 0-1
    root_causes: List[str] = field(default_factory=list)
    suggested_fixes: List[str] = field(default_factory=list)
    related_patterns: List[str] = field(default_factory=list)
    user_feedback: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class UserFeedback:
    """User feedback on system behavior"""
    feedback_id: str
    timestamp: datetime
    feedback_text: str
    sentiment: FeedbackSentiment
    task_context: Optional[str]
    related_failures: List[str]  # Failure IDs
    extracted_issues: List[str]
    metadata: Dict = field(default_factory=dict)


@dataclass
class GapInference:
    """Inferred capability gap from failure patterns"""
    inference_id: str
    gap_type: str  # tool, knowledge, skill, pattern
    description: str
    confidence: float  # 0-1
    supporting_patterns: List[str]
    supporting_feedback: List[str]
    priority_score: float
    suggested_remediations: List[str]


class FailureCategorizer:
    """Categorize failures by type"""

    def __init__(self):
        self.category_patterns = {
            FailureCategory.EXECUTION: [
                r"(RuntimeError|Exception|Error):",
                r"Traceback \(most recent call last\)",
                r"crashed|aborted|terminated",
            ],
            FailureCategory.RESOURCE: [
                r"No such file or directory",
                r"ModuleNotFoundError",
                r"command not found",
                r"not installed",
                r"missing (dependency|module|package)",
            ],
            FailureCategory.PERMISSION: [
                r"Permission denied",
                r"Access denied",
                r"unauthorized",
                r"forbidden",
                r"EACCES",
            ],
            FailureCategory.VALIDATION: [
                r"Invalid (input|output|format|type)",
                r"Validation failed",
                r"TypeError",
                r"ValueError",
                r"schema (error|mismatch)",
            ],
            FailureCategory.TIMEOUT: [
                r"timeout|timed out",
                r"deadline exceeded",
                r"connection (timeout|timed out)",
            ],
            FailureCategory.CONFIGURATION: [
                r"config(uration)? (error|invalid|missing)",
                r"environment variable .+ not set",
                r"setting .+ not found",
            ],
            FailureCategory.NETWORK: [
                r"connection (refused|reset|failed)",
                r"network (error|unreachable)",
                r"DNS (error|lookup failed)",
                r"HTTP (4\d\d|5\d\d)",
            ],
            FailureCategory.LOGIC: [
                r"AssertionError",
                r"unexpected (result|behavior|output)",
                r"incorrect (output|result)",
            ],
        }

        logger.info("Failure Categorizer initialized")

    def categorize(self, error_message: str, error_type: str = "") -> FailureCategory:
        """Categorize a failure"""
        combined = f"{error_type} {error_message}".lower()

        scores = {}
        for category, patterns in self.category_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    score += 1
            scores[category] = score

        # Return category with highest score
        if max(scores.values()) > 0:
            return max(scores.items(), key=lambda x: x[1])[0]

        return FailureCategory.UNKNOWN


class PatternDiscovery:
    """Automatically discover failure patterns"""

    def __init__(self, min_occurrences: int = 3):
        self.min_occurrences = min_occurrences
        self.token_patterns: Dict[str, List[str]] = defaultdict(list)
        logger.info("Pattern Discovery initialized")

    def tokenize_error(self, error_message: str) -> List[str]:
        """Tokenize error message for pattern matching"""
        # Remove variable parts (numbers, paths, UUIDs)
        normalized = re.sub(r'\b[0-9a-fA-F]{8,}\b', '<ID>', error_message)
        normalized = re.sub(r'\b\d+\b', '<NUM>', normalized)
        normalized = re.sub(r'/[\w/.-]+', '<PATH>', normalized)
        normalized = re.sub(r'"[^"]*"', '<STR>', normalized)
        normalized = re.sub(r"'[^']*'", '<STR>', normalized)

        # Tokenize
        tokens = re.findall(r'\w+|<\w+>', normalized.lower())

        return tokens

    def find_common_patterns(
        self,
        failures: List[FailureInstance],
    ) -> List[Dict[str, Any]]:
        """Find common patterns across failures"""
        # Group by category
        by_category = defaultdict(list)
        for f in failures:
            by_category[f.category].append(f)

        patterns = []

        for category, category_failures in by_category.items():
            if len(category_failures) < self.min_occurrences:
                continue

            # Tokenize all errors
            all_tokens = [
                self.tokenize_error(f.error_message)
                for f in category_failures
            ]

            # Find common subsequences
            common = self._find_common_subsequences(all_tokens)

            for subseq, count in common.items():
                if count >= self.min_occurrences:
                    # Create regex pattern
                    regex = self._subsequence_to_regex(subseq)

                    patterns.append({
                        "subsequence": subseq,
                        "regex": regex,
                        "occurrences": count,
                        "category": category,
                        "example_failures": [
                            f.id for f in category_failures[:3]
                        ],
                    })

        return patterns

    def _find_common_subsequences(
        self,
        token_lists: List[List[str]],
        min_length: int = 3,
    ) -> Dict[str, int]:
        """Find common token subsequences"""
        subsequence_counts = Counter()

        for tokens in token_lists:
            # Generate all subsequences of minimum length
            seen_in_this = set()

            for start in range(len(tokens)):
                for end in range(start + min_length, min(start + 10, len(tokens) + 1)):
                    subseq = tuple(tokens[start:end])
                    if subseq not in seen_in_this:
                        subsequence_counts[subseq] += 1
                        seen_in_this.add(subseq)

        # Convert to strings
        result = {}
        for subseq, count in subsequence_counts.most_common(50):
            result[' '.join(subseq)] = count

        return result

    def _subsequence_to_regex(self, subsequence: str) -> str:
        """Convert token subsequence to regex pattern"""
        tokens = subsequence.split()
        regex_parts = []

        for token in tokens:
            if token == '<id>':
                regex_parts.append(r'[0-9a-fA-F]{8,}')
            elif token == '<num>':
                regex_parts.append(r'\d+')
            elif token == '<path>':
                regex_parts.append(r'/[\w/.-]+')
            elif token == '<str>':
                regex_parts.append(r'["\'][^"\']*["\']')
            else:
                regex_parts.append(re.escape(token))

        return r'\s*'.join(regex_parts)


class TemporalAnalyzer:
    """Analyze temporal patterns in failures"""

    def __init__(self, window_hours: int = 24):
        self.window_hours = window_hours
        logger.info("Temporal Analyzer initialized")

    def analyze_frequency(
        self,
        failures: List[FailureInstance],
    ) -> Dict[str, Any]:
        """Analyze failure frequency over time"""
        if not failures:
            return {"total": 0, "trend": "unknown"}

        now = datetime.now(timezone.utc)

        # Count by hour buckets
        hourly_counts = defaultdict(int)
        for f in failures:
            # Handle both naive and aware datetimes
            if f.timestamp.tzinfo is None:
                ts = f.timestamp.replace(tzinfo=timezone.utc)
            else:
                ts = f.timestamp
            hours_ago = int((now - ts).total_seconds() / 3600)
            hourly_counts[hours_ago] += 1

        # Calculate trend
        recent = sum(hourly_counts.get(h, 0) for h in range(0, 6))  # Last 6 hours
        older = sum(hourly_counts.get(h, 0) for h in range(6, 24))  # 6-24 hours ago

        if recent > older * 1.5:
            trend = "increasing"
        elif recent < older * 0.5:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "total": len(failures),
            "last_hour": hourly_counts.get(0, 0),
            "last_6_hours": recent,
            "last_24_hours": sum(hourly_counts.get(h, 0) for h in range(24)),
            "trend": trend,
            "hourly_distribution": dict(hourly_counts),
        }

    def detect_bursts(
        self,
        failures: List[FailureInstance],
        burst_threshold: int = 5,
        window_minutes: int = 10,
    ) -> List[Dict[str, Any]]:
        """Detect failure bursts (many failures in short time)"""
        if not failures:
            return []

        sorted_failures = sorted(failures, key=lambda f: f.timestamp)
        bursts = []
        current_burst = []

        for failure in sorted_failures:
            if not current_burst:
                current_burst = [failure]
                continue

            # Check if within burst window
            time_diff = (failure.timestamp - current_burst[-1].timestamp).total_seconds()

            if time_diff <= window_minutes * 60:
                current_burst.append(failure)
            else:
                # End of burst
                if len(current_burst) >= burst_threshold:
                    bursts.append({
                        "start": current_burst[0].timestamp.isoformat(),
                        "end": current_burst[-1].timestamp.isoformat(),
                        "count": len(current_burst),
                        "duration_minutes": (
                            current_burst[-1].timestamp - current_burst[0].timestamp
                        ).total_seconds() / 60,
                        "failure_ids": [f.id for f in current_burst],
                    })
                current_burst = [failure]

        # Check last burst
        if len(current_burst) >= burst_threshold:
            bursts.append({
                "start": current_burst[0].timestamp.isoformat(),
                "end": current_burst[-1].timestamp.isoformat(),
                "count": len(current_burst),
                "duration_minutes": (
                    current_burst[-1].timestamp - current_burst[0].timestamp
                ).total_seconds() / 60,
                "failure_ids": [f.id for f in current_burst],
            })

        return bursts

    def detect_recurring(
        self,
        failures: List[FailureInstance],
        pattern_id: str,
        days_to_check: int = 7,
    ) -> bool:
        """Detect if a pattern is recurring (reappears after resolution)"""
        if len(failures) < 3:
            return False

        sorted_failures = sorted(failures, key=lambda f: f.timestamp)

        # Look for gaps > 24 hours followed by new failures
        for i in range(1, len(sorted_failures)):
            gap = (sorted_failures[i].timestamp - sorted_failures[i-1].timestamp)
            if gap > timedelta(hours=24):
                # Pattern recurred after a gap
                return True

        return False


class FeedbackAnalyzer:
    """Analyze user feedback for gap detection"""

    def __init__(self):
        self.sentiment_patterns = {
            FeedbackSentiment.FRUSTRATED: [
                r"frustrated|annoyed|irritated",
                r"keeps (failing|breaking|crashing)",
                r"doesn't work|broken|useless",
                r"waste of time",
            ],
            FeedbackSentiment.CONFUSED: [
                r"confused|unclear|don't understand",
                r"what (does|is) .+ (mean|do)",
                r"how (do|does|should) I",
                r"expected .+ but got",
            ],
            FeedbackSentiment.NEGATIVE: [
                r"wrong|incorrect|bad",
                r"failed|error|bug",
                r"not working|doesn't",
            ],
            FeedbackSentiment.POSITIVE: [
                r"works|working|fixed",
                r"thanks|thank you|great",
                r"perfect|excellent|good",
            ],
        }

        self.issue_patterns = [
            (r"can't (find|locate|access) (.+)", "Missing resource: {1}"),
            (r"doesn't (support|handle) (.+)", "Missing support for: {1}"),
            (r"need(s)? (.+) (but|to)", "Needs: {1}"),
            (r"should (be able to|support) (.+)", "Feature request: {1}"),
            (r"error (?:when|while) (.+)", "Error during: {0}"),
            (r"fails? (?:to|when) (.+)", "Failure: {0}"),
        ]

        logger.info("Feedback Analyzer initialized")

    def analyze_sentiment(self, feedback_text: str) -> FeedbackSentiment:
        """Analyze sentiment of feedback"""
        text_lower = feedback_text.lower()

        sentiment_scores = {}
        for sentiment, patterns in self.sentiment_patterns.items():
            score = sum(
                1 for pattern in patterns
                if re.search(pattern, text_lower)
            )
            sentiment_scores[sentiment] = score

        # Return highest scoring sentiment
        max_score = max(sentiment_scores.values())
        if max_score > 0:
            return max(
                sentiment_scores.items(),
                key=lambda x: x[1]
            )[0]

        return FeedbackSentiment.NEUTRAL

    def extract_issues(self, feedback_text: str) -> List[str]:
        """Extract specific issues from feedback"""
        issues = []
        text_lower = feedback_text.lower()

        for pattern, template in self.issue_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                if isinstance(match, tuple):
                    issue = template.format(*match)
                else:
                    issue = template.format(match)
                issues.append(issue)

        return issues

    def correlate_with_failures(
        self,
        feedback: UserFeedback,
        failures: List[FailureInstance],
        time_window_hours: int = 4,
    ) -> List[str]:
        """Find failures related to feedback"""
        if not feedback.timestamp:
            return []

        related = []
        window_start = feedback.timestamp - timedelta(hours=time_window_hours)
        window_end = feedback.timestamp + timedelta(hours=1)

        for failure in failures:
            if window_start <= failure.timestamp <= window_end:
                # Check for keyword overlap
                feedback_words = set(feedback.feedback_text.lower().split())
                error_words = set(failure.error_message.lower().split())

                if len(feedback_words & error_words) >= 2:
                    related.append(failure.id)

        return related


class GapInferrer:
    """Infer capability gaps from failure patterns"""

    GAP_TYPE_INDICATORS = {
        "tool": [
            "command not found", "not installed", "module not found",
            "package missing", "dependency missing",
        ],
        "knowledge": [
            "don't know how", "unclear how", "no documentation",
            "not familiar with", "need to understand",
        ],
        "skill": [
            "unable to implement", "failed to create", "couldn't build",
            "don't have experience", "need training",
        ],
        "pattern": [
            "no workflow for", "missing template", "need approach for",
            "no framework for", "need methodology",
        ],
    }

    def __init__(self):
        logger.info("Gap Inferrer initialized")

    def infer_gaps(
        self,
        patterns: List[FailurePattern],
        feedback: List[UserFeedback],
    ) -> List[GapInference]:
        """Infer capability gaps from patterns and feedback"""
        inferences = []

        # Group patterns by category
        pattern_groups = defaultdict(list)
        for p in patterns:
            pattern_groups[p.category].append(p)

        # Analyze each group for gaps
        for category, category_patterns in pattern_groups.items():
            gap_type = self._determine_gap_type(category_patterns)
            description = self._generate_gap_description(category_patterns)

            # Calculate confidence
            confidence = self._calculate_confidence(category_patterns, feedback)

            # Find supporting evidence
            supporting_patterns = [p.pattern_id for p in category_patterns]
            supporting_feedback = self._find_related_feedback(
                category_patterns, feedback
            )

            # Calculate priority
            priority = self._calculate_priority(category_patterns, feedback)

            # Suggest remediations
            remediations = self._suggest_remediations(gap_type, category_patterns)

            inference = GapInference(
                inference_id=hashlib.sha256(
                    f"{gap_type}_{description[:50]}".encode()
                ).hexdigest()[:12],
                gap_type=gap_type,
                description=description,
                confidence=confidence,
                supporting_patterns=supporting_patterns,
                supporting_feedback=supporting_feedback,
                priority_score=priority,
                suggested_remediations=remediations,
            )

            inferences.append(inference)

        return inferences

    def _determine_gap_type(self, patterns: List[FailurePattern]) -> str:
        """Determine gap type from patterns"""
        combined_text = ' '.join([
            p.description + ' ' + ' '.join(p.root_causes)
            for p in patterns
        ]).lower()

        type_scores = {}
        for gap_type, indicators in self.GAP_TYPE_INDICATORS.items():
            score = sum(
                1 for indicator in indicators
                if indicator in combined_text
            )
            type_scores[gap_type] = score

        if max(type_scores.values()) > 0:
            return max(type_scores.items(), key=lambda x: x[1])[0]

        # Infer from category
        category = patterns[0].category if patterns else FailureCategory.UNKNOWN

        category_gap_map = {
            FailureCategory.RESOURCE: "tool",
            FailureCategory.EXECUTION: "skill",
            FailureCategory.CONFIGURATION: "knowledge",
            FailureCategory.LOGIC: "pattern",
        }

        return category_gap_map.get(category, "knowledge")

    def _generate_gap_description(self, patterns: List[FailurePattern]) -> str:
        """Generate human-readable gap description"""
        if not patterns:
            return "Unknown capability gap"

        # Use most common pattern
        most_common = max(patterns, key=lambda p: p.occurrence_count)

        return f"Capability gap in {most_common.category.value}: {most_common.description}"

    def _calculate_confidence(
        self,
        patterns: List[FailurePattern],
        feedback: List[UserFeedback],
    ) -> float:
        """Calculate confidence in gap inference"""
        if not patterns:
            return 0.0

        # Base confidence on occurrence count and pattern count
        total_occurrences = sum(p.occurrence_count for p in patterns)
        pattern_count = len(patterns)

        occurrence_confidence = min(1.0, total_occurrences / 20)
        pattern_confidence = min(1.0, pattern_count / 5)

        # Boost if supported by feedback
        feedback_boost = 0.0
        if feedback:
            negative_feedback = sum(
                1 for f in feedback
                if f.sentiment in [FeedbackSentiment.FRUSTRATED, FeedbackSentiment.NEGATIVE]
            )
            feedback_boost = min(0.2, negative_feedback / 10)

        return min(1.0, occurrence_confidence * 0.5 + pattern_confidence * 0.3 + feedback_boost)

    def _find_related_feedback(
        self,
        patterns: List[FailurePattern],
        feedback: List[UserFeedback],
    ) -> List[str]:
        """Find feedback related to patterns"""
        related = []

        pattern_ids = set(p.pattern_id for p in patterns)

        for f in feedback:
            # Check if feedback mentions any failure from patterns
            for pattern in patterns:
                if any(fid in f.related_failures for fid in pattern.instances):
                    related.append(f.feedback_id)
                    break

        return related

    def _calculate_priority(
        self,
        patterns: List[FailurePattern],
        feedback: List[UserFeedback],
    ) -> float:
        """Calculate priority score for gap"""
        if not patterns:
            return 0.0

        # Average pattern severity
        avg_severity = statistics.mean(p.severity_score for p in patterns)

        # Frequency factor
        total_occurrences = sum(p.occurrence_count for p in patterns)
        frequency_factor = min(1.0, math.log(total_occurrences + 1) / math.log(50))

        # Recency factor
        most_recent = max(p.last_seen for p in patterns)
        if most_recent.tzinfo is None:
            most_recent = most_recent.replace(tzinfo=timezone.utc)
        hours_old = (datetime.now(timezone.utc) - most_recent).total_seconds() / 3600
        recency_factor = math.exp(-hours_old / 48)  # 2-day half-life

        # Feedback factor
        feedback_factor = 0.0
        frustrated = sum(
            1 for f in feedback
            if f.sentiment == FeedbackSentiment.FRUSTRATED
        )
        feedback_factor = min(0.2, frustrated / 10)

        return (
            avg_severity * 0.4 +
            frequency_factor * 0.3 +
            recency_factor * 0.2 +
            feedback_factor * 0.1
        )

    def _suggest_remediations(
        self,
        gap_type: str,
        patterns: List[FailurePattern],
    ) -> List[str]:
        """Suggest remediations for gap"""
        suggestions = []

        if gap_type == "tool":
            suggestions.append("Install missing tools or dependencies")
            suggestions.append("Add tool to system configuration")
            suggestions.append("Create wrapper script for missing functionality")

        elif gap_type == "knowledge":
            suggestions.append("Add documentation for the topic")
            suggestions.append("Create training examples for the skill")
            suggestions.append("Integrate external knowledge source")

        elif gap_type == "skill":
            suggestions.append("Create workflow template for the task")
            suggestions.append("Add step-by-step guidance")
            suggestions.append("Implement helper functions")

        elif gap_type == "pattern":
            suggestions.append("Extract reusable pattern from successful cases")
            suggestions.append("Create pattern library entry")
            suggestions.append("Document best practices")

        # Add pattern-specific suggestions
        for pattern in patterns[:3]:
            if pattern.suggested_fixes:
                suggestions.extend(pattern.suggested_fixes[:2])

        return list(set(suggestions))[:5]


class FailurePatternAnalyzer:
    """
    Main failure pattern analysis orchestrator.

    Combines categorization, pattern discovery, temporal analysis,
    and gap inference for comprehensive failure analysis.
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
    ):
        self.output_dir = output_dir or FAILURE_ANALYSIS_STATE
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.categorizer = FailureCategorizer()
        self.pattern_discovery = PatternDiscovery()
        self.temporal_analyzer = TemporalAnalyzer()
        self.feedback_analyzer = FeedbackAnalyzer()
        self.gap_inferrer = GapInferrer()

        # Storage
        self.failures: Dict[str, FailureInstance] = {}
        self.patterns: Dict[str, FailurePattern] = {}
        self.feedback: Dict[str, UserFeedback] = {}
        self.inferences: Dict[str, GapInference] = {}

        # Statistics
        self.stats = {
            "total_failures": 0,
            "total_patterns": 0,
            "total_feedback": 0,
            "gaps_inferred": 0,
        }

        logger.info(f"Failure Pattern Analyzer initialized: {self.output_dir}")

    def record_failure(
        self,
        error_message: str,
        error_type: str,
        task_context: str,
        stack_trace: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> FailureInstance:
        """Record a failure instance"""
        failure_id = hashlib.sha256(
            f"{error_message}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        category = self.categorizer.categorize(error_message, error_type)

        failure = FailureInstance(
            id=failure_id,
            timestamp=datetime.now(timezone.utc),
            error_message=error_message,
            error_type=error_type,
            stack_trace=stack_trace,
            task_context=task_context,
            category=category,
            metadata=metadata or {},
        )

        self.failures[failure_id] = failure
        self.stats["total_failures"] += 1

        # Try to match to existing patterns
        self._match_to_patterns(failure)

        logger.debug(f"Recorded failure {failure_id} ({category.value})")

        return failure

    def record_feedback(
        self,
        feedback_text: str,
        task_context: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> UserFeedback:
        """Record user feedback"""
        feedback_id = hashlib.sha256(
            f"{feedback_text}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        sentiment = self.feedback_analyzer.analyze_sentiment(feedback_text)
        issues = self.feedback_analyzer.extract_issues(feedback_text)

        # Find related failures
        related = self.feedback_analyzer.correlate_with_failures(
            UserFeedback(
                feedback_id=feedback_id,
                timestamp=datetime.now(timezone.utc),
                feedback_text=feedback_text,
                sentiment=sentiment,
                task_context=task_context,
                related_failures=[],
                extracted_issues=issues,
            ),
            list(self.failures.values()),
        )

        feedback = UserFeedback(
            feedback_id=feedback_id,
            timestamp=datetime.now(timezone.utc),
            feedback_text=feedback_text,
            sentiment=sentiment,
            task_context=task_context,
            related_failures=related,
            extracted_issues=issues,
            metadata=metadata or {},
        )

        self.feedback[feedback_id] = feedback
        self.stats["total_feedback"] += 1

        logger.debug(
            f"Recorded feedback {feedback_id} "
            f"(sentiment={sentiment.value}, issues={len(issues)})"
        )

        return feedback

    def _match_to_patterns(self, failure: FailureInstance):
        """Match failure to existing patterns"""
        for pattern in self.patterns.values():
            if re.search(pattern.regex_pattern, failure.error_message, re.IGNORECASE):
                pattern.instances.append(failure.id)
                pattern.occurrence_count += 1
                pattern.last_seen = failure.timestamp
                return

    def discover_patterns(self) -> List[FailurePattern]:
        """Discover patterns from recorded failures"""
        failures = list(self.failures.values())

        discovered = self.pattern_discovery.find_common_patterns(failures)

        new_patterns = []
        for disc in discovered:
            pattern_id = hashlib.sha256(
                disc["regex"].encode()
            ).hexdigest()[:12]

            if pattern_id in self.patterns:
                continue

            pattern = FailurePattern(
                pattern_id=pattern_id,
                name=f"Pattern_{len(self.patterns) + 1}",
                description=disc["subsequence"],
                category=disc["category"],
                regex_pattern=disc["regex"],
                instances=disc["example_failures"],
                first_seen=datetime.now(timezone.utc),
                last_seen=datetime.now(timezone.utc),
                occurrence_count=disc["occurrences"],
                status=PatternStatus.ACTIVE,
                severity_score=0.5,  # Default
                frequency_score=min(1.0, disc["occurrences"] / 10),
                impact_score=0.5,  # Default
            )

            self.patterns[pattern_id] = pattern
            new_patterns.append(pattern)

        self.stats["total_patterns"] = len(self.patterns)
        logger.info(f"Discovered {len(new_patterns)} new patterns")

        return new_patterns

    def infer_gaps(self) -> List[GapInference]:
        """Infer capability gaps from patterns and feedback"""
        patterns = list(self.patterns.values())
        feedback = list(self.feedback.values())

        inferences = self.gap_inferrer.infer_gaps(patterns, feedback)

        for inf in inferences:
            self.inferences[inf.inference_id] = inf

        self.stats["gaps_inferred"] = len(self.inferences)
        logger.info(f"Inferred {len(inferences)} capability gaps")

        return inferences

    def get_analysis_report(self) -> Dict[str, Any]:
        """Generate comprehensive analysis report"""
        failures = list(self.failures.values())

        # Temporal analysis
        frequency = self.temporal_analyzer.analyze_frequency(failures)
        bursts = self.temporal_analyzer.detect_bursts(failures)

        # Category breakdown
        category_counts = Counter(f.category.value for f in failures)

        # Top patterns
        top_patterns = sorted(
            self.patterns.values(),
            key=lambda p: p.occurrence_count,
            reverse=True,
        )[:10]

        # Top gaps
        top_gaps = sorted(
            self.inferences.values(),
            key=lambda g: g.priority_score,
            reverse=True,
        )[:5]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_failures": len(failures),
                "total_patterns": len(self.patterns),
                "total_feedback": len(self.feedback),
                "gaps_identified": len(self.inferences),
            },
            "frequency_analysis": frequency,
            "bursts": bursts,
            "category_breakdown": dict(category_counts),
            "top_patterns": [
                {
                    "id": p.pattern_id,
                    "name": p.name,
                    "category": p.category.value,
                    "occurrences": p.occurrence_count,
                    "severity": p.severity_score,
                }
                for p in top_patterns
            ],
            "top_gaps": [
                {
                    "id": g.inference_id,
                    "type": g.gap_type,
                    "description": g.description,
                    "confidence": g.confidence,
                    "priority": g.priority_score,
                    "remediations": g.suggested_remediations[:3],
                }
                for g in top_gaps
            ],
        }

    def save_state(self) -> Path:
        """Save analyzer state"""
        state_path = self.output_dir / "analyzer_state.json"

        state = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "stats": self.stats,
            "patterns": {
                pid: {
                    "name": p.name,
                    "category": p.category.value,
                    "occurrences": p.occurrence_count,
                    "status": p.status.value,
                }
                for pid, p in self.patterns.items()
            },
            "inferences": {
                iid: {
                    "type": i.gap_type,
                    "description": i.description,
                    "confidence": i.confidence,
                    "priority": i.priority_score,
                }
                for iid, i in self.inferences.items()
            },
        }

        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)

        logger.info(f"Saved state to {state_path}")
        return state_path

    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics"""
        return {
            **self.stats,
            "active_patterns": sum(
                1 for p in self.patterns.values()
                if p.status == PatternStatus.ACTIVE
            ),
            "high_priority_gaps": sum(
                1 for g in self.inferences.values()
                if g.priority_score > 0.7
            ),
        }


async def main():
    """Test failure pattern analysis"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Failure Pattern Analysis Test")
    logger.info("=" * 60)

    # Create analyzer
    analyzer = FailurePatternAnalyzer()

    # Simulate failures
    test_failures = [
        ("ModuleNotFoundError: No module named 'tensorflow'", "ImportError", "Training model"),
        ("ModuleNotFoundError: No module named 'torch'", "ImportError", "Building neural net"),
        ("command not found: nvidia-smi", "BashError", "Checking GPU status"),
        ("Permission denied: /etc/hosts", "OSError", "Editing hosts file"),
        ("Connection refused: localhost:5432", "NetworkError", "Connecting to database"),
        ("Connection refused: localhost:6379", "NetworkError", "Connecting to Redis"),
        ("TypeError: expected str, got int", "TypeError", "Processing input"),
        ("ValueError: invalid literal for int()", "ValueError", "Parsing user input"),
        ("TimeoutError: operation timed out after 30s", "TimeoutError", "API call"),
    ]

    for error_msg, error_type, task in test_failures:
        analyzer.record_failure(error_msg, error_type, task)

    # Simulate user feedback
    feedback_items = [
        "I'm frustrated that the GPU support keeps failing",
        "Confused about how to configure the database connection",
        "The module imports don't work, very annoying",
        "Can't access system files without permission",
    ]

    for fb in feedback_items:
        analyzer.record_feedback(fb)

    # Discover patterns
    logger.info("\n1. Pattern Discovery:")
    patterns = analyzer.discover_patterns()
    logger.info(f"  Discovered {len(patterns)} patterns")

    for pattern in patterns[:3]:
        logger.info(f"    - {pattern.name}: {pattern.description[:50]}...")

    # Infer gaps
    logger.info("\n2. Gap Inference:")
    gaps = analyzer.infer_gaps()
    logger.info(f"  Inferred {len(gaps)} capability gaps")

    for gap in gaps[:3]:
        logger.info(f"    - [{gap.gap_type}] {gap.description[:50]}...")
        logger.info(f"      Confidence: {gap.confidence:.2f}, Priority: {gap.priority_score:.2f}")

    # Generate report
    logger.info("\n3. Analysis Report:")
    report = analyzer.get_analysis_report()

    logger.info(f"  Total failures: {report['summary']['total_failures']}")
    logger.info(f"  Total patterns: {report['summary']['total_patterns']}")
    logger.info(f"  Gaps identified: {report['summary']['gaps_identified']}")
    logger.info(f"  Failure trend: {report['frequency_analysis']['trend']}")

    # Save state
    analyzer.save_state()

    # Show stats
    stats = analyzer.get_stats()
    logger.info(f"\n4. Final Stats:")
    logger.info(f"  Total failures: {stats['total_failures']}")
    logger.info(f"  Active patterns: {stats['active_patterns']}")
    logger.info(f"  High priority gaps: {stats['high_priority_gaps']}")


if __name__ == "__main__":
    asyncio.run(main())
