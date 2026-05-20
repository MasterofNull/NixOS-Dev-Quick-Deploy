"""Phase 56 checks — stub (to be populated in R1.3)."""
from __future__ import annotations
from ..core.context import RunContext
from ..core.result import CheckResult


def run(ctx: RunContext) -> list[CheckResult]:
    """Phase 56 checks (not yet migrated to Python)."""
    return _run_via_bash(ctx, "56")


def _run_via_bash(ctx: RunContext, phase: str) -> list[CheckResult]:
    """Fall back to the original bash script for this phase, parsing its output."""
    import subprocess, json as _json
    from ..core.result import CheckResult, Status
    script = ctx.repo_root / "scripts" / "ai" / "_aq-qa-bash"
    try:
        r = subprocess.run(
            ["bash", str(script), phase, "--json"],
            capture_output=True, text=True,
            cwd=str(ctx.repo_root),
            timeout=300,
        )
        data = _json.loads(r.stdout)
        results = []
        for item in data.get("tests", []):
            status_str = item.get("status", "SKIP")
            status = Status[status_str] if status_str in Status.__members__ else Status.SKIP
            results.append(CheckResult(
                status=status,
                layer=int(item.get("layer", 1)),
                id=item.get("id", "?"),
                description=item.get("description", ""),
                phase=str(phase),
            ))
        return results
    except Exception as e:
        from ..core.result import skipped
        return [skipped(1, f"{phase}.bash-fallback", f"phase {phase} bash fallback", str(e))]
