"""
pattern_integration.py — Pattern Integration into Hints/RAG

Loads extracted patterns from telemetry and integrates them into:
- Hint ranking system (boost frequently successful patterns)
- RAG retrieval (surface pattern-based knowledge)
- Quality monitoring (track pattern effectiveness)

Batch 6.2: Pattern Integration
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pattern Data Model
# ---------------------------------------------------------------------------

@dataclass
class ExtractedPattern:
    """A pattern extracted from telemetry."""
    id: str
    pattern_type: str  # "hint", "tool_sequence", "query_type"
    occurrences: int
    success_count: int
    quality_score: float  # 0.0-1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_seen: Optional[str] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.occurrences == 0:
            return 0.0
        return self.success_count / self.occurrences

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "pattern_type": self.pattern_type,
            "occurrences": self.occurrences,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 3),
            "quality_score": round(self.quality_score, 3),
            "metadata": self.metadata,
            "last_seen": self.last_seen,
        }


@dataclass
class PatternCache:
    """Cache for loaded patterns."""
    patterns: Dict[str, ExtractedPattern] = field(default_factory=dict)
    loaded_at: float = 0.0
    ttl_seconds: float = 3600.0  # 1 hour cache

    def is_fresh(self) -> bool:
        """Check if cache is still valid."""
        age = time.time() - self.loaded_at
        return age < self.ttl_seconds


# ---------------------------------------------------------------------------
# Pattern Loading
# ---------------------------------------------------------------------------

_pattern_cache = PatternCache()


def load_patterns_from_file(
    pattern_file: Path,
    min_quality: float = 0.7,
    min_occurrences: int = 3,
) -> List[ExtractedPattern]:
    """
    Load patterns from aq-patterns JSON output.

    Args:
        pattern_file: Path to pattern JSON file
        min_quality: Minimum quality score filter
        min_occurrences: Minimum occurrence count filter

    Returns:
        List of extracted patterns
    """
    if not pattern_file.exists():
        logger.debug(f"Pattern file not found: {pattern_file}")
        return []

    try:
        data = json.loads(pattern_file.read_text(encoding="utf-8"))
        patterns = []

        for item in data.get("patterns", []):
            if not isinstance(item, dict):
                continue

            pattern_id = str(item.get("id", "")).strip()
            if not pattern_id:
                continue

            occurrences = int(item.get("occurrences", 0))
            success_count = int(item.get("success_count", 0))
            quality_score = float(item.get("quality_score", 0.0))

            # Filter by quality and occurrence thresholds
            if quality_score < min_quality or occurrences < min_occurrences:
                continue

            pattern = ExtractedPattern(
                id=pattern_id,
                pattern_type=item.get("pattern_type", "hint"),
                occurrences=occurrences,
                success_count=success_count,
                quality_score=quality_score,
                metadata=item.get("metadata", {}),
                last_seen=item.get("last_seen"),
            )

            patterns.append(pattern)

        logger.info(f"Loaded {len(patterns)} patterns from {pattern_file}")
        return patterns

    except Exception as exc:
        logger.warning(f"Failed to load patterns from {pattern_file}: {exc}")
        return []


def load_patterns_cached(
    pattern_file: Optional[Path] = None,
    min_quality: float = 0.7,
    min_occurrences: int = 3,
    force_refresh: bool = False,
) -> Dict[str, ExtractedPattern]:
    """
    Load patterns with caching.

    Args:
        pattern_file: Path to pattern file (defaults to /var/lib/ai-stack/patterns.json)
        min_quality: Minimum quality score
        min_occurrences: Minimum occurrences
        force_refresh: Force cache refresh

    Returns:
        Dictionary of patterns by ID
    """
    global _pattern_cache

    # Use cache if fresh
    if not force_refresh and _pattern_cache.is_fresh():
        return _pattern_cache.patterns

    # Default pattern file location
    if pattern_file is None:
        pattern_file = Path("/var/lib/ai-stack/patterns.json")

    # Load patterns
    patterns_list = load_patterns_from_file(pattern_file, min_quality, min_occurrences)

    # Update cache
    _pattern_cache.patterns = {p.id: p for p in patterns_list}
    _pattern_cache.loaded_at = time.time()

    return _pattern_cache.patterns


def get_pattern_boost(pattern_id: str) -> float:
    """
    Get boost multiplier for a pattern based on its quality.

    Args:
        pattern_id: Pattern identifier

    Returns:
        Boost multiplier (1.0 = no boost, >1.0 = boost)
    """
    patterns = load_patterns_cached()
    pattern = patterns.get(pattern_id)

    if not pattern:
        return 1.0

    # Boost based on quality score
    # High quality (>0.9) = 1.4x boost
    # Medium quality (0.7-0.9) = 1.2x boost
    # Low quality (<0.7) = 1.0x (no boost)
    if pattern.quality_score >= 0.9:
        return 1.4
    elif pattern.quality_score >= 0.7:
        return 1.2
    else:
        return 1.0


def get_top_patterns(limit: int = 20) -> List[ExtractedPattern]:
    """
    Get top patterns by quality score.

    Args:
        limit: Maximum number of patterns to return

    Returns:
        List of top patterns
    """
    patterns = load_patterns_cached()
    sorted_patterns = sorted(
        patterns.values(),
        key=lambda p: (p.quality_score, p.occurrences),
        reverse=True
    )
    return sorted_patterns[:limit]


def get_pattern_stats() -> Dict[str, Any]:
    """
    Get pattern integration statistics.

    Returns:
        Statistics dictionary
    """
    patterns = load_patterns_cached()

    if not patterns:
        return {
            "total_patterns": 0,
            "active": False,
            "cache_age_seconds": 0,
        }

    total = len(patterns)
    high_quality = sum(1 for p in patterns.values() if p.quality_score >= 0.9)
    medium_quality = sum(1 for p in patterns.values() if 0.7 <= p.quality_score < 0.9)

    avg_quality = sum(p.quality_score for p in patterns.values()) / total if total > 0 else 0.0
    avg_success_rate = sum(p.success_rate for p in patterns.values()) / total if total > 0 else 0.0

    cache_age = time.time() - _pattern_cache.loaded_at

    return {
        "total_patterns": total,
        "high_quality_patterns": high_quality,
        "medium_quality_patterns": medium_quality,
        "avg_quality_score": round(avg_quality, 3),
        "avg_success_rate": round(avg_success_rate, 3),
        "cache_age_seconds": round(cache_age, 1),
        "cache_fresh": _pattern_cache.is_fresh(),
        "active": True,
    }


# ---------------------------------------------------------------------------
# Pattern-Based Hint Generation
# ---------------------------------------------------------------------------

def generate_hints_from_patterns(
    query_tokens: List[str],
    max_hints: int = 3,
) -> List[Dict[str, Any]]:
    """
    Generate hints from extracted patterns.

    Args:
        query_tokens: Tokenized query
        max_hints: Maximum hints to generate

    Returns:
        List of hint dictionaries
    """
    patterns = load_patterns_cached()

    # Find patterns matching query tokens
    matching_patterns = []
    query_token_set = {t.lower() for t in query_tokens}

    for pattern in patterns.values():
        # Simple keyword matching for now
        # In production, use more sophisticated matching
        pattern_keywords = pattern.id.lower().split("_")

        if query_token_set & set(pattern_keywords):
            matching_patterns.append(pattern)

    # Sort by quality and take top N
    matching_patterns.sort(key=lambda p: (p.quality_score, p.occurrences), reverse=True)
    top_patterns = matching_patterns[:max_hints]

    # Convert to hint format
    hints = []
    for pattern in top_patterns:
        hint = {
            "id": f"pattern_{pattern.id}",
            "type": "pattern_hint",
            "title": f"Pattern: {pattern.id}",
            "score": pattern.quality_score,
            "snippet": f"This pattern has {pattern.success_count}/{pattern.occurrences} successful uses",
            "reason": f"pattern match (quality={pattern.quality_score:.2f})",
            "tags": ["pattern", pattern.pattern_type],
        }
        hints.append(hint)

    return hints
