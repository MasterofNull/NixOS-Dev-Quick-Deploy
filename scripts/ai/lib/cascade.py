#!/usr/bin/env python3
"""cascade — draft-and-polish routing: local drafts, remote polishes only if needed.

god-tier prompt 7. Instead of parallel fan-out (every lane runs every task —
redundant, and remote tokens spent even when local was fine), the cascade:
  1. LOCAL drafts the answer (free, private).
  2. A task-agnostic VERIFIER scores the draft's confidence (no new model).
  3. If confidence >= the task-class threshold -> keep the local draft (0 remote
     tokens). Otherwise ESCALATE to a remote lane to polish or redo.

Every decision is an event on the A2A bus (trace-linked) and a row in a savings
ledger, so remote-token savings per task class accumulate for the "keep whichever
wins per class" comparison against the fan-out baseline.

Confidence is heuristic + optional self-rating — deliberately no dependency on a
verifier model (SMALL_RESIDENT is not deployed). When that model lands it can
replace/augment score_confidence() behind the same interface.

Kill switch: CASCADE_ENABLED=0 (callers fall back to their prior routing).
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

# ── confidence scoring (task-agnostic, no model) ─────────────────────────────

_HEDGE_MARKERS = (
    "i'm not sure", "i am not sure", "not certain", "unclear", "i don't know",
    "i do not know", "hard to say", "might be", "possibly", "perhaps",
    "it depends", "cannot determine", "no clear answer",
)
_REFUSAL_MARKERS = (
    "i cannot", "i can't", "unable to", "i'm unable", "no information",
    "insufficient context", "cannot answer", "i don't have",
)
# Per-task-class confidence bar to KEEP the local draft. Strict-format / high-
# stakes classes demand more; cheap classes accept a lower bar.
DEFAULT_THRESHOLD = 0.70
CLASS_THRESHOLDS = {
    "json_repair": 0.85, "tool_schema_validation": 0.85, "structured": 0.85,
    "classification": 0.75, "path_grep_summary": 0.70, "short_critique": 0.60,
    "diff_analysis": 0.72, "bounded_edit": 0.78, "single_file_plan": 0.72,
    "architecture": 0.80, "consensus_vote": 0.80, "multi_file_refactor": 0.82,
    "dissent_review": 0.78, "test_error_triage": 0.72,
}


def threshold_for(task_class: Optional[str]) -> float:
    return CLASS_THRESHOLDS.get(task_class or "", DEFAULT_THRESHOLD)


def score_confidence(response: str, *, min_words: int = 12) -> dict[str, Any]:
    """Return {confidence: 0..1, signals: {...}} for a draft response.

    Penalizes hedging, refusals, too-short answers, and degenerate repetition.
    Task-agnostic: no expected-keyword knowledge required.
    """
    text = (response or "").strip()
    low = text.lower()
    words = text.split()
    n = len(words)

    conf = 1.0
    signals: dict[str, Any] = {}

    if n == 0:
        return {"confidence": 0.0, "signals": {"empty": True}}

    hedges = sum(low.count(m) for m in _HEDGE_MARKERS)
    refusals = sum(low.count(m) for m in _REFUSAL_MARKERS)
    if hedges:
        conf -= min(0.45, 0.18 * hedges)
        signals["hedges"] = hedges
    if refusals:
        conf -= min(0.6, 0.30 * refusals)
        signals["refusals"] = refusals

    if n < min_words:
        conf -= min(0.5, (min_words - n) / min_words * 0.5)
        signals["short"] = n

    # Degenerate repetition: fraction of repeated 3-grams.
    if n >= 6:
        grams = [" ".join(words[i:i + 3]) for i in range(n - 2)]
        rep = 1 - (len(set(grams)) / max(len(grams), 1))
        if rep > 0.3:
            conf -= min(0.4, (rep - 0.3))
            signals["repetition"] = round(rep, 2)

    conf = max(0.0, min(1.0, round(conf, 3)))
    return {"confidence": conf, "signals": signals}


# ── cascade orchestration ────────────────────────────────────────────────────

def enabled() -> bool:
    return os.environ.get("CASCADE_ENABLED", "1") != "0"


@dataclass
class CascadeResult:
    response: str
    source: str                 # "local" | "remote"
    escalated: bool
    confidence: float
    threshold: float
    task_class: Optional[str]
    local_tokens: int = 0
    remote_tokens: int = 0
    signals: dict[str, Any] = field(default_factory=dict)

    def savings_vs_fanout(self, remote_lanes: int = 1) -> int:
        """Remote tokens SAVED vs a fan-out that would have run every remote lane.

        Fan-out spends remote tokens on all lanes regardless; the cascade spends
        them only on escalation. Estimate saved = (lanes that fan-out would run)
        * this task's remote token cost, minus what the cascade actually spent.
        """
        fanout_remote = remote_lanes * max(self.remote_tokens, self._est_remote_cost())
        return max(0, fanout_remote - self.remote_tokens)

    def _est_remote_cost(self) -> int:
        # When not escalated, estimate what a remote lane WOULD have cost from the
        # local output size (rough parity) so savings are non-zero for kept drafts.
        return max(64, self.local_tokens)


def run_cascade(
    task: str,
    *,
    task_class: Optional[str] = None,
    local_fn: Callable[[str], tuple[str, int]],
    remote_fn: Optional[Callable[[str, str], tuple[str, int]]] = None,
    threshold: Optional[float] = None,
    agent: str = "cascade",
) -> CascadeResult:
    """Draft locally, verify, escalate to remote only below threshold.

    local_fn(task) -> (response, tokens). remote_fn(task, draft) -> (response,
    tokens); receives the local draft so it can POLISH rather than redo. Both
    injectable for tests; the CLI wires them to delegate-to-local /
    delegate-to-antigravity.
    """
    thr = threshold if threshold is not None else threshold_for(task_class)
    draft, local_tokens = local_fn(task)
    scored = score_confidence(draft)
    conf = scored["confidence"]

    _emit_cascade_event(agent, "cascade.draft", task_class, conf, thr,
                        {"local_tokens": local_tokens, "signals": scored["signals"]})

    if conf >= thr or remote_fn is None:
        res = CascadeResult(
            response=draft, source="local", escalated=False, confidence=conf,
            threshold=thr, task_class=task_class, local_tokens=local_tokens,
            signals=scored["signals"],
        )
        _emit_cascade_event(agent, "cascade.keep_local", task_class, conf, thr,
                            {"saved_remote_tokens": res.savings_vs_fanout()})
        _ledger_append(res)
        return res

    polished, remote_tokens = remote_fn(task, draft)
    res = CascadeResult(
        response=polished, source="remote", escalated=True, confidence=conf,
        threshold=thr, task_class=task_class, local_tokens=local_tokens,
        remote_tokens=remote_tokens, signals=scored["signals"],
    )
    _emit_cascade_event(agent, "cascade.escalated", task_class, conf, thr,
                        {"remote_tokens": remote_tokens})
    _ledger_append(res)
    return res


# ── events + ledger ──────────────────────────────────────────────────────────

def _emit_cascade_event(agent, etype, task_class, conf, thr, extra) -> None:
    try:
        import event_log
        event_log.emit(agent, etype, subject=task_class or "",
                       payload={"confidence": conf, "threshold": thr, **extra})
    except Exception:
        pass  # observability must never break routing


def _ledger_path():
    from pathlib import Path
    p = os.environ.get("CASCADE_LEDGER", "").strip()
    if p:
        return Path(p)
    return Path(_LIB).parent.parent.parent / ".agents" / "telemetry" / "cascade-ledger.jsonl"


def _ledger_append(res: CascadeResult) -> None:
    import json
    from pathlib import Path
    try:
        path = _ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(), "task_class": res.task_class, "source": res.source,
            "escalated": res.escalated, "confidence": res.confidence,
            "threshold": res.threshold, "local_tokens": res.local_tokens,
            "remote_tokens": res.remote_tokens,
            "saved_remote_tokens": res.savings_vs_fanout(),
        }
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:
        pass


def ledger_summary() -> dict[str, Any]:
    """Per-task-class savings summary for 'keep whichever wins per class'."""
    import json
    from collections import defaultdict
    path = _ledger_path()
    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "escalated": 0, "saved_remote_tokens": 0, "remote_tokens": 0})
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            k = r.get("task_class") or "(none)"
            a = agg[k]
            a["n"] += 1
            a["escalated"] += 1 if r.get("escalated") else 0
            a["saved_remote_tokens"] += int(r.get("saved_remote_tokens") or 0)
            a["remote_tokens"] += int(r.get("remote_tokens") or 0)
    except OSError:
        pass
    for k, a in agg.items():
        a["escalation_rate"] = round(a["escalated"] / max(a["n"], 1), 3)
        a["recommend"] = "cascade" if a["escalation_rate"] < 0.5 else "review-vs-fanout"
    return dict(agg)


if __name__ == "__main__":
    import json
    if "--summary" in sys.argv:
        print(json.dumps(ledger_summary(), indent=2))
    else:
        print("usage: cascade.py --summary   (orchestration is via aq-cascade / library)")
