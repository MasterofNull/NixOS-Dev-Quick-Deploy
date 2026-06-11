#!/usr/bin/env python3
"""Phase 150 Slice 5: restricted eval sandbox for improvement candidates.

Performs static, deterministic evaluation against a candidate before it advances
from "evaluating" to "reviewed". No network egress, no writes outside the sandbox
result fields. Designed to be called from candidate lifecycle transitions.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Hardware constraints (sourced from CLAUDE.md — never hardcode in runtime code)
_GPU_LAYERS_CEILING = 12
_RAM_TOTAL_GB = 27.0
_MODEL_UMBM_GB = 22.5

# Forbidden patterns in candidate descriptions/proposed actions
_FORBIDDEN_PATTERNS = [
    re.compile(r"n[_-]?gpu[_-]?layers\s*[=>]+\s*([0-9]+)", re.IGNORECASE),
    re.compile(r"--n-gpu-layers\s+([0-9]+)", re.IGNORECASE),
]

# Categories that imply high/medium/low tokenomics impact
_HIGH_TOKEN_CATEGORIES = {"delegation-quality", "performance"}
_MED_TOKEN_CATEGORIES = {"observability", "health", "security", "tooling"}


class EvalSandboxExecutor:
    """Static, deterministic candidate evaluator.

    Never writes outside eval_results. Never makes network calls.
    """

    def __init__(self, repo_root: Path | None = None):
        self.repo_root = repo_root or Path(__file__).resolve().parents[2]

    def evaluate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        """Run static evaluation and return updated eval_results dict."""
        results = dict(candidate.get("eval_results") or {})
        violations: list[str] = []

        # Schema check: required top-level fields
        for req in ("id", "category", "title"):
            if not candidate.get(req):
                violations.append(f"missing required field: {req}")

        # Hardware constraint scan: GPU layers ceiling
        gpu_viol = self._check_gpu_layers(candidate)
        violations.extend(gpu_viol)

        # Check category is recognised
        from trust_scoring import _CATEGORY_RELEVANCE  # noqa: PLC0415
        cat = str(candidate.get("category") or "")
        if cat and cat not in _CATEGORY_RELEVANCE:
            violations.append(f"unknown category: {cat!r}")

        # Tokenomics: rough classification by category
        results["tokenomics_impact"] = self._estimate_tokenomics(candidate)

        # Hardware compatible: True unless GPU violation found
        results["hardware_compatible"] = not any("gpu" in v.lower() for v in violations)

        # Sandbox pass: no violations
        results["sandbox_pass"] = len(violations) == 0
        if violations:
            results["violations"] = violations
        else:
            results.pop("violations", None)

        return results

    # ------------------------------------------------------------------
    def _check_gpu_layers(self, candidate: dict[str, Any]) -> list[str]:
        violations: list[str] = []
        text = " ".join([
            str(candidate.get("title") or ""),
            str(candidate.get("description") or ""),
            str(candidate.get("proposed_action") or ""),
        ])
        for pat in _FORBIDDEN_PATTERNS:
            for m in pat.finditer(text):
                val = int(m.group(1))
                if val > _GPU_LAYERS_CEILING:
                    violations.append(
                        f"gpu_layers={val} exceeds ceiling={_GPU_LAYERS_CEILING}"
                    )
        return violations

    def _estimate_tokenomics(self, candidate: dict[str, Any]) -> str:
        cat = str(candidate.get("category") or "")
        priority = int(candidate.get("priority") or 3)
        if cat in _HIGH_TOKEN_CATEGORIES and priority <= 2:
            return "high"
        if cat in _HIGH_TOKEN_CATEGORIES or cat in _MED_TOKEN_CATEGORIES:
            return "medium"
        return "low"


def evaluate_candidate(candidate: dict[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    """Convenience wrapper: evaluate a single candidate dict in-place.

    Returns the candidate with updated eval_results.
    """
    executor = EvalSandboxExecutor(repo_root=repo_root)
    candidate["eval_results"] = executor.evaluate(candidate)
    return candidate


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".agents/improvement/candidates.json")
    if not path.exists():
        print(f"Not found: {path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    cands = data.get("candidates", [])
    executor = EvalSandboxExecutor()
    updated = 0
    for c in cands:
        if c.get("state") in ("evaluating", "proposed"):
            c["eval_results"] = executor.evaluate(c)
            updated += 1
    if updated:
        tmp = path.with_suffix(".tmp")
        data["candidates"] = cands
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
    print(f"Evaluated {updated} candidate(s) in {path}")
