"""
Real-time learning, meta-learning, and capability gap remediation helpers.

Extracted from http_server.py (Phase 12.4 decomposition).

Exposes module-level singletons and helper functions used by the delegation
and orchestration handlers in http_server.py and delegation_handlers.py.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from gap_detection import GapDetector
from gap_remediation import RemediationPlan, RemediationResult, RemediationStatus, RemediationStrategy
from remediation_learning import OutcomeTracker, PlaybookLibrary, StrategyOptimizer
from online_learning import IncrementalLearner, LearningExample, UpdateStrategy, HintQualityAdjuster, LivePatternMiner
from feedback_acceleration import ImmediateFeedbackProcessor, SuccessFailureDetector
from meta_learning import RapidAdaptor, Task, TaskDomain

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module-level singletons (shared across all callers via import)
# ---------------------------------------------------------------------------

_REMEDIATION_PLAYBOOKS_DIR = Path(
    os.getenv("REMEDIATION_PLAYBOOKS_DIR", "/var/lib/ai-stack/hybrid/playbooks")
)
_GAP_DETECTOR = GapDetector()
_REMEDIATION_OUTCOME_TRACKER = OutcomeTracker()
_REMEDIATION_STRATEGY_OPTIMIZER = StrategyOptimizer(_REMEDIATION_OUTCOME_TRACKER)
_REMEDIATION_PLAYBOOK_LIBRARY = PlaybookLibrary(_REMEDIATION_PLAYBOOKS_DIR)
_ONLINE_LEARNER = IncrementalLearner(update_strategy=UpdateStrategy.BATCH)
_HINT_QUALITY_ADJUSTER = HintQualityAdjuster()
_LIVE_PATTERN_MINER = LivePatternMiner()
_IMMEDIATE_FEEDBACK_PROCESSOR = ImmediateFeedbackProcessor()
_SUCCESS_FAILURE_DETECTOR = SuccessFailureDetector()
_RAPID_ADAPTOR = RapidAdaptor()


# ---------------------------------------------------------------------------
# Status snapshots (used by health/status handlers)
# ---------------------------------------------------------------------------

def _capability_gap_status_snapshot() -> Dict[str, Any]:
    top_gaps = _GAP_DETECTOR.get_top_gaps(limit=5)
    return {
        "detected_gap_count": len(_GAP_DETECTOR.detected_gaps),
        "tracked_outcomes": len(_REMEDIATION_OUTCOME_TRACKER.outcomes),
        "top_gaps": [
            {
                "gap_id": gap.gap_id,
                "gap_type": gap.gap_type.value,
                "severity": gap.severity.name.lower(),
                "priority_score": round(float(gap.priority_score or 0.0), 4),
                "description": gap.description,
            }
            for gap in top_gaps
        ],
    }


def _real_time_learning_status_snapshot() -> Dict[str, Any]:
    top_hints = _HINT_QUALITY_ADJUSTER.get_top_hints(limit=5)
    pending_actions = _IMMEDIATE_FEEDBACK_PROCESSOR.get_pending_actions(limit=5)
    return {
        "learning_buffer_size": len(_ONLINE_LEARNER.learning_buffer),
        "update_count": len(_ONLINE_LEARNER.update_history),
        "pattern_count": len(_LIVE_PATTERN_MINER.patterns),
        "top_hints": [[hint_id, round(float(score), 4)] for hint_id, score in top_hints],
        "pending_feedback_actions": [
            {
                "action_id": action.action_id,
                "description": action.description,
                "priority": round(float(action.priority), 4),
            }
            for action in pending_actions
        ],
    }


def _meta_learning_status_snapshot() -> Dict[str, Any]:
    optimizer_history = _RAPID_ADAPTOR.meta_optimizer.optimization_history
    latest = optimizer_history[-1] if optimizer_history else {}
    return {
        "cached_adaptations": len(_RAPID_ADAPTOR.adaptation_cache),
        "meta_update_count": len(_RAPID_ADAPTOR.maml.update_history),
        "known_task_embeddings": len(_RAPID_ADAPTOR.embedder.task_embeddings),
        "known_domain_prototypes": len(_RAPID_ADAPTOR.few_shot.prototypes),
        "latest_hyperparams": dict(_RAPID_ADAPTOR.meta_optimizer.hyperparams),
        "latest_optimization_score": round(float(latest.get("best_score", 0.0) or 0.0), 4) if latest else 0.0,
    }


# ---------------------------------------------------------------------------
# Gap failure text builder
# ---------------------------------------------------------------------------

def _build_gap_failure_text(
    final_classification: Dict[str, Any],
    delegated_quality: Dict[str, Any],
) -> str:
    parts: List[str] = []
    failure_classes = final_classification.get("failure_classes") or []
    if failure_classes:
        parts.append("delegated failure classes: " + ", ".join(str(item) for item in failure_classes))
    salvage = final_classification.get("salvage")
    if isinstance(salvage, dict) and salvage.get("reasoning_excerpt"):
        parts.append(str(salvage.get("reasoning_excerpt") or ""))
    issues = delegated_quality.get("issues") or []
    if issues:
        parts.append("quality issues: " + "; ".join(str(item) for item in issues))
    suggestions = delegated_quality.get("suggestions") or []
    if suggestions:
        parts.append("quality suggestions: " + "; ".join(str(item) for item in suggestions))
    return " | ".join(part for part in parts if part).strip()


# ---------------------------------------------------------------------------
# Remediation planning and outcome recording
# ---------------------------------------------------------------------------

def _plan_capability_gap_remediation(gap: Any) -> Dict[str, Any]:
    strategies = _REMEDIATION_STRATEGY_OPTIMIZER.optimize_for_gap_type(gap.gap_type)
    strategy = strategies[0] if strategies else RemediationStrategy.MANUAL_INTERVENTION
    steps_by_strategy = {
        RemediationStrategy.INSTALL_PACKAGE: [
            "check declarative package source of truth",
            "stage package integration through Nix modules",
            "validate with repo gates before deploy",
        ],
        RemediationStrategy.IMPORT_KNOWLEDGE: [
            "collect authoritative docs for the missing topic",
            "stage bounded knowledge artifact or hint",
            "validate references and expected operators",
        ],
        RemediationStrategy.SYNTHESIZE_SKILL: [
            "derive a repeatable procedure from recent successful examples",
            "stage a bounded skill artifact",
            "validate the workflow against the failing task class",
        ],
        RemediationStrategy.EXTRACT_PATTERN: [
            "extract a reusable pattern from repeated successful work",
            "stage the pattern contract in repo surfaces",
            "validate against similar tasks",
        ],
        RemediationStrategy.CREATE_INTEGRATION: [
            "identify the missing coordinator or dashboard hook",
            "stage non-destructive integration wiring",
            "validate with targeted regression coverage",
        ],
        RemediationStrategy.MANUAL_INTERVENTION: [
            "collect failure evidence",
            "surface manual remediation recommendation",
            "defer destructive changes until reviewed",
        ],
    }
    playbook = _REMEDIATION_PLAYBOOK_LIBRARY.find_similar_playbook(gap)
    plan = RemediationPlan(
        plan_id=f"gap-plan-{gap.gap_id}",
        gap_id=gap.gap_id,
        strategy=strategy,
        steps=steps_by_strategy.get(strategy, steps_by_strategy[RemediationStrategy.MANUAL_INTERVENTION]),
        estimated_effort="low" if strategy != RemediationStrategy.MANUAL_INTERVENTION else "medium",
        requires_approval=strategy in {RemediationStrategy.INSTALL_PACKAGE, RemediationStrategy.MANUAL_INTERVENTION},
    )
    return {
        "plan_id": plan.plan_id,
        "strategy": plan.strategy.value,
        "steps": plan.steps,
        "estimated_effort": plan.estimated_effort,
        "requires_approval": plan.requires_approval,
        "playbook_id": playbook.playbook_id if playbook else "",
        "playbook_name": playbook.name if playbook else "",
    }


def _record_capability_gap_outcomes(
    gaps: List[Any],
    *,
    duration_seconds: float,
    response_status: int,
    fallback_applied: bool,
    finalization_applied: bool,
    delegated_quality: Dict[str, Any],
) -> None:
    remediation_actions: List[str] = []
    strategy = RemediationStrategy.MANUAL_INTERVENTION
    if fallback_applied:
        remediation_actions.append("delegated remote-free fallback applied")
        strategy = RemediationStrategy.CREATE_INTEGRATION
    if finalization_applied:
        remediation_actions.append("delegated finalization remediation applied")
        strategy = RemediationStrategy.EXTRACT_PATTERN
    if delegated_quality.get("refinement_applied"):
        remediation_actions.append("delegated quality refinement applied")
        strategy = RemediationStrategy.SYNTHESIZE_SKILL
    if delegated_quality.get("cached_fallback_used"):
        remediation_actions.append("delegated cached response fallback applied")
        strategy = RemediationStrategy.IMPORT_KNOWLEDGE
    if not remediation_actions:
        return
    success = response_status < 400
    for gap in gaps:
        plan = RemediationPlan(
            plan_id=f"gap-outcome-{gap.gap_id}-{int(time.time())}",
            gap_id=gap.gap_id,
            strategy=strategy,
            steps=remediation_actions,
            estimated_effort="low",
        )
        result = RemediationResult(
            plan_id=plan.plan_id,
            gap_id=gap.gap_id,
            status=RemediationStatus.SUCCESSFUL if success else RemediationStatus.FAILED,
            success=success,
            actions_taken=list(remediation_actions),
            artifacts_created=[],
            validation_passed=success,
        )
        outcome = _REMEDIATION_OUTCOME_TRACKER.record_outcome(gap, plan, result, duration_seconds)
        playbook = _REMEDIATION_PLAYBOOK_LIBRARY.find_similar_playbook(gap)
        if playbook:
            _REMEDIATION_PLAYBOOK_LIBRARY.update_playbook(playbook.playbook_id, outcome)
        elif success:
            _REMEDIATION_PLAYBOOK_LIBRARY.create_playbook(
                f"{gap.gap_type.value} recovery",
                gap,
                plan,
                outcome,
            )


# ---------------------------------------------------------------------------
# Online and meta learning application
# ---------------------------------------------------------------------------

async def _apply_real_time_learning(
    task: str,
    body: Any,
    *,
    profile_name: str,
    delegated_quality: Dict[str, Any],
    final_classification: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from delegation_handlers import _extract_delegated_response_text
    response_text = _extract_delegated_response_text(body)
    if not response_text:
        return {"available": False}
    quality_score = float(delegated_quality.get("quality_score", 0.0) or 0.0)
    if quality_score <= 0:
        quality_score = 0.85 if not final_classification.get("is_failure") else 0.35
    example = LearningExample(
        example_id=str(uuid4()),
        query=task,
        response=response_text,
        feedback=max(0.0, min(1.0, quality_score)),
        context={
            "profile": profile_name,
            "context": context or {},
            "failure_classes": final_classification.get("failure_classes", []),
        },
    )
    await _ONLINE_LEARNER.add_example(example)
    await _LIVE_PATTERN_MINER.mine_interaction(task, response_text, example.context)
    _HINT_QUALITY_ADJUSTER.record_hint_feedback(f"delegate:{profile_name}", example.feedback)
    implicit_feedback = _SUCCESS_FAILURE_DETECTOR.create_implicit_feedback(task, response_text, None)
    actions = await _IMMEDIATE_FEEDBACK_PROCESSOR.process_feedback(implicit_feedback)
    return {
        "available": True,
        "example_id": example.example_id,
        "feedback_score": round(example.feedback, 4),
        "update_count": len(_ONLINE_LEARNER.update_history),
        "pattern_count": len(_LIVE_PATTERN_MINER.patterns),
        "pending_action_count": len(_IMMEDIATE_FEEDBACK_PROCESSOR.pending_actions),
        "executed_action_count": sum(1 for action in actions if action.executed_at is not None),
    }


async def _apply_meta_learning(
    task: str,
    body: Any,
    *,
    profile_name: str,
    delegated_quality: Dict[str, Any],
) -> Dict[str, Any]:
    from delegation_handlers import _extract_delegated_response_text
    response_text = _extract_delegated_response_text(body)
    if not response_text:
        return {"available": False}

    domain_map = {
        "remote-gemini": TaskDomain.PLANNING,
        "remote-coding": TaskDomain.CODE_GENERATION,
        "remote-reasoning": TaskDomain.PLANNING,
        "remote-tool-calling": TaskDomain.CONFIGURATION,
        "remote-free": TaskDomain.EXPLANATION,
    }
    domain = domain_map.get(str(profile_name or "").strip(), TaskDomain.PLANNING)
    quality_score = float(delegated_quality.get("quality_score", 0.0) or 0.0)
    few_shot_examples = [
        {
            "input": task,
            "output": response_text[:1200],
            "quality": max(0.0, min(1.0, quality_score or 0.75)),
        }
    ]
    meta_task = Task(
        task_id=str(uuid4()),
        domain=domain,
        description=task,
        examples=list(few_shot_examples),
    )
    adaptation = await _RAPID_ADAPTOR.adapt_to_new_task(meta_task, few_shot_examples)
    return {
        "available": True,
        "task_id": meta_task.task_id,
        "domain": domain.value,
        "method": str(adaptation.get("method", "") or ""),
        "similar_task_count": len(adaptation.get("similar_tasks") or []),
        "embedding_norm": round(float(adaptation.get("embedding_norm", 0.0) or 0.0), 4),
        "cached_adaptations": len(_RAPID_ADAPTOR.adaptation_cache),
    }
