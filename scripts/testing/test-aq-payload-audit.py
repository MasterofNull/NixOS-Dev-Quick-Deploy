#!/usr/bin/env python3
"""test-aq-payload-audit — unit and integration tests for aq-payload-audit.

Self-running: `python3 scripts/testing/test-aq-payload-audit.py`
Fixtures use temp directories and CLI arg overrides.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_AUDIT_SCRIPT = _REPO / "scripts" / "ai" / "aq-payload-audit"


def run_audit(repo: Path, home: Path, *args: str) -> tuple[int, str]:
    """Run aq-payload-audit with given args, return (exit_code, output)."""
    cmd = [str(_AUDIT_SCRIPT), "--repo", str(repo), "--home", str(home)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def test_empty_repo():
    """Test 1: Empty repo should pass with no findings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        home = Path(tmpdir) / "home"
        repo.mkdir(parents=True)
        home.mkdir(parents=True)

        # Create minimal structure
        (repo / ".claude").mkdir()
        (home / ".claude").mkdir()

        exit_code, output = run_audit(repo, home, "--json")

        assert exit_code == 0, f"Expected exit 0, got {exit_code}"

        try:
            data = json.loads(output)
            assert data["summary"]["total"] == 0, "Expected 0 findings"
            print("✓ test_empty_repo passed")
        except json.JSONDecodeError:
            print(f"✗ test_empty_repo failed: invalid JSON\n{output}")
            return False

    return True


def test_claude_oversized_rules():
    """Test 2: Claude rules over 24KB triggers medium finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        home = Path(tmpdir) / "home"
        repo.mkdir(parents=True)
        home.mkdir(parents=True)

        # Create oversized CLAUDE.md
        (repo).mkdir(exist_ok=True)
        big_file = repo / "CLAUDE.md"
        big_file.write_text("x" * 30_000)  # 30KB

        (repo / ".claude").mkdir()
        (home / ".claude").mkdir()

        exit_code, output = run_audit(repo, home, "--json")

        try:
            data = json.loads(output)
            findings = data["findings"]

            # Should have at least one medium severity finding
            medium_findings = [f for f in findings if f["severity"] == "medium"]
            assert any(f["check_id"] == "1" for f in medium_findings), \
                "Expected check_id 1 medium finding"

            print("✓ test_claude_oversized_rules passed")
        except (json.JSONDecodeError, AssertionError) as e:
            print(f"✗ test_claude_oversized_rules failed: {e}")
            return False

    return True


def test_claude_memory_over_limit():
    """Test 3: Claude MEMORY.md over hard limit triggers high finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        home = Path(tmpdir) / "home"
        repo.mkdir(parents=True)
        home.mkdir(parents=True)

        (repo / ".claude").mkdir()
        memory_dir = home / ".claude" / "projects" / "-test-project" / "memory"
        memory_dir.mkdir(parents=True)

        # Create memory file over limit
        memory_content = "# Memory\n# Hard limit: 100 lines\n"
        memory_content += "\n".join([f"line {i}" for i in range(150)])

        (memory_dir / "MEMORY.md").write_text(memory_content)

        exit_code, output = run_audit(repo, home, "--json")

        try:
            data = json.loads(output)
            findings = data["findings"]

            # Should have high severity finding for check 2
            high_findings = [f for f in findings if f["severity"] == "high"]
            assert any(f["check_id"] == "2" for f in high_findings), \
                "Expected check_id 2 high finding"

            print("✓ test_claude_memory_over_limit passed")
        except (json.JSONDecodeError, AssertionError) as e:
            print(f"✗ test_claude_memory_over_limit failed: {e}")
            return False

    return True


def test_claude_hooks_large_context():
    """Test 4: Claude hooks with large additionalContext triggers medium finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        home = Path(tmpdir) / "home"
        repo.mkdir(parents=True)
        home.mkdir(parents=True)

        (repo / ".claude").mkdir()
        (home / ".claude").mkdir()

        # Create settings with large hook context
        settings = {
            "hooks": {
                "UserPromptSubmit": {
                    "my-handler": {
                        "additionalContext": "x" * 1000  # 1000 bytes
                    }
                }
            }
        }

        (repo / ".claude" / "settings.json").write_text(json.dumps(settings))

        exit_code, output = run_audit(repo, home, "--json")

        try:
            data = json.loads(output)
            findings = data["findings"]

            # Should have medium finding for check 3
            medium_findings = [f for f in findings if f["severity"] == "medium"]
            assert any(f["check_id"] == "3" for f in medium_findings), \
                "Expected check_id 3 medium finding"

            print("✓ test_claude_hooks_large_context passed")
        except (json.JSONDecodeError, AssertionError) as e:
            print(f"✗ test_claude_hooks_large_context failed: {e}")
            return False

    return True


def test_codex_oversized_agents():
    """Test 5: Codex AGENTS.md over 32KB triggers high finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        home = Path(tmpdir) / "home"
        repo.mkdir(parents=True)
        home.mkdir(parents=True)

        (repo / ".claude").mkdir()
        (home / ".claude").mkdir()

        # Create oversized AGENTS.md
        (repo / "AGENTS.md").write_text("x" * 40_000)  # 40KB

        exit_code, output = run_audit(repo, home, "--json")

        try:
            data = json.loads(output)
            findings = data["findings"]

            # Should have high finding for check 5a
            high_findings = [f for f in findings if f["severity"] == "high"]
            assert any(f["check_id"] == "5a" for f in high_findings), \
                "Expected check_id 5a high finding"

            print("✓ test_codex_oversized_agents passed")
        except (json.JSONDecodeError, AssertionError) as e:
            print(f"✗ test_codex_oversized_agents failed: {e}")
            return False

    return True


