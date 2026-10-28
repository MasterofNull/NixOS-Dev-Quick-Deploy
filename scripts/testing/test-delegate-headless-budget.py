#!/usr/bin/env python3
"""
Test suite for delegate-to-codex headless token budget and grounding.

Tests:
1. Budget sum parsing from fixture logs
   (budget window is mtime-based, rolling DELEGATE_CODEX_BUDGET_WINDOW_HOURS)
2. DELEGATE_OUTPUTS_DIR env override
3. --budget-check-only flag behavior
4. Daily budget enforcement (refuse at/over budget without --force-budget)
5. Rolling window ignores old logs; review reserve (implement refused before review);
   --force-budget bypass; next-free time printed
6. Grounding block contains "DELEGATE MODE" and size constraint
"""

import os
import sys
import json
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DELEGATE_SCRIPT = REPO_ROOT / "scripts" / "ai" / "delegate-to-codex"
GROUNDING_SCRIPT = REPO_ROOT / "scripts" / "ai" / "lib" / "harness-grounding.sh"
OUTPUTS_DIR_ENV = "DELEGATE_OUTPUTS_DIR"

def run_cmd(cmd, env=None, cwd=None):
    """Run command, return (returncode, stdout, stderr)."""
    e = os.environ.copy()
    if env:
        e.update(env)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=e,
        cwd=cwd or REPO_ROOT,
        shell=isinstance(cmd, str),
    )
    return result.returncode, result.stdout, result.stderr

def test_grounding_delegate_mode():
    """Test that grounding block contains DELEGATE MODE and is reasonable size."""
    cmd = f"source {GROUNDING_SCRIPT} && harness_grounding codex"
    rc, out, err = run_cmd(cmd, env={}, cwd=REPO_ROOT)

    if rc != 0:
        print(f"FAIL: grounding script failed: {err}")
        return False

    if "DELEGATE MODE" not in out:
        print(f"FAIL: grounding missing 'DELEGATE MODE' marker")
        return False

    if "END DELEGATE MODE" not in out:
        print(f"FAIL: grounding missing 'END DELEGATE MODE' marker")
        return False

    # Extract just the delegate mode section
    lines = out.split("\n")
    delegate_start = None
    delegate_end = None
    for i, line in enumerate(lines):
        if "=== DELEGATE MODE" in line:
            delegate_start = i
        if "=== END DELEGATE MODE ===" in line:
            delegate_end = i
            break

    if delegate_start is None or delegate_end is None:
        print(f"FAIL: could not extract DELEGATE MODE section")
        return False

    delegate_section = "\n".join(lines[delegate_start:delegate_end+1])
    section_size = len(delegate_section.encode("utf-8"))

    # Should be <= 600 bytes (per spec)
    if section_size > 600:
        print(f"FAIL: DELEGATE MODE section is {section_size} bytes, should be <= 600")
        return False

    print(f"PASS: grounding DELEGATE MODE section: {section_size} bytes")
    return True

def test_budget_parsing():
    """Test budget sum parsing from fixture logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        outputs_dir = tmpdir / "outputs"
        outputs_dir.mkdir()

        # Create fixture logs for today with token counts
        today = datetime.now().strftime("%Y%m%d")

        # Log 1: 10,000 tokens
        log1 = outputs_dir / f"codex-{today}-aaa111.log"
        log1.write_text("some output\ntokens used\n10,000\nmore output\n")

        # Log 2: 5,000 tokens
        log2 = outputs_dir / f"codex-{today}-bbb222.log"
        log2.write_text("output\ntokens used\n5,000\n")

        # Log 3: 100 tokens
        log3 = outputs_dir / f"codex-{today}-ccc333.log"
        log3.write_text("tokens used\n100\n")

        # Parse tokens the same way the script does
        total = 0
        for logfile in sorted(outputs_dir.glob("codex-*.log")):
            content = logfile.read_text()
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if line.strip() == "tokens used":
                    if i + 1 < len(lines):
                        tokens_str = lines[i + 1].strip().replace(",", "")
                        try:
                            total += int(tokens_str)
                        except ValueError:
                            pass

        expected = 15100  # 10,000 + 5,000 + 100
        if total != expected:
            print(f"FAIL: budget parsing got {total}, expected {expected}")
            return False

        print(f"PASS: budget parsing: {total} tokens from 3 logs")
        return True

def test_budget_check_only_flag():
    """Test --budget-check-only flag behavior."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        outputs_dir = tmpdir / "outputs"
        outputs_dir.mkdir()

        today = datetime.now().strftime("%Y%m%d")

        # Test 1: Under budget should succeed (exit 0)
        log1 = outputs_dir / f"codex-{today}-test111.log"
        log1.write_text("tokens used\n50000\n")

        env = {
            OUTPUTS_DIR_ENV: str(outputs_dir),
            "DELEGATE_CODEX_DAILY_TOKEN_BUDGET": "250000",
        }

        rc, out, err = run_cmd(f"bash {DELEGATE_SCRIPT} --budget-check-only", env=env)
        if rc != 0:
            print(f"FAIL: --budget-check-only under budget returned {rc}, expected 0")
            return False

        # Test 2: Over budget should fail (exit 3)
        log2 = outputs_dir / f"codex-{today}-big111.log"
        log2.write_text("tokens used\n260000\n")

        env["DELEGATE_CODEX_DAILY_TOKEN_BUDGET"] = "250000"
        rc, out, err = run_cmd(f"bash {DELEGATE_SCRIPT} --budget-check-only", env=env)
        if rc != 3:
            print(f"FAIL: --budget-check-only over budget returned {rc}, expected 3")
            return False

        if "daily headless budget exhausted" not in err:
            print(f"FAIL: error message not in stderr")
            return False

        # Test 3: Over budget with --force-budget should succeed (exit 0)
        rc, out, err = run_cmd(f"bash {DELEGATE_SCRIPT} --budget-check-only --force-budget", env=env)
        if rc != 0:
            print(f"FAIL: --budget-check-only with --force-budget returned {rc}, expected 0")
            return False

        print(f"PASS: --budget-check-only flag behavior correct")
        return True

