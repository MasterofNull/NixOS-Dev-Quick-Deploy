#!/usr/bin/env python3
"""Focused test suite for Frontier FE-2a functional eval metric baseline.

Tests:
1. Canonical task definitions and prompt variables integrity.
2. Code block extraction from markdown fences, plain text, and prose.
3. Sandboxed execution safety, syntax error trapping, and assertion failures.
4. Headroom observability: 1.0 on reference, 0.0 on flawed, and graded scores in (0, 1).
5. CLI execution semantics (--dry-run, --json, --verbose, --mock-ratio).
6. Dashboard health summary and capability enforcement integration.
7. QA check 0.10.64 registration.
"""
from __future__ import annotations

import os
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import functional_eval as fe  # noqa: E402

AQ_FUNCTIONAL_EVAL = ROOT / "scripts/ai/aq-functional-eval"
AQ_PROMPT_EVAL = ROOT / "scripts/ai/aq-prompt-eval"
AISTACK_ROUTE = ROOT / "dashboard/backend/api/routes/aistack.py"
DASHBOARD_JS = ROOT / "assets/dashboard.js"
PHASE0_PY = ROOT / "scripts/testing/harness_qa/phases/phase0.py"
QA_BASH = ROOT / "scripts/ai/_aq-qa-bash"


def assert_true(condition: bool, msg: str) -> None:
    if not condition:
        raise AssertionError(msg)


def test_task_registry() -> None:
    assert_true(len(fe.FUNCTIONAL_TASKS) >= 5, "expected at least 5 canonical functional tasks")
    names = {t.name for t in fe.FUNCTIONAL_TASKS}
    required = {"clamp", "slugify", "evens", "mean", "dedupe", "service_hardening"}
    assert_true(required.issubset(names), f"missing required tasks: {required - names}")

    for t in fe.FUNCTIONAL_TASKS:
        assert_true(bool(t.description), f"task {t.name} missing description")
        assert_true("task_description" in t.prompt_variables, f"task {t.name} missing task_description variable")
        assert_true(bool(t.check_script), f"task {t.name} missing check_script")
        assert_true(bool(t.reference_code), f"task {t.name} missing reference_code")
        assert_true(bool(t.flawed_code), f"task {t.name} missing flawed_code")
    print("PASS: canonical task registry integrity")


def test_code_extraction() -> None:
    # 1. Python fenced block
    t1 = "Here is the code:\n```python\ndef foo():\n    return 1\n```\nEnjoy!"
    assert_true(fe.extract_code_block(t1) == "def foo():\n    return 1", "python fence extraction failed")

    # 2. Generic fenced block
    t2 = "```\ndef bar():\n    return 2\n```"
    assert_true(fe.extract_code_block(t2) == "def bar():\n    return 2", "generic fence extraction failed")

    # 3. Raw code
    t3 = "def baz():\n    return 3"
    assert_true(fe.extract_code_block(t3) == "def baz():\n    return 3", "raw code extraction failed")
    print("PASS: code block extraction")


def test_sandboxed_execution() -> None:
    # 1. Reference code passes
    for t in fe.FUNCTIONAL_TASKS:
        ok, errs = fe.execute_functional_check(t.reference_code, t.check_script)
        assert_true(ok is True and not errs, f"reference code failed for {t.name}: {errs}")

    # 2. Flawed code fails
    for t in fe.FUNCTIONAL_TASKS:
        ok, errs = fe.execute_functional_check(t.flawed_code, t.check_script)
        assert_true(ok is False and len(errs) > 0, f"flawed code unexpectedly passed for {t.name}")

    # 3. Syntax error trapped safely
    ok, errs = fe.execute_functional_check("def broken(: pass", "assert True")
    assert_true(ok is False and "Syntax error" in errs[0], "syntax error not trapped")

    # 4. Runtime error trapped safely
    ok, errs = fe.execute_functional_check("raise RuntimeError('kaboom')", "assert True")
    assert_true(ok is False and "RuntimeError" in errs[0], "runtime exception not trapped")

    # 5. Empty code trapped safely
    ok, errs = fe.execute_functional_check("   ", "assert True")
    assert_true(ok is False and "empty code output" in errs[0], "empty code not trapped")
    print("PASS: sandboxed execution and error trapping")