def test_local_thinking_enabled():
    """Test 6: Local with enable_thinking=True in profiles triggers high finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        home = Path(tmpdir) / "home"
        repo.mkdir(parents=True)
        home.mkdir(parents=True)

        (repo / ".claude").mkdir()
        (home / ".claude").mkdir()

        # Create llm_config with bad thinking
        llm_config_content = '''
TASK_PROFILES = {
    "research": TaskProfile(
        name="research",
        enable_thinking=True,
        thinking_budget=100,
    ),
}
'''

        config_dir = repo / "ai-stack" / "mcp-servers" / "shared"
        config_dir.mkdir(parents=True)
        (config_dir / "llm_config.py").write_text(llm_config_content)

        exit_code, output = run_audit(repo, home, "--json")

        try:
            data = json.loads(output)
            findings = data["findings"]

            # Should have high finding for check 7a
            high_findings = [f for f in findings if f["severity"] == "high"]
            assert any(f["check_id"] == "7a" for f in high_findings), \
                "Expected check_id 7a high finding"

            print("✓ test_local_thinking_enabled passed")
        except (json.JSONDecodeError, AssertionError) as e:
            print(f"✗ test_local_thinking_enabled failed: {e}")
            return False

    return True


def test_rounds_missing_shared_flag():
    """Test 7: Rounds without --shared in codex dispatch triggers high finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        home = Path(tmpdir) / "home"
        repo.mkdir(parents=True)
        home.mkdir(parents=True)

        (repo / ".claude").mkdir()
        (home / ".claude").mkdir()

        # Create aq-collab-round without --shared
        collab_script = '''#!/bin/bash
cmd = ["bash", str(SCRIPTS / "delegate-to-codex"), "--mode", "edit",
       "--prompt-file", str(prompt_file)]
'''

        scripts_dir = repo / "scripts" / "ai"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "aq-collab-round").write_text(collab_script)

        exit_code, output = run_audit(repo, home, "--json")

        try:
            data = json.loads(output)
            findings = data["findings"]

            # Should have high finding for check 8
            high_findings = [f for f in findings if f["severity"] == "high"]
            assert any(f["check_id"] == "8" for f in high_findings), \
                "Expected check_id 8 high finding"

            print("✓ test_rounds_missing_shared_flag passed")
        except (json.JSONDecodeError, AssertionError) as e:
            print(f"✗ test_rounds_missing_shared_flag failed: {e}")
            return False

    return True


def test_fail_on_high():
    """Test 8: --fail-on high exits 1 when high severity found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        home = Path(tmpdir) / "home"
        repo.mkdir(parents=True)
        home.mkdir(parents=True)

        (repo / ".claude").mkdir()
        (home / ".claude").mkdir()

        # Create oversized CLAUDE.md to trigger high finding
        (repo / "CLAUDE.md").write_text("x" * 50_000)

        exit_code, output = run_audit(repo, home, "--fail-on", "high")

        assert exit_code == 1, f"Expected exit 1 for high severity, got {exit_code}"
        print("✓ test_fail_on_high passed")

    return True


def test_human_output_format():
    """Test 9: Human table output is readable and contains expected info."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        home = Path(tmpdir) / "home"
        repo.mkdir(parents=True)
        home.mkdir(parents=True)

        (repo / ".claude").mkdir()
        (home / ".claude").mkdir()
        (repo / "CLAUDE.md").write_text("x" * 30_000)

        exit_code, output = run_audit(repo, home)

        assert exit_code == 0, "Expected exit 0"
        assert "CLAUDE" in output or "✓ All checks passed" in output, \
            "Expected lane header or pass message"

        print("✓ test_human_output_format passed")

    return True


def test_real_repo_smoke():
    """Test 10: Smoke test against real repo (shouldn't crash)."""
    exit_code, output = run_audit(_REPO, Path.home())

    # Just check it doesn't crash and returns valid JSON/output
    assert exit_code in (0, 1), f"Unexpected exit code {exit_code}"

    # Try to parse JSON if --json was run with fixtures
    if "findings" in output or "total" in output:
        try:
            data = json.loads(output)
            assert "findings" in data or "total" in data, "Missing expected fields"
        except json.JSONDecodeError:
            pass  # Human table output is okay too

    print("✓ test_real_repo_smoke passed")
    return True


def main() -> int:
    """Run all tests."""
    tests = [
        test_empty_repo,
        test_claude_oversized_rules,
        test_claude_memory_over_limit,
        test_claude_hooks_large_context,
        test_codex_oversized_agents,
        test_local_thinking_enabled,
        test_rounds_missing_shared_flag,
        test_fail_on_high,
        test_human_output_format,
        test_real_repo_smoke,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            result = test()
            if result or result is None:  # None means printed ok inside
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} crashed: {e}")
            failed += 1

    print(f"\n{passed}/{len(tests)} tests passed")

    if failed == 0:
        print(f"✓ All {len(tests)} tests passed")
        return 0
    else:
        print(f"✗ {failed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
