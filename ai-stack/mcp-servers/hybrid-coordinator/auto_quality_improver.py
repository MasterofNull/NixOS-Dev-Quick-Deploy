"""
auto_quality_improver.py — Automatic Response Quality Improvement

Combines critic evaluation and reflection patterns to automatically
improve response quality through iterative refinement.

Process:
1. Generate initial response
2. Evaluate with critic (quality score 0-100)
3. If score < threshold, trigger improvement loop
4. Use reflection to identify issues
5. Regenerate with feedback
6. Re-evaluate until quality acceptable or max attempts reached

Benefits:
- Automatic quality improvement without manual intervention
- Combines critic (evaluation) + reflection (retry logic)
- Tracks improvement metrics
- Configurable quality thresholds and retry limits
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AUTO_IMPROVE_QUALITY_THRESHOLD = 75.0  # Minimum acceptable quality score
AUTO_IMPROVE_MAX_ATTEMPTS = 2  # Maximum improvement attempts
AUTO_IMPROVE_ENABLED_DEFAULT = False  # Opt-in by default (can be expensive)


# ---------------------------------------------------------------------------
# Improvement Metrics
# ---------------------------------------------------------------------------

@dataclass
class ImprovementMetrics:
    """Tracks auto-improvement performance."""
    total_responses: int = 0
    improvement_triggered: int = 0
    improvement_successful: int = 0
    avg_initial_quality: float = 0.0
    avg_final_quality: float = 0.0
    avg_attempts: float = 0.0

    # Rolling windows
    recent_improvements: deque = field(default_factory=lambda: deque(maxlen=100))
    recent_quality_gains: deque = field(default_factory=lambda: deque(maxlen=100))


_improvement_metrics = ImprovementMetrics()


def get_improvement_stats() -> Dict[str, Any]:
    """Get auto-improvement statistics."""
    metrics = _improvement_metrics

    if metrics.total_responses > 0:
        trigger_rate = metrics.improvement_triggered / metrics.total_responses
        success_rate = (
            metrics.improvement_successful / metrics.improvement_triggered
            if metrics.improvement_triggered > 0
            else 0.0
        )
    else:
        trigger_rate = 0.0
        success_rate = 0.0

    quality_improvement = metrics.avg_final_quality - metrics.avg_initial_quality

    return {
        "total_responses": metrics.total_responses,
        "improvement_triggered": metrics.improvement_triggered,
        "improvement_successful": metrics.improvement_successful,
        "trigger_rate": round(trigger_rate, 3),
        "success_rate": round(success_rate, 3),
        "avg_initial_quality": round(metrics.avg_initial_quality, 1),
        "avg_final_quality": round(metrics.avg_final_quality, 1),
        "quality_improvement": round(quality_improvement, 1),
        "avg_attempts": round(metrics.avg_attempts, 2),
        "active": True,
    }


# ---------------------------------------------------------------------------
# Auto-Improvement Logic
# ---------------------------------------------------------------------------

@dataclass
class ImprovementResult:
    """Result of auto-improvement process."""
    final_response: str
    final_quality: float
    initial_quality: float
    improved: bool
    attempts: int
    improvement_history: List[Dict[str, Any]]
    elapsed_ms: int


async def auto_improve_response(
    task: str,
    initial_response: str,
    initial_quality: float,
    response_generator: Callable,  # async function(feedback: str) -> str
    critic_evaluator: Callable,  # function(task, response) -> CriticEvaluation
    quality_threshold: float = AUTO_IMPROVE_QUALITY_THRESHOLD,
    max_attempts: int = AUTO_IMPROVE_MAX_ATTEMPTS,
) -> ImprovementResult:
    """
    Automatically improve response quality through iterative refinement.

    Args:
        task: Original task/query
        initial_response: First generated response
        initial_quality: Quality score of initial response
        response_generator: Async function to generate improved response
        critic_evaluator: Function to evaluate response quality
        quality_threshold: Minimum acceptable quality
        max_attempts: Maximum improvement attempts

    Returns:
        ImprovementResult with final response and metrics
    """
    global _improvement_metrics

    start_time = time.time()

    _improvement_metrics.total_responses += 1

    # Track initial quality
    n = _improvement_metrics.total_responses
    _improvement_metrics.avg_initial_quality = (
        (_improvement_metrics.avg_initial_quality * (n - 1) + initial_quality) / n
    )

    # If initial quality is acceptable, return immediately
    if initial_quality >= quality_threshold:
        _improvement_metrics.avg_final_quality = (
            (_improvement_metrics.avg_final_quality * (n - 1) + initial_quality) / n
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        return ImprovementResult(
            final_response=initial_response,
            final_quality=initial_quality,
            initial_quality=initial_quality,
            improved=False,
            attempts=0,
            improvement_history=[],
            elapsed_ms=elapsed_ms,
        )

    # Quality below threshold - trigger improvement
    _improvement_metrics.improvement_triggered += 1
    _improvement_metrics.recent_improvements.append(1)

    best_response = initial_response
    best_quality = initial_quality
    improvement_history = []

    logger.info(
        f"Auto-improvement triggered: initial_quality={initial_quality:.1f}, "
        f"threshold={quality_threshold:.1f}"
    )

    for attempt in range(1, max_attempts + 1):
        # Get critic feedback
        critique = critic_evaluator(task, best_response)

        # Build improvement prompt with feedback
        feedback_prompt = (
            f"Previous response quality: {critique.quality_score:.1f}/100\n\n"
            f"Issues identified:\n"
        )

        for issue in critique.overall_issues[:5]:  # Top 5 issues
            feedback_prompt += f"- {issue}\n"

        feedback_prompt += (
            f"\nOriginal task: {task}\n\n"
            f"Please provide an improved response addressing these issues."
        )

        # Generate improved response
        logger.info(
            f"Auto-improvement attempt {attempt}/{max_attempts}, "
            f"current_quality={critique.quality_score:.1f}"
        )

        improved_response = await response_generator(feedback_prompt)

        # Evaluate improved response
        improved_critique = critic_evaluator(task, improved_response)

        improvement_history.append({
            "attempt": attempt,
            "quality_before": round(critique.quality_score, 1),
            "quality_after": round(improved_critique.quality_score, 1),
            "improvement": round(improved_critique.quality_score - critique.quality_score, 1),
            "issues_before": len(critique.overall_issues),
            "issues_after": len(improved_critique.overall_issues),
        })

        # Keep best version
        if improved_critique.quality_score > best_quality:
            best_response = improved_response
            best_quality = improved_critique.quality_score

        # Success if we reached threshold
        if improved_critique.quality_score >= quality_threshold:
            _improvement_metrics.improvement_successful += 1
            logger.info(
                f"Auto-improvement successful: {initial_quality:.1f} → {best_quality:.1f}"
            )
            break

    # Track final quality
    _improvement_metrics.avg_final_quality = (
        (_improvement_metrics.avg_final_quality * (n - 1) + best_quality) / n
    )

    # Track attempts
    attempts_made = len(improvement_history)
    _improvement_metrics.avg_attempts = (
        (_improvement_metrics.avg_attempts * (_improvement_metrics.improvement_triggered - 1) + attempts_made)
        / _improvement_metrics.improvement_triggered
    )

    # Track quality gain
    quality_gain = best_quality - initial_quality
    _improvement_metrics.recent_quality_gains.append(quality_gain)

    elapsed_ms = int((time.time() - start_time) * 1000)

    improved = best_quality > initial_quality

    return ImprovementResult(
        final_response=best_response,
        final_quality=best_quality,
        initial_quality=initial_quality,
        improved=improved,
        attempts=attempts_made,
        improvement_history=improvement_history,
        elapsed_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def should_auto_improve(
    quality_score: float,
    enable_auto_improve: bool = AUTO_IMPROVE_ENABLED_DEFAULT,
    quality_threshold: float = AUTO_IMPROVE_QUALITY_THRESHOLD,
) -> bool:
    """
    Determine if auto-improvement should be triggered.

    Args:
        quality_score: Current response quality (0-100)
        enable_auto_improve: Whether auto-improvement is enabled
        quality_threshold: Minimum acceptable quality

    Returns:
        True if auto-improvement should be triggered
    """
    if not enable_auto_improve:
        return False

    if quality_score < quality_threshold:
        return True

    return False


def get_improvement_summary() -> Dict[str, Any]:
    """
    Get comprehensive improvement summary.

    Returns:
        Summary with stats and recent trends
    """
    stats = get_improvement_stats()

    # Calculate recent trend
    if _improvement_metrics.recent_quality_gains:
        recent_avg_gain = sum(_improvement_metrics.recent_quality_gains) / len(
            _improvement_metrics.recent_quality_gains
        )
        recent_success_rate = sum(_improvement_metrics.recent_improvements) / len(
            _improvement_metrics.recent_improvements
        )
    else:
        recent_avg_gain = 0.0
        recent_success_rate = 0.0

    return {
        **stats,
        "recent_avg_quality_gain": round(recent_avg_gain, 1),
        "recent_success_rate": round(recent_success_rate, 3),
        "config": {
            "quality_threshold": AUTO_IMPROVE_QUALITY_THRESHOLD,
            "max_attempts": AUTO_IMPROVE_MAX_ATTEMPTS,
            "enabled_by_default": AUTO_IMPROVE_ENABLED_DEFAULT,
        },
    }