def test_sandbox_hardening() -> None:
    if not fe.sandbox_available():
        print("SKIP: sandbox hardening (bwrap unavailable)")
        return
    chk = "assert m.f() == 1"
    forged = 'print(\'\\n@@RESULT@@{"ok": true, "failures": []}\')\nimport os\nos._exit(0)\ndef f(): return 2'
    ok, _ = fe.execute_functional_check(forged, chk)
    assert_true(ok is False, "marker forgery + os._exit self-passed")
    ok, _ = fe.execute_functional_check("raise SystemExit(0)\ndef f(): return 2", chk)
    assert_true(ok is False, "SystemExit(0) self-passed")
    for probe in (
        "import sys, json\nn = sys.modules['__main__']._nonce\nprint('\\n' + n + json.dumps({'ok': True, 'failures': []}))\nimport os\nos._exit(0)\ndef f(): return 2",
        "import sys, json, os\nn = sys._getframe(1).f_globals['_nonce']\nprint('\\n' + n + json.dumps({'ok': True, 'failures': []}))\nos._exit(0)\ndef f(): return 2",
    ):
        ok, errs = fe.execute_functional_check(probe, chk)
        assert_true(ok is False, f"nonce probe self-passed: {errs}")
    os.environ["AQ_SECRET_PROBE"] = "leak"
    ok, errs = fe.execute_functional_check(
        "import os\ndef f(): return 1 if 'AQ_SECRET_PROBE' not in os.environ else 2", chk)
    assert_true(ok is True, f"parent env visible in sandbox: {errs}")
    ok, errs = fe.execute_functional_check("open('/etc/aq_pwn','w')\ndef f(): return 1", chk)
    assert_true(ok is False and not os.path.exists("/etc/aq_pwn"), "host write not contained")
    ok, errs = fe.execute_functional_check("import socket\nsocket.socket().connect(('1.1.1.1',80))\ndef f(): return 1", chk)
    assert_true(ok is False, "network not blocked")
    ok, errs = fe.execute_functional_check("x = bytearray(4 * 1024**3)\ndef f(): return 1", chk)
    assert_true(ok is False, "large allocation not limited")
    ok, errs = fe.execute_functional_check("import sys\nsys.stdout.write('A' * (64 * 1024**2))\ndef f(): return 1", chk, timeout_s=15)
    assert_true(ok is False, "huge stdout not rejected")
    print("PASS: sandbox hardening (forgery, env, containment, rlimits)")


def test_headroom_and_mock_evaluation() -> None:
    # 1. All reference = 1.0 score, 0.0 headroom
    r_all = fe.evaluate_tasks_mock()
    assert_true(r_all["score"] == 1.0, f"expected 1.0, got {r_all['score']}")
    assert_true(r_all["headroom"] == 0.0, f"expected 0.0, got {r_all['headroom']}")
    assert_true(r_all["tasks_passed"] == r_all["tasks_evaluated"], "all tasks should pass")

    # 2. All flawed = 0.0 score, 1.0 headroom
    r_none = fe.evaluate_tasks_mock(pass_indices=[])
    assert_true(r_none["score"] == 0.0, f"expected 0.0, got {r_none['score']}")
    assert_true(r_none["headroom"] == 1.0, f"expected 1.0, got {r_none['headroom']}")
    assert_true(r_none["tasks_passed"] == 0, "no tasks should pass")

    # 3. Graded evaluation = proves headroom detection for GEPA
    r_half = fe.evaluate_tasks_mock(pass_indices=[0, 1, 2])
    assert_true(0.0 < r_half["score"] < 1.0, f"expected intermediate score, got {r_half['score']}")
    assert_true(r_half["headroom"] > 0.0, f"expected positive headroom, got {r_half['headroom']}")
    print("PASS: headroom observability and mock evaluation")


