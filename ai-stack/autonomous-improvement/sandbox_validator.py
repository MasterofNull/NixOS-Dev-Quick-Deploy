"""
Sandbox Validator — Phase 17.2

Runs a multi-gate validation suite against an applied ExperimentSpec and
produces a ValidationReport with per-gate outcomes and a final recommendation.

Gates (run in order):
  Gate 1: syntax  — bash -n, python3 -m py_compile, nix-instantiate --parse
  Gate 2: smoke   — scripts/testing/smoke-focused-parity.sh (if applicable)
  Gate 3: aq-qa   — scripts/ai/aq-qa 0 → require >=39 passes
  Gate 4: report  — scripts/testing/check-aq-report-contract.sh

recommendation:
  accept  — all gates passed and blast_radius == low
  revert  — any gate failed
  queue   — blast_radius >= medium (regardless of gate results)
"""

import json
import logging
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("autonomous-improvement")

_GATE_TIMEOUT = int(os.environ.get("SANDBOX_GATE_TIMEOUT_SECONDS", "120"))
_AQ_QA_MIN_PASS = int(os.environ.get("SANDBOX_AQ_QA_MIN_PASS", "39"))
_ARTIFACT_BASE = os.environ.get("PRSI_ARTIFACT_DIR", "data/prsi-artifacts/runs")


@dataclass
class GateResult:
    name: str
    passed: bool
    output: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationReport:
    passed: bool
    gates: List[GateResult]        = field(default_factory=list)
    recommendation: str            = "revert"   # accept | revert | queue

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "gates": [g.to_dict() for g in self.gates],
            "recommendation": self.recommendation,
        }


class SandboxValidator:
    """
    Runs validation gates and produces a ValidationReport.

    Usage:
        validator = SandboxValidator(cycle_id="abc123")
        report    = validator.run_gates(spec, result)
        if report.recommendation == "revert":
            executor.revert(spec)
    """

    def __init__(self, cycle_id: str = "", repo_root: Optional[str] = None) -> None:
        self.cycle_id = cycle_id
        self.repo_root = Path(repo_root or os.getcwd())
        self._validation_count = 0
        self._artifact_dir = self.repo_root / _ARTIFACT_BASE / cycle_id if cycle_id else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_gates(self, spec: Any, result: Any) -> ValidationReport:
        """
        Run all four gates against the current repo state.
        spec/result may be None (e.g. during import-time smoke tests).
        """
        self._validation_count += 1
        gates: List[GateResult] = []

        # Gate 1: Syntax check
        gates.append(self._gate_syntax(spec))

        # Gate 2: Smoke test (only when applicable files exist)
        gates.append(self._gate_smoke(spec))

        # Gate 3: aq-qa baseline
        gates.append(self._gate_aq_qa())

        # Gate 4: Report contract
        gates.append(self._gate_report_contract())

        all_passed = all(g.passed for g in gates)
        blast_radius = (getattr(spec, "blast_radius", "low") or "low") if spec else "low"

        if not all_passed:
            recommendation = "revert"
        elif blast_radius in ("medium", "high"):
            recommendation = "queue"
        else:
            recommendation = "accept"

        report = ValidationReport(
            passed=all_passed,
            gates=gates,
            recommendation=recommendation,
        )

        self._write_artifact(report)
        return report

    # ------------------------------------------------------------------
    # Gate 1 — Syntax
    # ------------------------------------------------------------------

    def _gate_syntax(self, spec: Any) -> GateResult:
        name = "syntax"
        if spec is None:
            return GateResult(name=name, passed=True, output="no spec; skipped")

        files = getattr(spec, "files_affected", []) or []
        if not files:
            return GateResult(name=name, passed=True, output="no files affected; skipped")

        errors: List[str] = []
        for f in files:
            p = self.repo_root / f
            if not p.exists():
                continue
            suffix = p.suffix.lower()
            if suffix == ".py":
                r = self._run(["python3", "-m", "py_compile", str(p)])
                if r.returncode != 0:
                    errors.append(f"{f}: {r.stderr.strip()}")
            elif suffix == ".sh":
                r = self._run(["bash", "-n", str(p)])
                if r.returncode != 0:
                    errors.append(f"{f}: {r.stderr.strip()}")
            elif suffix == ".nix":
                r = self._run(["nix-instantiate", "--parse", str(p)])
                if r.returncode != 0:
                    errors.append(f"{f}: {r.stderr.strip()}")

        passed = len(errors) == 0
        return GateResult(
            name=name,
            passed=passed,
            output="; ".join(errors) if errors else "all files pass syntax check",
        )

    # ------------------------------------------------------------------
    # Gate 2 — Smoke
    # ------------------------------------------------------------------

    def _gate_smoke(self, spec: Any) -> GateResult:
        name = "smoke"
        smoke_script = self.repo_root / "scripts/testing/smoke-focused-parity.sh"
        if not smoke_script.exists():
            return GateResult(name=name, passed=True, output="smoke script not found; skipped")

        r = self._run(["bash", str(smoke_script)])
        passed = r.returncode == 0
        output = (r.stdout + r.stderr).strip()[-500:]
        return GateResult(name=name, passed=passed, output=output)

    # ------------------------------------------------------------------
    # Gate 3 — aq-qa
    # ------------------------------------------------------------------

    def _gate_aq_qa(self) -> GateResult:
        name = "aq-qa"
        aq_qa = self.repo_root / "scripts/ai/aq-qa"
        if not aq_qa.exists():
            return GateResult(name=name, passed=True, output="aq-qa not found; skipped")

        r = self._run(["python3", str(aq_qa), "0"])
        output = (r.stdout + r.stderr).strip()

        # Parse pass count from output: "N passed" or "N/M passed"
        passed_count = self._extract_pass_count(output)
        passed = r.returncode == 0 and passed_count >= _AQ_QA_MIN_PASS
        summary = f"pass_count={passed_count} (min={_AQ_QA_MIN_PASS})"
        return GateResult(name=name, passed=passed, output=f"{summary}; {output[-300:]}")

    def _extract_pass_count(self, output: str) -> int:
        import re
        # "39 passed" or "39/39 passed" or "PASS: 39"
        for pat in [r"(\d+)\s+passed", r"(\d+)/\d+\s+passed", r"PASS:\s*(\d+)"]:
            m = re.search(pat, output, re.IGNORECASE)
            if m:
                return int(m.group(1))
        return 0

    # ------------------------------------------------------------------
    # Gate 4 — Report contract
    # ------------------------------------------------------------------

    def _gate_report_contract(self) -> GateResult:
        name = "report-contract"
        contract_script = self.repo_root / "scripts/testing/check-aq-report-contract.sh"
        if not contract_script.exists():
            return GateResult(name=name, passed=True, output="contract script not found; skipped")

        r = self._run(["bash", str(contract_script)])
        passed = r.returncode == 0
        output = (r.stdout + r.stderr).strip()[-300:]
        return GateResult(name=name, passed=passed, output=output)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run(self, cmd: List[str]) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.repo_root,
                timeout=_GATE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="timeout")
        except OSError as exc:
            return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr=str(exc))

    def _write_artifact(self, report: ValidationReport) -> None:
        if not self._artifact_dir:
            return
        try:
            self._artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact = self._artifact_dir / f"validation-{self._validation_count}.json"
            artifact.write_text(
                json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("sandbox_validator: artifact write failed: %s", exc)
