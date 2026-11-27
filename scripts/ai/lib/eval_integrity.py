#!/usr/bin/env python3
"""eval_integrity — decides whether a scoring signal is TRUSTWORTHY (RSI-Readiness R1.3).

R1 is the global gate for all self-improvement: a corruptible reward signal makes
the loop optimize toward the wrong thing. This module is the gate ON the gate —
it does not score model outputs, it certifies that a SCORER is trustworthy enough
to grade them. A scorer passes only if it:

  1. DISCRIMINATES — ranks a known-good output strictly above a known-bad one on
     every golden task. A scorer that can't tell good from bad is worthless
     however stable it is.
  2. Is DETERMINISTIC — the same (response, task) scores within a tight variance
     bound across repeats. A noisy signal can't gate decisions.
  3. ABSTAINS on infra noise — a timeout / empty / degraded response is NOT a
     capability miss; it must abstain, never score 0 (extends the prompt-5
     degraded_infra classification so contention can't fake a regression).
  4. Resists GAMING — the golden answers must be UNREADABLE by the model under
     eval (antigravity's finding: a local agent can read the test files and
     overfit). This module refuses to certify if the golden set is inside the
     agent's readable paths.

`trustworthiness_gate()` runs all four and returns a signed-off verdict. Until it
passes, NO downstream automation (R2 fine-tune, R4 shadow loop) may trust the
scores. This is the human/orchestrator sign-off, mechanized.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Callable

# A scorer under test: (response_text, task_dict) -> {"score": 0..1, "abstain": bool}
Scorer = Callable[[str, dict], dict]

# Variance bound: max stdev of the same (response, task) scored N times.
DETERMINISM_STDEV_MAX = 0.001
# Minimum margin a scorer must put between known-good and known-bad.
DISCRIMINATION_MIN_MARGIN = 0.15


@dataclass
class GateResult:
    trustworthy: bool
    discrimination: dict = field(default_factory=dict)  # {ok, failures[], min_margin}
    determinism: dict = field(default_factory=dict)     # {ok, max_stdev}
    abstention: dict = field(default_factory=dict)       # {ok, failures[]}
    isolation: dict = field(default_factory=dict)        # {ok, reason}
    reason: str = ""


@dataclass
class PromotionResult:
    promoted: bool
    reason: str
    selection: dict[str, Any]
    holdout: dict[str, Any] | None
    checks: dict[str, bool]


@dataclass
class FutilityDecision:
    halt: bool
    reason: str
    consecutive_non_promoted: int
    latest_crash_rate: float


def baseline_cache_key(
    model_id: str, quant: str, dataset_sha: str, decode_params: Mapping[str, Any],
) -> str:
    """Bind a baseline to the model, quantization, dataset and decoding config."""
    for name, value in (("model_id", model_id), ("quant", quant), ("dataset_sha", dataset_sha)):
        if not value.strip():
            raise ValueError(f"{name} must not be empty")
    payload = json.dumps(
        {"model_id": model_id, "quant": quant, "dataset_sha": dataset_sha,
         "decode_params": dict(decode_params)},
        separators=(",", ":"), sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _paired_summary(base: Mapping[str, str], candidate: Mapping[str, str]) -> dict[str, Any]:
    labels = ("pass", "fail", "crash")
    valid = (bool(base) and base.keys() == candidate.keys()
             and all(value in labels for value in base.values())
             and all(value in labels for value in candidate.values()))
    if not valid:
        return {"valid": False}
    n = len(base)
    base_crashes = sum(value == "crash" for value in base.values())
    candidate_crashes = sum(value == "crash" for value in candidate.values())
    base_errors = sum(value == "fail" for value in base.values())
    non_crash_n = n - base_crashes
    w_to_c = sum(base[key] == "fail" and candidate[key] == "pass" for key in base)
    c_to_w = sum(base[key] == "pass" and candidate[key] == "fail" for key in base)
    discordant = w_to_c + c_to_w
    difference = abs(w_to_c - c_to_w)
    z = (difference - 1.0) / math.sqrt(discordant) if discordant and difference >= 1 else 0.0
    return {
        "valid": True, "n": n, "non_crash_n": non_crash_n,
        "base_acc": (non_crash_n - base_errors) / non_crash_n if non_crash_n else 0.0,
        "base_errors": base_errors, "base_crash_rate": base_crashes / n,
        "candidate_crash_rate": candidate_crashes / n,
        "w_to_c": w_to_c, "c_to_w": c_to_w, "z_score": z,
    }


def _rate_threshold(value: float, name: str) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1")


def promotion_gate(
    base_outcomes: Mapping[str, str],
    candidate_outcomes: Mapping[str, str],
    holdout_base_outcomes: Mapping[str, str] | None = None,
    holdout_candidate_outcomes: Mapping[str, str] | None = None,
    *,
    min_n: int = 40,
    max_base_acc: float = 0.95,
    min_error_headroom: int = 20,
    max_crash_rate: float = 0.10,
    min_z: float = 1.96,
    require_holdout: bool = True,
) -> PromotionResult:
    """Require usable selection data and a significant gain on a disjoint holdout.

    Crashes count toward crash rates, never toward paired capability changes.
    Holdout locking is a caller responsibility; this gate verifies ID separation.
    """
    _rate_threshold(max_base_acc, "max_base_acc")
    _rate_threshold(max_crash_rate, "max_crash_rate")
    if (isinstance(min_n, bool) or not isinstance(min_n, int) or min_n < 1
            or isinstance(min_error_headroom, bool)
            or not isinstance(min_error_headroom, int) or min_error_headroom < 0
            or not math.isfinite(min_z) or min_z < 0):
        raise ValueError("sample/headroom thresholds must be valid integers and min_z finite/nonnegative")
    selection = _paired_summary(base_outcomes, candidate_outcomes)
    checks = {"selection_inputs": bool(selection["valid"])}

    def check_pair(prefix: str, summary: dict[str, Any]) -> None:
        valid = bool(summary["valid"])
        checks[f"{prefix}_crash_rate"] = (
            valid and summary["base_crash_rate"] <= max_crash_rate
            and summary["candidate_crash_rate"] <= max_crash_rate
        )
        checks[f"{prefix}_improvement"] = valid and summary["w_to_c"] > summary["c_to_w"]
        checks[f"{prefix}_significance"] = valid and summary["z_score"] >= min_z

    check_pair("selection", selection)
    valid = checks["selection_inputs"]
    checks["selection_min_n"] = valid and selection["n"] >= min_n
    checks["selection_saturation"] = (
        valid and selection["non_crash_n"] > 0 and selection["base_acc"] <= max_base_acc
    )
    checks["selection_headroom"] = valid and selection["base_errors"] >= min_error_headroom
    holdout = None
    if require_holdout or holdout_base_outcomes is not None or holdout_candidate_outcomes is not None:
        holdout = _paired_summary(
            holdout_base_outcomes if holdout_base_outcomes is not None else {},
            holdout_candidate_outcomes if holdout_candidate_outcomes is not None else {},
        )
        checks["holdout_inputs"] = bool(holdout["valid"])
        checks["holdout_disjoint"] = (
            checks["holdout_inputs"]
            and base_outcomes.keys().isdisjoint(
                holdout_base_outcomes.keys() if holdout_base_outcomes is not None else ()
            )
        )
        check_pair("holdout", holdout)
    failed = [name for name, passed in checks.items() if not passed]
    return PromotionResult(
        promoted=not failed,
        reason="PROMOTED: all checks passed" if not failed else "NOT PROMOTED: " + ", ".join(failed),
        selection=selection, holdout=holdout, checks=checks,
    )


def futility_breaker(
    run_history: Sequence[Mapping[str, Any]], *,
    max_consecutive_non_promoted: int = 2, max_crash_rate: float = 0.10,
) -> FutilityDecision:
    """Stop a queue after repeated failed promotions or an unhealthy latest run."""
    _rate_threshold(max_crash_rate, "max_crash_rate")
    if (isinstance(max_consecutive_non_promoted, bool)
            or not isinstance(max_consecutive_non_promoted, int)
            or max_consecutive_non_promoted < 1):
        raise ValueError("max_consecutive_non_promoted must be a positive integer")
    if any(type(run.get("promoted")) is not bool for run in run_history):
        raise ValueError("every run must have a boolean promoted field")
    latest_crash_rate = float(run_history[-1].get("crash_rate", 0.0)) if run_history else 0.0
    _rate_threshold(latest_crash_rate, "latest crash_rate")
    streak = 0
    for run in reversed(run_history):
        if run["promoted"]:
            break
        streak += 1
    reasons = []
    if latest_crash_rate > max_crash_rate:
        reasons.append("latest crash rate exceeds threshold")
    if streak >= max_consecutive_non_promoted:
        reasons.append("consecutive non-promoted runs reached threshold")
    return FutilityDecision(bool(reasons), "; ".join(reasons) or "continue", streak, latest_crash_rate)


# ── individual checks ─────────────────────────────────────────────────────────

def discrimination_check(scorer: Scorer, golden: list[dict]) -> dict:
    """Every task's known-good must score >= known-bad + margin."""
    failures = []
    margins = []
    for task in golden:
        good, bad = task.get("reference_good"), task.get("reference_bad")
        if good is None or bad is None:
            continue
        sg = scorer(good, task).get("score", 0.0)
        sb = scorer(bad, task).get("score", 0.0)
        margin = sg - sb
        margins.append(margin)
        if margin < DISCRIMINATION_MIN_MARGIN:
            failures.append({"task": task.get("id"), "good": sg, "bad": sb, "margin": round(margin, 3)})
    return {"ok": not failures and bool(margins),
            "failures": failures,
            "min_margin": round(min(margins), 3) if margins else None}


