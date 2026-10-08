#!/usr/bin/env python3
"""Tests for check-frontier-fold tier0 validation.

Tests verify that the tier0 check correctly detects orphan folded candidates:
  (a) scheduled candidate targeting a missing plan → FAIL (exit 1)
  (b) target plan exists but lacks the folded slice → FAIL (exit 1)
  (c) properly folded candidate in target plan → PASS (exit 0)
  (d) no scheduled candidates → PASS (exit 0)
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Add lib to path
SCRIPTS_LIB = Path(__file__).resolve().parent.parent / "ai" / "lib"
sys.path.insert(0, str(SCRIPTS_LIB))

import frontier_backlog as fb
import frontier_fold as ff


def run_check(repo_root: str | Path) -> tuple[int, str, str]:
    """Run check-frontier-fold as subprocess with FRONTIER_REPO_ROOT and CODE_REPO_ROOT env vars."""
    check_path = Path(__file__).resolve().parent.parent / "governance" / "tier0.d" / "check-frontier-fold"
    code_repo = Path(__file__).resolve().parents[2]  # Real repo (contains scripts/ai/lib)

    env = dict(__import__("os").environ)
    repo_root_abs = Path(repo_root).resolve()
    env["FRONTIER_REPO_ROOT"] = str(repo_root_abs)  # Where to read backlog/plans
    env["CODE_REPO_ROOT"] = str(code_repo)  # Where to read implementation

    result = subprocess.run(
        ["python3", str(check_path)],
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def test_scheduled_missing_plan():
    """Scheduled candidate with missing target_plan → FAIL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_p = Path(tmpdir)

        # Create backlog with scheduled candidate targeting missing plan
        backlog_dir = tmpdir_p / ".agents" / "plans" / "frontier-evidence-intake"
        backlog_dir.mkdir(parents=True)
        backlog_file = backlog_dir / "BACKLOG.jsonl"

        candidate = {
            "id": "FE-TEST-A",
            "status": "scheduled",
            "target_plan": ".agents/plans/nonexistent-plan",  # Missing!
            "technique": "test",
            "claim": "test claim",
        }
        backlog_file.write_text(json.dumps(candidate) + "\n")

        # Run check
        code, stdout, stderr = run_check(tmpdir_p)

        # Should FAIL (exit 1)
        assert code == 1, f"Expected exit 1, got {code}\nstdout: {stdout}\nstderr: {stderr}"
        assert "does not exist" in stderr or "orphan fold" in stderr, f"Expected orphan error in stderr: {stderr}"
        print("✓ test_scheduled_missing_plan PASSED")


def test_scheduled_missing_folded_slice():
    """Scheduled candidate with target plan that lacks folded slice → FAIL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_p = Path(tmpdir)

        # Create backlog with scheduled candidate
        backlog_dir = tmpdir_p / ".agents" / "plans" / "frontier-evidence-intake"
        backlog_dir.mkdir(parents=True)
        backlog_file = backlog_dir / "BACKLOG.jsonl"

        plan_dir = tmpdir_p / ".agents" / "plans" / "test-plan"
        plan_dir.mkdir(parents=True)

        # Create tracker WITHOUT the folded slice
        tracker = {
            "phases": [{"id": "p0"}],
            "items": [
                {"id": "other-item", "name": "other", "kind": "slice", "phase": "p0"}
            ]
        }
        (plan_dir / "tracker.json").write_text(json.dumps(tracker, indent=2) + "\n")

        # Backlog: scheduled candidate targeting the plan
        candidate = {
            "id": "FE-TEST-B",
            "status": "scheduled",
            "target_plan": ".agents/plans/test-plan",
            "technique": "test",
            "claim": "test claim",
        }
        backlog_file.write_text(json.dumps(candidate) + "\n")

        # Run check
        code, stdout, stderr = run_check(tmpdir_p)

        # Should FAIL (exit 1) — slice is missing
        assert code == 1, f"Expected exit 1, got {code}\nstdout: {stdout}\nstderr: {stderr}"
        assert "not in that tracker" in stderr or "orphan slice" in stderr, f"Expected orphan slice error: {stderr}"
        print("✓ test_scheduled_missing_folded_slice PASSED")


def test_scheduled_properly_folded():
    """Scheduled candidate with properly folded slice in target plan → PASS."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_p = Path(tmpdir)

        # Create backlog
        backlog_dir = tmpdir_p / ".agents" / "plans" / "frontier-evidence-intake"
        backlog_dir.mkdir(parents=True)
        backlog_file = backlog_dir / "BACKLOG.jsonl"

        plan_dir = tmpdir_p / ".agents" / "plans" / "test-plan"
        plan_dir.mkdir(parents=True)

        # Create tracker WITH the folded slice
        candidate_id = "FE-TEST-C"
        folded_slice = ff.slice_from_candidate(
            {"id": candidate_id, "technique": "test", "claim": "test", "verdict": "adopt"},
            "p0"
        )
        tracker = {
            "phases": [{"id": "p0"}],
            "items": [folded_slice]
        }
        (plan_dir / "tracker.json").write_text(json.dumps(tracker, indent=2) + "\n")

        # Backlog: scheduled candidate
        candidate = {
            "id": candidate_id,
            "status": "scheduled",
            "target_plan": ".agents/plans/test-plan",
            "technique": "test",
            "claim": "test claim",
        }
        backlog_file.write_text(json.dumps(candidate) + "\n")

        # Run check
        code, stdout, stderr = run_check(tmpdir_p)

        # Should PASS (exit 0)
        assert code == 0, f"Expected exit 0, got {code}\nstdout: {stdout}\nstderr: {stderr}"
        assert "PASS" in stdout or "valid target plans" in stdout, f"Expected PASS in output: {stdout}"
        print("✓ test_scheduled_properly_folded PASSED")


def test_no_scheduled():
    """No scheduled candidates → PASS."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_p = Path(tmpdir)

        # Create empty backlog
        backlog_dir = tmpdir_p / ".agents" / "plans" / "frontier-evidence-intake"
        backlog_dir.mkdir(parents=True)
        backlog_file = backlog_dir / "BACKLOG.jsonl"

        # Backlog with only "accepted" candidate (not scheduled)
        candidate = {
            "id": "FE-TEST-D",
            "status": "accepted",
            "technique": "test",
            "claim": "test claim",
        }
        backlog_file.write_text(json.dumps(candidate) + "\n")

        # Run check
        code, stdout, stderr = run_check(tmpdir_p)

        # Should PASS (exit 0) — no scheduled items
        assert code == 0, f"Expected exit 0, got {code}\nstdout: {stdout}\nstderr: {stderr}"
        assert "no scheduled" in stdout.lower(), f"Expected 'no scheduled' in output: {stdout}"
        print("✓ test_no_scheduled PASSED")


if __name__ == "__main__":
    test_scheduled_missing_plan()
    test_scheduled_missing_folded_slice()
    test_scheduled_properly_folded()
    test_no_scheduled()
    print("\n✓ All check-frontier-fold tests passed")
