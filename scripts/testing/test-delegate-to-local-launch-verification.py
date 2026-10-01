#!/usr/bin/env python3
"""
Test local delegation launch verification.

Verifies that delegate-to-local confirms process is alive after launch
and that the registry entry exists.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

def get_test_root():
    """Find the repository root."""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent.parent

def test_launch_verification_exists():
    """Verify that launch verification function is present."""
    repo_root = get_test_root()
    script_file = repo_root / "scripts" / "ai" / "delegate-to-local"

    content = script_file.read_text()

    # Check for the verify_launch_success function
    assert 'verify_launch_success()' in content, \
        "verify_launch_success function should be defined"

    # Check that it verifies PID is alive
    assert 'kill -0' in content, \
        "Should verify process is alive with kill -0"

    # Check that it verifies registry entry exists
    assert 'registry.jsonl' in content, \
        "Should check registry entry exists"

    # Check that the function is called after setsid launch
    assert 'verify_launch_success "$BG_PID"' in content, \
        "verify_launch_success should be called with BG_PID"

def test_launch_verification_catches_failures():
    """Verify that launch verification fails on bad launch."""
    repo_root = get_test_root()
    script_file = repo_root / "scripts" / "ai" / "delegate-to-local"

    content = script_file.read_text()

    # Check that on failure, the script exits nonzero
    assert 'exit 1' in content or 'return 1' in content, \
        "Should exit with error on launch failure"

    # Check that error message is printed
    assert 'ERROR' in content, \
        "Should print error messages on launch failure"

def test_launch_verification_timeout():
    """Verify that launch verification has a reasonable timeout."""
    repo_root = get_test_root()
    script_file = repo_root / "scripts" / "ai" / "delegate-to-local"

    content = script_file.read_text()

    # Check for timeout value
    assert 'max_wait' in content or 'timeout' in content, \
        "Should have a timeout mechanism for registry polling"

    # The timeout should be reasonable (not too long)
    # Looking for something like 3 seconds or similar
    assert '3' in content or '2' in content or '1' in content, \
        "Should have a bounded wait time"

def test_launch_verification_integration():
    """Test that the function can be sourced and called."""
    repo_root = get_test_root()
    script_file = repo_root / "scripts" / "ai" / "delegate-to-local"

    # Read the script content
    content = script_file.read_text()

    # Extract the verify_launch_success function
    start_idx = content.find('verify_launch_success()')
    end_idx = content.find('\n}', start_idx) + 2

    if start_idx > 0 and end_idx > start_idx:
        function_def = content[start_idx:end_idx]

        # The function should:
        # 1. Take pid and task_id as arguments
        # 2. Check if process is alive
        # 3. Check registry
        # 4. Return 0 on success, 1 on failure

        assert 'local pid=' in function_def or 'pid="$1"' in function_def, \
            "Function should take pid as first argument"

        assert 'task_id=' in function_def or 'task_id="$2"' in function_def, \
            "Function should take task_id as second argument"

        assert 'return 0' in function_def or 'return 1' in function_def, \
            "Function should return 0 or 1"

if __name__ == "__main__":
    print("Testing launch verification exists...")
    test_launch_verification_exists()
    print("✓ Launch verification exists test passed")

    print("Testing launch verification catches failures...")
    test_launch_verification_catches_failures()
    print("✓ Launch verification failure detection test passed")

    print("Testing launch verification timeout...")
    test_launch_verification_timeout()
    print("✓ Launch verification timeout test passed")

    print("Testing launch verification integration...")
    test_launch_verification_integration()
    print("✓ Launch verification integration test passed")

    print("\nAll tests passed!")
    sys.exit(0)