def determinism_check(scorer: Scorer, golden: list[dict], repeats: int = 5) -> dict:
    """Same (response, task) must score within the variance bound across repeats."""
    worst = 0.0
    for task in golden:
        sample = task.get("reference_good") or task.get("prompt") or ""
        scores = [scorer(sample, task).get("score", 0.0) for _ in range(repeats)]
        stdev = statistics.pstdev(scores) if len(scores) > 1 else 0.0
        worst = max(worst, stdev)
    return {"ok": worst <= DETERMINISM_STDEV_MAX, "max_stdev": round(worst, 6)}


def abstention_check(scorer: Scorer, golden: list[dict]) -> dict:
    """Infra-noise responses (empty / timeout markers) must ABSTAIN, not score 0
    as a capability miss."""
    noise = ["", "   ", "Queued behind busy local inference slot: timeout",
             "Error: model not generating", "[Error: disk full]"]
    failures = []
    task = golden[0] if golden else {}
    for n in noise:
        r = scorer(n, task)
        if not r.get("abstain", False):
            failures.append({"input": n[:40] or "(empty)", "scored": r.get("score")})
    return {"ok": not failures, "failures": failures}


def isolation_check(golden_dir: str) -> dict:
    """Refuse to certify if the golden set is readable by the agent under eval.

    antigravity's finding: a model that can read the golden answers games the
    eval. The golden dir must be declared off-limits to agent file tools —
    signalled by a `.agent-no-read` marker AND absence from any agent read-root.
    """
    marker = os.path.join(golden_dir, ".agent-no-read")
    if not os.path.isdir(golden_dir):
        return {"ok": False, "reason": f"golden dir missing: {golden_dir}"}
    if not os.path.exists(marker):
        return {"ok": False, "reason": f"golden set not marked agent-no-read (add {marker}) — "
                                       f"a model that can read the answers games the eval"}
    return {"ok": True, "reason": "golden set marked off-limits to agent read/search"}


