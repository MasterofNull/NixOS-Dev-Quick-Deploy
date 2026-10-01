#!/usr/bin/env python3
"""
Regression test for Codex shared-mode write authorization.

Tests that:
1. --print-argv prints the constructed codex command without executing
2. Shared mode (--shared) does not use isolated worktree isolation
3. Edit mode (--mode edit) with shared mode is rejected upfront
"""

import subprocess
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
DELEGATE_CODEX = REPO_ROOT / "scripts" / "ai" / "delegate-to-codex"


def run_delegate(args):
    """Run delegate-to-codex and return stdout."""
    cmd = [str(DELEGATE_CODEX)] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "TIMEOUT"


def test_print_argv_no_execution():
    """Test that --print-argv prints argv without executing codex."""
    rc, stdout, stderr = run_delegate(
        [
            "--print-argv",
            "--prompt",
            "test prompt",
            "--mode",
            "safe",
        ]
    )
    assert rc == 0, f"Expected rc=0, got {rc}. stderr={stderr}"
    lines = stdout.strip().split("\n")
    # Should print at least: CODEX_BIN, "exec", prompt
    assert len(lines) >= 3, f"Expected at least 3 argv lines, got {len(lines)}: {lines}"
    assert lines[0].endswith("codex") or "codex" in lines[0], f"First arg not codex: {lines[0]}"
    assert lines[1] == "exec", f"Second arg not 'exec': {lines[1]}"
    print("✓ test_print_argv_no_execution passed")


def test_print_argv_with_shared_mode():
    """Test that shared mode includes -C flag with repo root."""
    rc, stdout, stderr = run_delegate(
        [
            "--print-argv",
            "--prompt",
            "analyze only",
            "--shared",
            "--mode",
            "safe",
        ]
    )
    assert rc == 0, f"Expected rc=0, got {rc}. stderr={stderr}"
    lines = stdout.strip().split("\n")
    # In shared mode, should have -C flag followed by REPO_ROOT
    assert "-C" in lines, f"Shared mode missing -C flag: {lines}"
    c_index = lines.index("-C")
    assert c_index + 1 < len(lines), f"Expected REPO_ROOT after -C: {lines}"
    # The next line should be the repo root path (containing 'NixOS-Dev-Quick-Deploy')
    assert "NixOS-Dev-Quick-Deploy" in lines[c_index + 1], f"Missing repo root after -C: {lines[c_index+1]}"
    # Should NOT reference worktrees (only used in isolated mode)
    argv_line = " ".join(lines)
    assert "worktrees" not in argv_line, f"Shared mode should not reference worktree: {argv_line}"
    print("✓ test_print_argv_with_shared_mode passed")


def test_shared_edit_rejected():
    """Test that --shared --mode edit is rejected immediately."""
    rc, stdout, stderr = run_delegate(
        [
            "--prompt",
            "edit something",
            "--shared",
            "--mode",
            "edit",
        ]
    )
    assert rc != 0, f"Expected failure for --shared --mode edit, got rc={rc}"
    assert "shared editing is not authorized" in stderr, f"Expected error message, got: {stderr}"
    print("✓ test_shared_edit_rejected passed")


def test_print_argv_respects_model_override():
    """Test that --model flag is included in argv."""
    rc, stdout, stderr = run_delegate(
        [
            "--print-argv",
            "--prompt",
            "test",
            "--model",
            "gpt-6-test",
        ]
    )
    assert rc == 0, f"Expected rc=0, got {rc}"
    argv_text = stdout.strip()
    assert "gpt-6-test" in argv_text or "-m" in argv_text, f"Model not in argv: {argv_text}"
    print("✓ test_print_argv_respects_model_override passed")


def test_print_argv_with_reasoning_effort():
    """Test that --effort flag is included in argv."""
    rc, stdout, stderr = run_delegate(
        [
            "--print-argv",
            "--prompt",
            "test",
            "--effort",
            "high",
        ]
    )
    assert rc == 0, f"Expected rc=0, got {rc}"
    argv_text = stdout.strip()
    # effort != "medium" should add -c model_reasoning_effort=high
    assert "high" in argv_text or "model_reasoning_effort" in argv_text, f"Effort not in argv: {argv_text}"
    print("✓ test_print_argv_with_reasoning_effort passed")


if __name__ == "__main__":
    try:
        test_print_argv_no_execution()
        test_print_argv_with_shared_mode()
        test_shared_edit_rejected()
        test_print_argv_respects_model_override()
        test_print_argv_with_reasoning_effort()
        print("\n✓ All tests passed")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
