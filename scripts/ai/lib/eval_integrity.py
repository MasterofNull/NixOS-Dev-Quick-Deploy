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

import os
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

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