# ── the gate ──────────────────────────────────────────────────────────────────

def trustworthiness_gate(scorer: Scorer, golden: list[dict], golden_dir: str) -> GateResult:
    """Run all four checks; a scorer is trustworthy only if ALL pass."""
    disc = discrimination_check(scorer, golden)
    det = determinism_check(scorer, golden)
    abst = abstention_check(scorer, golden)
    iso = isolation_check(golden_dir)
    ok = disc["ok"] and det["ok"] and abst["ok"] and iso["ok"]
    reasons = []
    if not disc["ok"]:
        reasons.append(f"discrimination failed ({len(disc['failures'])} tasks can't tell good from bad)")
    if not det["ok"]:
        reasons.append(f"non-deterministic (stdev {det['max_stdev']} > {DETERMINISM_STDEV_MAX})")
    if not abst["ok"]:
        reasons.append(f"scores infra-noise as capability ({len(abst['failures'])} cases)")
    if not iso["ok"]:
        reasons.append(f"gameable: {iso['reason']}")
    return GateResult(
        trustworthy=ok, discrimination=disc, determinism=det, abstention=abst,
        isolation=iso, reason="TRUSTWORTHY — signal safe to gate automation"
        if ok else "NOT TRUSTWORTHY: " + "; ".join(reasons),
    )


# ── a reference exec-based scorer (R1.2 seed) ────────────────────────────────

def exec_scorer(response: str, task: dict) -> dict:
    """Reference scorer: exec-based where possible, else keyword coverage.

    Abstains on infra-noise (empty / known error markers). Deterministic.
    task["scoring"]: "json_parse" | "py_compile" | "keyword".
    """
    text = (response or "").strip()
    _NOISE = ("queued behind busy", "error: model", "[error:", "task incomplete:")
    if not text or any(m in text.lower() for m in _NOISE):
        return {"score": 0.0, "abstain": True}

    kind = task.get("scoring", "keyword")
    if kind == "json_parse":
        import json
        try:
            json.loads(_extract_block(text))
            return {"score": 1.0, "abstain": False}
        except Exception:
            return {"score": 0.0, "abstain": False}
    if kind == "py_compile":
        import ast
        try:
            ast.parse(_extract_block(text))
            return {"score": 1.0, "abstain": False}
        except Exception:
            return {"score": 0.0, "abstain": False}
    # keyword coverage (deterministic)
    kws = [k.lower() for k in task.get("expected_keywords", [])]
    if not kws:
        return {"score": 0.0, "abstain": False}
    hit = sum(1 for k in kws if k in text.lower())
    return {"score": round(hit / len(kws), 6), "abstain": False}


def _extract_block(text: str) -> str:
    """Pull a fenced code block if present, else the whole text."""
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            body = parts[1]
            return body.split("\n", 1)[1] if "\n" in body else body
    return text


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    gd = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).resolve().parent.parent.parent.parent / "data" / "golden")
    tasks = []
    p = Path(gd) / "tasks.json"
    if p.exists():
        tasks = json.loads(p.read_text())
    res = trustworthiness_gate(exec_scorer, tasks, gd)
    print(json.dumps({"trustworthy": res.trustworthy, "reason": res.reason,
                      "discrimination": res.discrimination, "determinism": res.determinism,
                      "abstention": res.abstention, "isolation": res.isolation}, indent=2))
    sys.exit(0 if res.trustworthy else 1)
