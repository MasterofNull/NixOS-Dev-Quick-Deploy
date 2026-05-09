#!/usr/bin/env python3
"""Regression checks for aq-introspection-validate."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts" / "ai" / "aq-introspection-validate"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(args: list[str], expect_ok: bool) -> dict:
    result = subprocess.run(
        ["python3", str(TOOL), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if expect_ok and result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout or "aq-introspection-validate failed unexpectedly")
    if not expect_ok and result.returncode == 0:
        raise AssertionError("aq-introspection-validate unexpectedly passed")
    return json.loads(result.stdout)


def main() -> int:
    good_json = json.dumps(
        {
            "observed_signals": {},
            "inferred_constraints": [],
            "evidence_sources": [{"command": ["aq-qa", "0", "--json"], "status": "ok"}],
            "unknowns_or_next_checks": [],
        }
    )
    good_payload = _run(["--text", good_json, "--format", "json"], expect_ok=True)
    assert_true(good_payload["valid"] is True, "expected valid json payload")

    bad_text = """1. My Internal State\nI write after every significant action.\nEvidence sources:\n- none"""
    bad_payload = _run(["--text", bad_text, "--format", "json"], expect_ok=False)
    assert_true("observed signals" in bad_payload["missing_sections"], "expected missing observed signals section")
    assert_true(len(bad_payload["unsupported_claims"]) >= 1, "expected unsupported claim detection")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "response.md"
        path.write_text(
            "Observed signals:\n- qa green\n\nInferred constraints:\n- keep scope bounded\n\nEvidence sources:\n- aq-qa 0 --json\n\nUnknowns:\n- exact context usage\n",
            encoding="utf-8",
        )
        file_payload = _run(["--file", str(path), "--format", "json"], expect_ok=True)
        assert_true(file_payload["valid"] is True, "expected valid text payload from file")

    print("PASS: aq-introspection-validate enforces introspection response contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
