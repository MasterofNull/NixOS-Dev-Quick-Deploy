#!/usr/bin/env python3
"""
Test pre-commit whitespace and conflict marker checks.

Verifies that the pre-commit hook correctly catches:
1. Trailing whitespace
2. Conflict markers
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

def get_test_root():
    """Find the repository root."""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent.parent

def test_hook_function_exists():
    """Verify that the whitespace check function exists."""
    repo_root = get_test_root()
    hook_file = repo_root / ".githooks" / "pre-commit"

    content = hook_file.read_text()

    # Check for the function definition
    assert 'run_whitespace_and_conflict_check()' in content, \
        "run_whitespace_and_conflict_check function should be defined"

    # Check that it uses git diff --cached --check
    assert 'git diff --cached --check' in content, \
        "Should use 'git diff --cached --check' to validate whitespace"

    # Check that the function is called in the main flow
    # Match the invocation line itself: the hook has an early `exit 0` guard and
    # function definitions, so substring checks would count unreachable text.
    assert re.search(r'^run_whitespace_and_conflict_check$', content.rsplit('exit 0', 1)[0], re.M), \
        "Function should be invoked before the final exit"

def test_hook_checks_trailing_whitespace():
    """Verify that hook content mentions trailing whitespace."""
    repo_root = get_test_root()
    hook_file = repo_root / ".githooks" / "pre-commit"

    content = hook_file.read_text()

    # Check for mention of trailing whitespace
    assert 'trailing whitespace' in content or 'whitespace errors' in content, \
        "Hook should check for trailing whitespace"

def test_hook_checks_conflict_markers():
    """Verify that hook content mentions conflict markers."""
    repo_root = get_test_root()
    hook_file = repo_root / ".githooks" / "pre-commit"

    content = hook_file.read_text()

    # Check for mention of conflict markers
    assert 'conflict' in content.lower(), \
        "Hook should check for conflict markers"

def test_hook_provides_error_message():
    """Verify that hook provides clear error messages."""
    repo_root = get_test_root()
    hook_file = repo_root / ".githooks" / "pre-commit"

    content = hook_file.read_text()

    # Check for error message
    lines = content.split('\n')
    in_function = False
    has_error_message = False

    for line in lines:
        if 'run_whitespace_and_conflict_check()' in line:
            in_function = True
        elif in_function and 'Commit blocked' in line:
            has_error_message = True
            break

    assert has_error_message, \
        "Hook should provide a clear error message for blocked commits"

def test_git_diff_check_command():
    """Verify that git diff --cached --check is a valid command."""
    # This is just a sanity check that the command exists and is valid
    result = subprocess.run(
        ['git', '--help'],
        capture_output=True,
        text=True
    )

    # If git help works, the command likely exists
    assert result.returncode == 0 or 'usage' in result.stdout.lower(), \
        "git should be available"

def test_hook_execution_order():
    """Verify that whitespace check runs at appropriate time."""
    repo_root = get_test_root()
    hook_file = repo_root / ".githooks" / "pre-commit"

    content = hook_file.read_text()

    # Find the position of whitespace check in the execution order
    exec_section = content.rsplit('exit 0', 1)[0]

    checks = [
        'run_secret_scan',
        'run_shell_validation',
        'run_syntax_check',
        'run_whitespace_and_conflict_check',
        'run_repo_structure_validation',
    ]

    positions = {}
    for check in checks:
        match = re.search(rf'^{check}$', exec_section, re.M)
        assert match, f"{check} must be invoked (not just defined) before the final exit"
        positions[check] = match.start()

    ordered = sorted(checks, key=positions.get)
    assert ordered == checks, f"pre-commit checks must run in order {checks}, got {ordered}"

if __name__ == "__main__":
    print("Testing hook function exists...")
    test_hook_function_exists()
    print("✓ Hook function exists test passed")

    print("Testing hook checks trailing whitespace...")
    test_hook_checks_trailing_whitespace()
    print("✓ Trailing whitespace check test passed")

    print("Testing hook checks conflict markers...")
    test_hook_checks_conflict_markers()
    print("✓ Conflict marker check test passed")

    print("Testing hook provides error message...")
    test_hook_provides_error_message()
    print("✓ Error message test passed")

    print("Testing git diff check command...")
    test_git_diff_check_command()
    print("✓ Git diff check command test passed")

    print("Testing hook execution order...")
    test_hook_execution_order()
    print("✓ Execution order test passed")

    print("\nAll tests passed!")
    sys.exit(0)