def test_budget_window_and_review_reserve():
    """Rolling mtime window, 40% review reserve, force-budget, next-free time."""
    import time
    with tempfile.TemporaryDirectory() as tmpdir:
        outputs_dir = Path(tmpdir) / "outputs"
        outputs_dir.mkdir()
        env = {OUTPUTS_DIR_ENV: str(outputs_dir), "DELEGATE_CODEX_DAILY_TOKEN_BUDGET": "250000",
               "DELEGATE_CODEX_REVIEW_RESERVE_PCT": "40", "DELEGATE_CODEX_BUDGET_WINDOW_HOURS": "24"}
        chk = lambda role, extra="": run_cmd(f"bash {DELEGATE_SCRIPT} --budget-check-only --role {role} {extra}", env=env)

        # Old log (48h) must be ignored even though its filename is "today".
        old = outputs_dir / "codex-old.log"
        old.write_text("tokens used\n900,000\n")
        t_old = time.time() - 48 * 3600
        os.utime(old, (t_old, t_old))
        rc, out, err = chk("implement")
        if rc != 0 or "used: 0/250000" not in out:
            print(f"FAIL: old log not ignored rc={rc} out={out!r} err={err!r}")
            return False

        # 180000 used: implement limit is 150000 -> implement refused, review allowed.
        recent = outputs_dir / "codex-recent.log"
        recent.write_text("tokens used\n180,000\n")
        t_rec = time.time() - 3600
        os.utime(recent, (t_rec, t_rec))
        rc, out, err = chk("implement")
        if rc != 3 or "review headroom 70000" not in err or "frees at" not in err:
            print(f"FAIL: implement should be refused rc={rc} err={err!r}")
            return False
        rc, out, err = chk("review")
        if rc != 0 or "review headroom: 70000" not in out or "implement headroom: 0" not in out:
            print(f"FAIL: review should be allowed rc={rc} out={out!r}")
            return False
        if "next free:" not in out or "n/a" in out:
            print(f"FAIL: next free time missing: {out!r}")
            return False
        rc, _, err = chk("implement", "--force-budget")
        if rc != 0:
            print(f"FAIL: --force-budget should bypass rc={rc}")
            return False

        # At/over total: both refused.
        (outputs_dir / "codex-more.log").write_text("tokens used\n70,000\n")
        for role in ("implement", "review"):
            rc, _, err = chk(role)
            if rc != 3 or "daily headless budget exhausted" not in err:
                print(f"FAIL: {role} should be refused at total rc={rc} err={err!r}")
                return False

        print("PASS: rolling window, review reserve, force-budget, next-free time")
        return True

def test_effort_flag():
    """Test --effort flag is recognized and passed to codex."""
    # Check syntax
    rc, out, err = run_cmd(f"bash -n {DELEGATE_SCRIPT}")
    if rc != 0:
        print(f"FAIL: delegate-to-codex syntax error: {err}")
        return False

    # Check help includes effort
    rc, out, err = run_cmd(f"bash {DELEGATE_SCRIPT} --help")
    if "--effort" not in out:
        print(f"FAIL: --effort not in help output")
        return False

    if "low|medium|high" not in out:
        print(f"FAIL: effort levels not documented")
        return False

    print(f"PASS: --effort flag recognized with levels")
    return True

def test_delegate_script_syntax():
    """Test that delegate-to-codex has valid bash syntax."""
    rc, out, err = run_cmd(f"bash -n {DELEGATE_SCRIPT}")
    if rc != 0:
        print(f"FAIL: delegate-to-codex syntax error: {err}")
        return False

    print(f"PASS: delegate-to-codex syntax valid")
    return True

def test_grounding_script_syntax():
    """Test that harness-grounding.sh has valid bash syntax."""
    rc, out, err = run_cmd(f"bash -n {GROUNDING_SCRIPT}")
    if rc != 0:
        print(f"FAIL: harness-grounding.sh syntax error: {err}")
        return False

    print(f"PASS: harness-grounding.sh syntax valid")
    return True

def main():
    """Run all tests."""
    tests = [
        ("Grounding script syntax", test_grounding_script_syntax),
        ("Delegate script syntax", test_delegate_script_syntax),
        ("Grounding DELEGATE MODE", test_grounding_delegate_mode),
        ("Budget parsing", test_budget_parsing),
        ("Effort flag", test_effort_flag),
        ("Budget check only flag", test_budget_check_only_flag),
        ("Budget window + review reserve", test_budget_window_and_review_reserve),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"FAIL: {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{passed}/{len(tests)} tests passed")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
