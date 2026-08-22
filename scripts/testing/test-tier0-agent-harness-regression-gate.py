#!/usr/bin/env python3
"""Hermetic contract checks for Tier0's local-agent regression-suite gate."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts/governance/tier0-validation-gate.sh"
REQUIRED_SUITES = (
    "test-context-assembler.py",
    "test-read-file-gate.py",
    "test-reread-intervention.py",
    "test-noaction-intervention.py",
    "test-edit-feedback.py",
    "test-write-region.py",
    "test-tool-call-grammar.py",
    "test-llm-cassette.py",
    "test-agent-loop-bounds.py",
    "test-local-shell-sandbox.py",
)


def extract_gate_function() -> str:
    lines = GATE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("gate_agent_harness_regression_suites()"))
    depth = 0
    extracted: list[str] = []
    for line in lines[start:]:
        extracted.append(line)
        stripped = line.strip()
        if stripped.endswith("{"):
            depth += 1
        elif stripped == "}":
            depth -= 1
            if depth == 0:
                return "\n".join(extracted)
    raise AssertionError("could not extract gate_agent_harness_regression_suites")


def run_gate(suite_names: tuple[str, ...], *, fake_timeout: bool = False) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        suite_dir = root / "scripts/testing"
        suite_dir.mkdir(parents=True)
        for name in suite_names:
            path = suite_dir / name
            path.write_text("print('suite ok')\n", encoding="utf-8")

        bin_dir = root / "bin"
        bin_dir.mkdir()
        if fake_timeout:
            timeout = bin_dir / "timeout"
            timeout.write_text("#!/usr/bin/env bash\necho simulated timeout >&2\nexit 124\n", encoding="utf-8")
            timeout.chmod(0o755)

        harness = root / "run-gate.sh"
        harness.write_text(
            "set -u\n"
            "pass() { printf 'PASS:%s\\n' \"$*\"; }\n"
            "fail() { printf 'FAIL:%s\\n' \"$*\"; }\n"
            "log() { printf 'LOG:%s\\n' \"$*\"; }\n"
            f"REPO_ROOT={root!s}\n"
            f"{extract_gate_function()}\n"
            "gate_agent_harness_regression_suites\n",
            encoding="utf-8",
        )
        return subprocess.run(
            ["bash", str(harness)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        )


def main() -> int:
    source = GATE.read_text(encoding="utf-8")
    for suite in REQUIRED_SUITES:
        assert suite in source, f"required suite omitted from manifest: {suite}"
    assert "Harness regression suite missing (required)" in source
    assert 'timeout "${suite_timeout_seconds}s" python3' in source
    assert "Harness regression diagnostics" in source

    passing = run_gate(REQUIRED_SUITES)
    assert passing.returncode == 0, passing.stderr or passing.stdout

    missing = run_gate(REQUIRED_SUITES[:-1])
    assert missing.returncode != 0
    assert "missing (required): test-local-shell-sandbox.py" in missing.stdout

    timed_out = run_gate(REQUIRED_SUITES, fake_timeout=True)
    assert timed_out.returncode != 0
    assert "timed out after 60s" in timed_out.stdout
    assert "simulated timeout" in timed_out.stderr

    print("PASS: Tier0 local-agent harness gate requires every suite and fails closed on timeout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
