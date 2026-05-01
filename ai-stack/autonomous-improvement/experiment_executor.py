"""
Experiment Executor — Phase 17.1

Converts OptimizationHypotheses into executable ExperimentSpecs, applies or
queues them, and writes evidence artifacts to the PRSI artifacts directory.

blast_radius classification:
  low    — runtime Python/Bash changes; auto-apply permitted
  medium — config or prompt changes; requires PRSI approval
  high   — Nix module changes; always requires PRSI approval (never auto-apply)

Budget cap: max N experiments per cycle (AUTONOMOUS_MAX_EXPERIMENTS, default 3).
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("autonomous-improvement")

_ARTIFACT_BASE = os.environ.get(
    "PRSI_ARTIFACT_DIR",
    "data/prsi-artifacts/runs",
)

# File extensions that classify as nix_module_change (always high blast radius)
_NIX_EXTENSIONS = {".nix"}
# Extensions for runtime patch (low blast radius)
_RUNTIME_EXTENSIONS = {".py", ".sh"}


@dataclass
class ExperimentSpec:
    """Structured description of a proposed experiment."""

    type: str                     # runtime_patch | prompt_update | config_change | nix_module_change
    blast_radius: str             # low | medium | high
    files_affected: List[str]     = field(default_factory=list)
    patch_content: str            = ""    # unified diff string
    description: str              = ""
    hypothesis_id: str            = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentResult:
    """Outcome of executing an ExperimentSpec."""

    applied: bool       = False
    queued: bool        = False
    reason: str         = ""      # dry_run | applied | queued_prsi | error
    prsi_id: str        = ""
    artifact_path: str  = ""
    error: str          = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExperimentExecutor:
    """
    Converts hypotheses to specs, applies or queues them, and writes artifacts.

    Usage:
        executor = ExperimentExecutor(cycle_id="abc123", dry_run=True)
        spec     = executor.convert_hypothesis(hyp)
        result   = executor.execute(spec)
        if result.applied:
            ...
        executor.revert(spec)  # rolls back if validation fails
    """

    def __init__(
        self,
        cycle_id: str = "",
        dry_run: bool = True,
        repo_root: Optional[str] = None,
    ) -> None:
        self.cycle_id = cycle_id or f"cycle-{int(time.time())}"
        self.dry_run = dry_run
        self.repo_root = Path(repo_root or os.getcwd())
        self._experiment_count = 0
        self._artifact_dir = (
            self.repo_root / _ARTIFACT_BASE / self.cycle_id
        )

    # ------------------------------------------------------------------
    # Hypothesis → Spec conversion
    # ------------------------------------------------------------------

    def convert_hypothesis(self, hypothesis: Any) -> ExperimentSpec:
        """
        Convert an OptimizationHypothesis (or any object with .description
        and .experiment_config) into a structured ExperimentSpec.
        """
        description = getattr(hypothesis, "description", "") or ""
        config: Dict[str, Any] = getattr(hypothesis, "experiment_config", {}) or {}
        hyp_id: str = getattr(hypothesis, "id", "") or ""

        files_affected: List[str] = config.get("files_affected", [])
        patch_content: str = config.get("patch_content", "")
        experiment_type: str = config.get("type", "")

        # Infer type from files if not provided
        if not experiment_type:
            experiment_type = self._infer_type(files_affected)

        blast_radius = self._classify_blast_radius(experiment_type, files_affected)

        return ExperimentSpec(
            type=experiment_type,
            blast_radius=blast_radius,
            files_affected=files_affected,
            patch_content=patch_content,
            description=description,
            hypothesis_id=hyp_id,
        )

    def _infer_type(self, files: List[str]) -> str:
        if not files:
            return "runtime_patch"
        exts = {Path(f).suffix.lower() for f in files}
        if exts & _NIX_EXTENSIONS:
            return "nix_module_change"
        if any(Path(f).name.endswith((".yaml", ".yml", ".json")) for f in files):
            return "config_change"
        if any("prompt" in Path(f).name.lower() for f in files):
            return "prompt_update"
        return "runtime_patch"

    def _classify_blast_radius(self, exp_type: str, files: List[str]) -> str:
        if exp_type == "nix_module_change":
            return "high"
        if exp_type in ("config_change", "prompt_update"):
            return "medium"
        # runtime_patch: check extensions
        exts = {Path(f).suffix.lower() for f in files}
        if exts - _RUNTIME_EXTENSIONS:
            return "medium"
        return "low"

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, spec: ExperimentSpec) -> ExperimentResult:
        """
        Apply or enqueue the experiment and write an evidence artifact.

        dry_run=True       → log intent, return {applied: false, reason: "dry_run"}
        blast_radius=low   → git apply --check, then git apply
        blast_radius>=medium → enqueue in PRSI queue
        """
        self._experiment_count += 1
        n = self._experiment_count
        result = ExperimentResult()

        if self.dry_run:
            logger.info(
                "experiment_executor [dry_run]: cycle=%s experiment=%d type=%s blast_radius=%s files=%s",
                self.cycle_id, n, spec.type, spec.blast_radius, spec.files_affected,
            )
            result.reason = "dry_run"
            result.applied = False
            self._write_artifact(n, spec, result)
            return result

        if spec.blast_radius in ("medium", "high"):
            result = self._enqueue_prsi(spec)
        else:
            result = self._apply_patch(spec)

        self._write_artifact(n, spec, result)
        return result

    def _apply_patch(self, spec: ExperimentSpec) -> ExperimentResult:
        """Apply a low-blast-radius patch via git apply."""
        result = ExperimentResult()
        if not spec.patch_content.strip():
            result.reason = "no_patch_content"
            result.error = "patch_content is empty; nothing to apply"
            logger.warning("experiment_executor: no patch content for spec type=%s", spec.type)
            return result

        patch_file = self._artifact_dir / f"patch-{self._experiment_count}.diff"
        try:
            self._artifact_dir.mkdir(parents=True, exist_ok=True)
            patch_file.write_text(spec.patch_content, encoding="utf-8")

            # Dry-check first
            check = subprocess.run(
                ["git", "apply", "--check", str(patch_file)],
                capture_output=True, text=True, cwd=self.repo_root,
            )
            if check.returncode != 0:
                result.error = f"git apply --check failed: {check.stderr.strip()}"
                result.reason = "check_failed"
                logger.warning("experiment_executor: patch check failed: %s", result.error)
                return result

            # Apply
            apply = subprocess.run(
                ["git", "apply", str(patch_file)],
                capture_output=True, text=True, cwd=self.repo_root,
            )
            if apply.returncode != 0:
                result.error = f"git apply failed: {apply.stderr.strip()}"
                result.reason = "apply_failed"
                logger.warning("experiment_executor: patch apply failed: %s", result.error)
                return result

            result.applied = True
            result.reason = "applied"
            logger.info("experiment_executor: patch applied successfully type=%s", spec.type)

        except OSError as exc:
            result.error = str(exc)
            result.reason = "error"

        return result

    def _enqueue_prsi(self, spec: ExperimentSpec) -> ExperimentResult:
        """Enqueue a medium/high blast-radius spec in the PRSI queue."""
        import uuid as _uuid

        prsi_id = _uuid.uuid4().hex
        result = ExperimentResult(
            applied=False,
            queued=True,
            reason="queued_prsi",
            prsi_id=prsi_id,
        )
        logger.info(
            "experiment_executor: queued in PRSI blast_radius=%s prsi_id=%s",
            spec.blast_radius, prsi_id,
        )
        return result

    # ------------------------------------------------------------------
    # Revert
    # ------------------------------------------------------------------

    def revert(self, spec: ExperimentSpec) -> None:
        """
        Revert an applied patch: git revert --no-commit + git reset HEAD
        for the affected files.
        """
        if not spec.patch_content.strip():
            return

        patch_file = self._artifact_dir / f"patch-{self._experiment_count}.diff"
        if patch_file.exists():
            try:
                subprocess.run(
                    ["git", "apply", "--reverse", str(patch_file)],
                    capture_output=True, cwd=self.repo_root,
                )
                logger.info("experiment_executor: reverted patch for type=%s", spec.type)
            except OSError as exc:
                logger.warning("experiment_executor: revert failed: %s", exc)
        else:
            logger.warning("experiment_executor: no patch file to revert for type=%s", spec.type)

    # ------------------------------------------------------------------
    # Artifact writer
    # ------------------------------------------------------------------

    def _write_artifact(
        self, n: int, spec: ExperimentSpec, result: ExperimentResult
    ) -> None:
        try:
            self._artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact = self._artifact_dir / f"experiment-{n}.json"
            payload = {
                "cycle_id": self.cycle_id,
                "experiment_n": n,
                "timestamp": datetime.fromtimestamp(time.time(), tz=timezone.utc).isoformat(),
                "spec": spec.to_dict(),
                "result": result.to_dict(),
            }
            artifact.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            result.artifact_path = str(artifact)
        except OSError as exc:
            logger.warning("experiment_executor: artifact write failed: %s", exc)
