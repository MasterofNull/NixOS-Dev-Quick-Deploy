#!/usr/bin/env python3
"""
Phase 4.2: Pattern Extraction Engine
Identifies patterns from query/response interactions for learning.

Features:
- Query pattern identification
- Response pattern clustering
- Success pattern recognition
- Failure pattern detection
- Trend analysis
- Pattern frequency tracking
"""

import json
import logging
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum

import structlog

logger = structlog.get_logger()


class PatternType(Enum):
    """Type of detected pattern"""
    COMMON_QUERY = "common_query"
    SUCCESSFUL_RESOLUTION = "successful_resolution"
    RECURRING_ERROR = "recurring_error"
    AGENT_PERFORMANCE = "agent_performance"
    TIME_BASED = "time_based"
    SEMANTIC_CLUSTER = "semantic_cluster"


class Pattern:
    """Represents an extracted pattern"""

    def __init__(
        self,
        pattern_id: str,
        pattern_type: PatternType,
        description: str,
        frequency: int = 1,
        associated_agents: Optional[List[str]] = None,
        success_rate: float = 0.5,
        examples: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.pattern_id = pattern_id
        self.pattern_type = pattern_type
        self.description = description
        self.frequency = frequency
        self.associated_agents = associated_agents or []
        self.success_rate = success_rate
        self.examples = examples or []
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.confidence = 0.0  # Will be computed

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "description": self.description,
            "frequency": self.frequency,
            "associated_agents": self.associated_agents,
            "success_rate": round(self.success_rate, 3),
            "confidence": round(self.confidence, 3),
            "example_count": len(self.examples),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class PatternExtractor:
    """
    Extracts patterns from interaction history for learning.

    Usage:
        extractor = PatternExtractor()
        patterns = await extractor.extract_patterns(interactions)
        trends = await extractor.analyze_trends(interactions)
    """

    def __init__(self, data_root: Optional[str] = None):
        """Initialize pattern extractor"""
        self.data_root = Path(
            os.path.expanduser(
                data_root or os.getenv("PATTERN_EXTRACTION_DATA_ROOT")
                or os.getenv("DATA_DIR")
                or "~/.local/share/nixos-ai-stack/patterns"
            )
        )
        self.data_root.mkdir(parents=True, exist_ok=True)

        # Pattern storage
        self.patterns: Dict[str, Pattern] = {}
        self.pattern_counter: Counter = Counter()
        self.pattern_occurrences: Dict[str, List[Any]] = defaultdict(list)

        # Configuration
        self.min_frequency_threshold = 3
        self.min_confidence_threshold = 0.6

        logger.info("pattern_extractor_initialized", root=str(self.data_root))

    async def extract_common_query_patterns(
        self, interactions: List[Dict[str, Any]]
    ) -> List[Pattern]:
        """Identify common query patterns from interactions"""
        patterns: List[Pattern] = []

        if not interactions:
            return patterns

        try:
            # Tokenize queries for pattern extraction
            query_tokens: Dict[str, int] = Counter()
            query_phrases: Dict[str, int] = Counter()

            for interaction in interactions:
                query = interaction.get("query", "").lower()
                if not query:
                    continue

                # Extract tokens
                tokens = query.split()
                for token in tokens:
                    if len(token) > 3:  # Skip short tokens
                        query_tokens[token] += 1

                # Extract bigrams and trigrams
                words = query.split()
                for i in range(len(words) - 1):
                    phrase = " ".join(words[i:i+2])
                    query_phrases[phrase] += 1

            # Create patterns from frequent tokens/phrases
            for phrase, count in query_phrases.most_common(20):
                if count >= self.min_frequency_threshold:
                    pattern_id = f"query_pattern_{hash(phrase) % (10**8)}"

                    # Find associated agents and success rates
                    related_interactions = [
                        i for i in interactions
                        if phrase.lower() in i.get("query", "").lower()
                    ]

                    agents = list(set(i.get("agent") for i in related_interactions))
                    successes = sum(
                        1 for i in related_interactions
                        if i.get("status") == "success"
                    )
                    success_rate = successes / len(related_interactions) if related_interactions else 0.0

                    pattern = Pattern(
                        pattern_id=pattern_id,
                        pattern_type=PatternType.COMMON_QUERY,
                        description=f"Common query phrase: '{phrase}'",
                        frequency=count,
                        associated_agents=agents,
                        success_rate=success_rate,
                        examples=[
                            {"query": i.get("query"), "agent": i.get("agent")}
                            for i in related_interactions[:3]
                        ],
                    )
                    pattern.confidence = min(1.0, count / 20)
                    patterns.append(pattern)

            logger.info("common_query_patterns_extracted", count=len(patterns))
            return patterns

        except Exception as e:
            logger.error("common_query_pattern_extraction_failed", error=str(e))
            return []

    async def extract_success_patterns(
        self, interactions: List[Dict[str, Any]]
    ) -> List[Pattern]:
        """Identify patterns in successful resolutions"""
        patterns: List[Pattern] = []

        if not interactions:
            return patterns

        try:
            # Filter successful interactions
            successful = [
                i for i in interactions
                if i.get("status") == "success"
            ]

            if not successful:
                return patterns

            # Analyze agent performance on specific query types
            agent_type_success: Dict[Tuple[str, str], Tuple[int, int]] = defaultdict(lambda: (0, 0))

            for interaction in successful:
                agent = interaction.get("agent", "unknown")
                query_type = interaction.get("query_type", "unknown")
                execution_time = interaction.get("execution_time_ms", 0)

                success_count, total_count = agent_type_success[(agent, query_type)]
                agent_type_success[(agent, query_type)] = (success_count + 1, total_count + 1)

            # Create patterns for high-performing combinations
            for (agent, query_type), (successes, total) in agent_type_success.items():
                if total >= self.min_frequency_threshold:
                    success_rate = successes / total
                    if success_rate >= 0.8:  # 80%+ success
                        pattern_id = f"success_pattern_{agent}_{query_type}"
                        pattern = Pattern(
                            pattern_id=pattern_id,
                            pattern_type=PatternType.SUCCESSFUL_RESOLUTION,
                            description=f"Agent {agent} excels at {query_type} queries (80%+ success)",
                            frequency=total,
                            associated_agents=[agent],
                            success_rate=success_rate,
                        )
                        pattern.confidence = min(1.0, success_rate)
                        patterns.append(pattern)

            logger.info("success_patterns_extracted", count=len(patterns))
            return patterns

        except Exception as e:
            logger.error("success_pattern_extraction_failed", error=str(e))
            return []

    async def extract_failure_patterns(
        self, interactions: List[Dict[str, Any]]
    ) -> List[Pattern]:
        """Identify recurring failure patterns"""
        patterns: List[Pattern] = []

        if not interactions:
            return patterns

        try:
            # Filter failed interactions
            failed = [
                i for i in interactions
                if i.get("status") == "failed"
            ]

            if not failed:
                return patterns

            # Extract error keywords and patterns
            error_keywords: Counter = Counter()
            error_agent_patterns: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)

            for interaction in failed:
                response = interaction.get("response", "").lower()
                agent = interaction.get("agent", "unknown")
                query_type = interaction.get("query_type", "unknown")

                # Extract error keywords
                keywords = [
                    "error", "failed", "timeout", "connection", "permission",
                    "invalid", "not found", "unauthorized", "conflict"
                ]
                for keyword in keywords:
                    if keyword in response:
                        error_keywords[keyword] += 1
                        error_agent_patterns[(agent, keyword)].append({
                            "query": interaction.get("query", ""),
                            "response": interaction.get("response", "")[:200],
                        })

            # Create patterns from frequent error keywords
            for keyword, count in error_keywords.most_common(10):
                if count >= self.min_frequency_threshold:
                    pattern_id = f"error_pattern_{keyword}"
                    examples = []
                    related_agents = set()

                    for (agent, error_keyword), error_examples in error_agent_patterns.items():
                        if error_keyword == keyword:
                            related_agents.add(agent)
                            examples.extend(error_examples[:2])

                    pattern = Pattern(
                        pattern_id=pattern_id,
                        pattern_type=PatternType.RECURRING_ERROR,
                        description=f"Recurring error pattern: '{keyword}' appears in {count} failures",
                        frequency=count,
                        associated_agents=list(related_agents),
                        success_rate=0.0,
                        examples=examples,
                    )
                    pattern.confidence = min(1.0, count / 20)
                    patterns.append(pattern)

            logger.info("failure_patterns_extracted", count=len(patterns))
            return patterns

        except Exception as e:
            logger.error("failure_pattern_extraction_failed", error=str(e))
            return []

    async def extract_agent_performance_patterns(
        self, interactions: List[Dict[str, Any]]
    ) -> List[Pattern]:
        """Identify agent performance patterns"""
        patterns: List[Pattern] = []

        if not interactions:
            return patterns

        try:
            agent_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
                "total": 0,
                "successful": 0,
                "total_time": 0,
                "query_types": Counter(),
            })

            for interaction in interactions:
                agent = interaction.get("agent", "unknown")
                is_success = interaction.get("status") == "success"
                exec_time = interaction.get("execution_time_ms", 0)
                query_type = interaction.get("query_type", "unknown")

                stats = agent_stats[agent]
                stats["total"] += 1
                if is_success:
                    stats["successful"] += 1
                stats["total_time"] += exec_time
                stats["query_types"][query_type] += 1

            # Create patterns for agent performance
            for agent, stats in agent_stats.items():
                if stats["total"] >= self.min_frequency_threshold:
                    success_rate = stats["successful"] / stats["total"]
                    avg_time = stats["total_time"] / stats["total"]

                    pattern_id = f"agent_perf_{agent}"
                    pattern = Pattern(
                        pattern_id=pattern_id,
                        pattern_type=PatternType.AGENT_PERFORMANCE,
                        description=f"Agent {agent}: {success_rate*100:.1f}% success, {avg_time:.0f}ms avg",
                        frequency=stats["total"],
                        associated_agents=[agent],
                        success_rate=success_rate,
                        metadata={
                            "avg_execution_time_ms": int(avg_time),
                            "primary_query_types": dict(stats["query_types"].most_common(3)),
                        }
                    )
                    pattern.confidence = min(1.0, stats["total"] / 100)
                    patterns.append(pattern)

            logger.info("agent_performance_patterns_extracted", count=len(patterns))
            return patterns

        except Exception as e:
            logger.error("agent_performance_extraction_failed", error=str(e))
            return []

    async def analyze_trends(
        self, interactions: List[Dict[str, Any]], days: int = 7
    ) -> Dict[str, Any]:
        """Analyze temporal trends in interactions"""
        try:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(days=days)

            recent_interactions = [
                i for i in interactions
                if datetime.fromisoformat(i.get("timestamp", "")).replace(tzinfo=timezone.utc) > cutoff
            ]

            if not recent_interactions:
                return {"error": "no recent interactions"}

            # Analyze trends
            query_type_trend: Dict[str, int] = Counter()
            success_trend: List[int] = []
            execution_time_trend: List[float] = []

            for interaction in recent_interactions:
                query_type_trend[interaction.get("query_type")] += 1
                success_trend.append(1 if interaction.get("status") == "success" else 0)
                execution_time_trend.append(interaction.get("execution_time_ms", 0))

            # Calculate success rate trend (moving average)
            success_rate = sum(success_trend) / len(success_trend) if success_trend else 0.0
            avg_execution_time = sum(execution_time_trend) / len(execution_time_trend) if execution_time_trend else 0

            return {
                "period_days": days,
                "interaction_count": len(recent_interactions),
                "success_rate": round(success_rate, 3),
                "avg_execution_time_ms": int(avg_execution_time),
                "query_type_distribution": dict(query_type_trend.most_common(10)),
                "trending_up": success_rate > 0.7,
                "performance_status": "improving" if success_rate > 0.8 else "stable" if success_rate > 0.6 else "needs_improvement",
            }
        except Exception as e:
            logger.error("trend_analysis_failed", error=str(e))
            return {"error": str(e)}

    async def extract_all_patterns(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, List[Pattern]]:
        """Extract all pattern types from interactions"""
        try:
            results = {
                "common_queries": await self.extract_common_query_patterns(interactions),
                "success_patterns": await self.extract_success_patterns(interactions),
                "failure_patterns": await self.extract_failure_patterns(interactions),
                "agent_performance": await self.extract_agent_performance_patterns(interactions),
            }

            # Store patterns
            for pattern_list in results.values():
                for pattern in pattern_list:
                    self.patterns[pattern.pattern_id] = pattern

            total_patterns = sum(len(p) for p in results.values())
            logger.info("all_patterns_extracted", count=total_patterns)

            return results
        except Exception as e:
            logger.error("pattern_extraction_failed", error=str(e))
            return {
                "common_queries": [],
                "success_patterns": [],
                "failure_patterns": [],
                "agent_performance": [],
            }

    async def get_top_patterns(
        self, pattern_type: Optional[PatternType] = None, limit: int = 10
    ) -> List[Pattern]:
        """Get top patterns by confidence and frequency"""
        try:
            patterns = list(self.patterns.values())

            if pattern_type:
                patterns = [p for p in patterns if p.pattern_type == pattern_type]

            # Sort by confidence and frequency
            patterns.sort(
                key=lambda p: (p.confidence * 0.6 + (p.frequency / 100) * 0.4),
                reverse=True
            )

            return patterns[:limit]
        except Exception as e:
            logger.error("get_top_patterns_failed", error=str(e))
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get pattern extraction statistics"""
        try:
            by_type: Dict[str, int] = Counter()
            for pattern in self.patterns.values():
                by_type[pattern.pattern_type.value] += 1

            high_confidence = sum(
                1 for p in self.patterns.values()
                if p.confidence >= self.min_confidence_threshold
            )

            return {
                "total_patterns": len(self.patterns),
                "by_type": dict(by_type),
                "high_confidence_patterns": high_confidence,
                "min_frequency_threshold": self.min_frequency_threshold,
                "min_confidence_threshold": self.min_confidence_threshold,
            }
        except Exception as e:
            logger.error("statistics_computation_failed", error=str(e))
            return {}
