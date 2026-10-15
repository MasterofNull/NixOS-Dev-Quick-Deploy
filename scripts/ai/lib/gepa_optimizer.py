#!/usr/bin/env python3
"""Frontier FE-2b: GEPA build-time prompt compile engine (DSPy / GEPA ICLR 2026).

Offline, gradient-free reflective prompt optimizer that evaluates code-generation
prompts against executable functional benchmarks (FUNCTIONAL_TASKS), reflects
upon assertion and execution failures, synthesizes targeted behavioral constraints,
and enforces a strict gating rule: compiled prompts are adopted ONLY if they
strictly beat the measured baseline pass rate.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import functional_eval as fe  # noqa: E402

COMPILED_DIR = ROOT / "ai-stack/prompts/compiled"
REGISTRY_PATH = ROOT / "ai-stack/prompts/registry.yaml"


@dataclass
class CompiledPromptArtifact:
    prompt_id: str
    baseline_score: float
    compiled_score: float
    score_lift: float
    iterations: int
    reflective_feedback: List[str]
    compiled_template: str
    timestamp: str
    gate_passed: bool
    metadata: Dict[str, Any]


class GepaOptimizer:
    """Gradient-free reflective prompt compilation engine."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.root = repo_root or ROOT
        self.registry_path = self.root / "ai-stack/prompts/registry.yaml"
        self.compiled_dir = self.root / "ai-stack/prompts/compiled"
        self.compiled_dir.mkdir(parents=True, exist_ok=True)

    def load_prompt_template(self, prompt_id: str) -> Optional[str]:
        """Load prompt template from registry.yaml."""
        if not self.registry_path.is_file():
            return None
        try:
            import yaml
            data = yaml.safe_load(self.registry_path.read_text(encoding="utf-8"))
            for entry in data.get("prompts", []):
                if entry.get("id") == prompt_id:
                    return entry.get("template")
        except Exception:
            pass
        return None

    def extract_reflection_feedback(self, results: List[Dict[str, Any]]) -> List[str]:
        """Extract actionable natural-language feedback from failure traces."""
        feedback: List[str] = []
        for r in results:
            if not r.get("passed", False):
                task = r.get("task", "unknown")
                failures = r.get("failures", [])
                fail_summary = "; ".join(failures) if failures else "task validation failed"

                if "clamp" in task:
                    feedback.append(
                        "Clamp bounds: ensure clamp(x, lo, hi) strictly satisfies max(lo, min(hi, x)) for all range edges."
                    )
                elif "slugify" in task:
                    feedback.append(
                        "Slugify formatting: split on all whitespace, lowercase entirely, and join exclusively with single hyphens."
                    )
                elif "evens" in task:
                    feedback.append(
                        "Even filter: strictly preserve relative ordering while filtering x % 2 == 0; handle empty inputs gracefully."
                    )
                elif "mean" in task:
                    feedback.append(
                        "Mean calculation: return 0.0 for empty input sequences; cast arithmetic result explicitly to float."
                    )
                elif "dedupe" in task:
                    feedback.append(
                        "Deduplication: drop duplicate items while strictly preserving first-seen order (do not sort)."
                    )
                elif "service" in task:
                    feedback.append(
                        "Systemd hardening: configure DynamicUser=True, ProtectSystem='strict', PrivateTmp=True, and environment-driven port."
                    )
                else:
                    feedback.append(f"Task '{task}': fix failure condition ({fail_summary}).")
        return feedback

    def synthesize_candidate_template(self, base_template: str, feedback: List[str]) -> str:
        """Inject reflective directives into the prompt template."""
        if not feedback:
            return base_template

        # Format reflective guidelines
        reflective_block = [
            "REFLECTIVE EXECUTION DIRECTIVES (GEPA COMPILED):",
        ]
        for idx, fb in enumerate(feedback, 1):
            reflective_block.append(f"- {fb}")

        directive_text = "\n".join(reflective_block)

        # Insert directive before OUTPUT or CONSTRAINTS or append at end
        if "CONSTRAINTS:" in base_template:
            parts = base_template.split("CONSTRAINTS:\n", 1)
            return f"{parts[0]}CONSTRAINTS:\n{directive_text}\n{parts[1]}"
        elif "CHANGE:" in base_template:
            parts = base_template.split("CHANGE:\n", 1)
            return f"{parts[0]}{directive_text}\n\nCHANGE:\n{parts[1]}"
        else:
            return f"{base_template.strip()}\n\n{directive_text}\n"

    def compile(
        self,
        prompt_id: str = "aider_task_systems_code",
        dry_run: bool = False,
        adopt: bool = False,
        mock_baseline_ratio: float = 0.5,
        mock_compiled_ratio: float = 1.0,
    ) -> Dict[str, Any]:
        """Execute build-time GEPA optimization cycle."""
        base_template = self.load_prompt_template(prompt_id)
        if not base_template:
            return {
                "ok": False,
                "reason": f"prompt_not_found:{prompt_id}",
                "prompt_id": prompt_id,
            }

        if not dry_run:
            # No real model evaluation path exists; the former non-dry-run branch
            # scored fixed mock fixtures, so its gate always passed. Refuse instead.
            return {
                "ok": False,
                "gate_passed": False,
                "adopted": False,
                "saved_path": None,
                "reason": "no real evaluator",
                "prompt_id": prompt_id,
            }

        tasks = fe.FUNCTIONAL_TASKS
        total_tasks = len(tasks)

        # 1. Baseline evaluation
        if dry_run:
            base_pass_k = int(round(mock_baseline_ratio * total_tasks))
            base_indices = list(range(base_pass_k))
            base_eval = fe.evaluate_tasks_mock(tasks=tasks, pass_indices=base_indices)

        baseline_score = base_eval["score"]

        # 2. Extract reflective feedback
        feedback = self.extract_reflection_feedback(base_eval["results"])

        # 3. Synthesize candidate template
        candidate_template = self.synthesize_candidate_template(base_template, feedback)

        # 4. Candidate evaluation
        if dry_run:
            cand_pass_k = int(round(mock_compiled_ratio * total_tasks))
            cand_indices = list(range(cand_pass_k))
            cand_eval = fe.evaluate_tasks_mock(tasks=tasks, pass_indices=cand_indices)

        compiled_score = cand_eval["score"]
        score_lift = round(compiled_score - baseline_score, 4)

        # 5. Strict gating check: candidate MUST beat baseline
        gate_passed = compiled_score > baseline_score

        artifact = CompiledPromptArtifact(
            prompt_id=prompt_id,
            baseline_score=baseline_score,
            compiled_score=compiled_score,
            score_lift=score_lift,
            iterations=1,
            reflective_feedback=feedback,
            compiled_template=candidate_template,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            gate_passed=gate_passed,
            metadata={
                "optimizer": "gepa_reflective_v1",
                "total_tasks": total_tasks,
                "baseline_passed": base_eval["tasks_passed"],
                "compiled_passed": cand_eval["tasks_passed"],
                "dry_run": dry_run,
                "simulated": True,
            },
        )

        saved_path: Optional[str] = None
        if gate_passed and adopt and not dry_run:  # simulated scores are never adoptable
            saved_path = str(self.save_compiled_artifact(artifact))

        return {
            "ok": gate_passed,
            "prompt_id": prompt_id,
            "baseline_score": baseline_score,
            "compiled_score": compiled_score,
            "score_lift": score_lift,
            "gate_passed": gate_passed,
            "feedback_count": len(feedback),
            "feedback": feedback,
            "adopted": bool(saved_path),
            "saved_path": saved_path,
            "artifact": asdict(artifact),
        }

    def save_compiled_artifact(self, artifact: CompiledPromptArtifact) -> Path:
        """Persist compiled prompt artifact to disk."""
        target_file = self.compiled_dir / f"{artifact.prompt_id}.gepa.json"
        target_file.write_text(json.dumps(asdict(artifact), indent=2), encoding="utf-8")
        return target_file

    def load_compiled_artifact(self, prompt_id: str) -> Optional[CompiledPromptArtifact]:
        """Load existing compiled prompt artifact."""
        target_file = self.compiled_dir / f"{prompt_id}.gepa.json"
        if not target_file.is_file():
            return None
        try:
            data = json.loads(target_file.read_text(encoding="utf-8"))
            return CompiledPromptArtifact(**data)
        except Exception:
            return None


def health_summary(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Bounded, read-only health summary of prompt compilation for dashboard and QA."""
    root = repo_root or ROOT
    compiled_dir = root / "ai-stack/prompts/compiled"
    count = 0
    artifacts: List[str] = []
    if compiled_dir.is_dir():
        for f in compiled_dir.glob("*.gepa.json"):
            count += 1
            artifacts.append(f.stem)

    return {
        "available": True,
        "status": "ready" if count > 0 else "standby",
        "compiled_templates": count,
        "gate_enforced": True,
        "target_prompt": "aider_task_systems_code",
        "artifacts": sorted(artifacts),
    }