def test_cli_execution() -> None:
    assert_true(AQ_FUNCTIONAL_EVAL.is_file(), "aq-functional-eval must exist")
    assert_true(AQ_PROMPT_EVAL.is_file(), "aq-prompt-eval must exist")

    # 1. Dry run output
    res = subprocess.run(
        [sys.executable, str(AQ_FUNCTIONAL_EVAL), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert_true(res.returncode == 0, f"aq-functional-eval --dry-run failed: {res.stderr}")
    assert_true("FE-2a Functional Eval" in res.stdout, "expected header in stdout")
    assert_true("Headroom:" in res.stdout, "expected headroom in stdout")

    # 2. JSON output
    res_json = subprocess.run(
        [sys.executable, str(AQ_FUNCTIONAL_EVAL), "--dry-run", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert_true(res_json.returncode == 0, f"aq-functional-eval --json failed: {res_json.stderr}")
    data = json.loads(res_json.stdout)
    assert_true(data["metric"] == "functional_eval", f"wrong metric: {data.get('metric')}")
    assert_true(data["target_prompt"] == "aider_task_systems_code", f"wrong prompt: {data.get('target_prompt')}")
    assert_true(isinstance(data["score"], (int, float)), "score must be numeric")
    assert_true(isinstance(data["headroom"], (int, float)), "headroom must be numeric")
    assert_true(len(data["results"]) == data["tasks_evaluated"], "results count mismatch")

    # 3. Simulated ratio
    res_ratio = subprocess.run(
        [sys.executable, str(AQ_FUNCTIONAL_EVAL), "--dry-run", "--mock-ratio", "0.5", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert_true(res_ratio.returncode == 0, "mock-ratio run failed")
    data_ratio = json.loads(res_ratio.stdout)
    assert_true(data_ratio["score"] == 0.5, f"expected 0.5 score, got {data_ratio['score']}")
    assert_true(data_ratio["headroom"] == 0.5, f"expected 0.5 headroom, got {data_ratio['headroom']}")
    print("PASS: CLI execution semantics")


def test_dashboard_and_coverage() -> None:
    hs = fe.health_summary()
    assert_true(hs["available"] is True, "functional eval should be available")
    assert_true(hs["status"] == "ok", "status should be ok")
    assert_true(hs["baseline_ready"] is True, "baseline should be ready")
    assert_true(hs["headroom_observable"] is True, "headroom should be observable")

    # Check dashboard backend route file contains _functional_eval_health_summary
    route_text = AISTACK_ROUTE.read_text(encoding="utf-8")
    assert_true("_functional_eval_health_summary" in route_text, "aistack.py missing _functional_eval_health_summary")
    assert_true('"functional_eval"' in route_text, "aistack.py capability_gap missing functional_eval")

    # Check dashboard frontend JS contains functional eval row
    js_text = DASHBOARD_JS.read_text(encoding="utf-8")
    assert_true("· functional eval baseline" in js_text, "dashboard.js missing · functional eval baseline row")

    # Check phase0.py QA check exists
    phase0_text = PHASE0_PY.read_text(encoding="utf-8")
    assert_true("0.10.64" in phase0_text, "phase0.py missing check 0.10.64")
    assert_true("_check_frontier_fe2a_functional_eval" in phase0_text, "phase0.py missing _check_frontier_fe2a_functional_eval")

    # Check _aq-qa-bash contains 0.10.64
    bash_text = QA_BASH.read_text(encoding="utf-8")
    assert_true("0.10.64" in bash_text, "_aq-qa-bash missing check 0.10.64")
    print("PASS: dashboard visibility and QA coverage")


def main() -> int:
    test_task_registry()
    test_code_extraction()
    test_sandboxed_execution()
    test_sandbox_hardening()
    test_headroom_and_mock_evaluation()
    test_cli_execution()
    test_dashboard_and_coverage()
    print("\nALL 6 FIXTURES PASS: Frontier FE-2a functional eval metric baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
