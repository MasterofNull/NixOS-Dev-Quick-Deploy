#!/usr/bin/env python3
"""
Phase 163 regression: local inference budget + visibility.

Verifies:
- TaskProfile.max_tokens_hint present in all 5 profiles with correct values
- _scale_timeout() scales with token budget, respects minimum, responds to LOCAL_TOK_PER_SEC
- _write_progress() creates an atomic .progress.json sidecar
- task_config._resolve_tokens() uses hint before mode default, after env vars
- DirectRunner.run() opens output file at stream start (incremental write)
- 'watch' subcommand present in dispatch.py parser
- main() calls _scale_timeout for direct-mode tasks
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "ai-stack" / "mcp-servers" / "shared"
LIB = ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(LIB))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_eq(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def _load_llm_config():
    loader = importlib.machinery.SourceFileLoader("llm_config", str(SHARED / "llm_config.py"))
    spec = importlib.util.spec_from_loader("llm_config", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _load_dispatch():
    loader = importlib.machinery.SourceFileLoader("dispatch", str(LIB / "dispatch.py"))
    spec = importlib.util.spec_from_loader("dispatch", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _load_task_config():
    loader = importlib.machinery.SourceFileLoader("task_config", str(LIB / "task_config.py"))
    spec = importlib.util.spec_from_loader("task_config", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Profile hints
# ---------------------------------------------------------------------------

def test_max_tokens_hint_in_all_profiles():
    mod = _load_llm_config()
    for name, p in mod.TASK_PROFILES.items():
        assert_true(hasattr(p, "max_tokens_hint"), f"{name}: missing max_tokens_hint")
        assert_true(p.max_tokens_hint > 0, f"{name}: max_tokens_hint must be > 0")
    print("PASS  all profiles have max_tokens_hint > 0")


def test_max_tokens_hint_values():
    mod = _load_llm_config()
    expected = {
        "lookup": 150,
        "structured": 512,
        "agent": 512,
        "code": 1200,
        "reasoning": 1800,
    }
    for task_type, hint in expected.items():
        p = mod.TASK_PROFILES[task_type]
        assert_eq(p.max_tokens_hint, hint, f"{task_type}.max_tokens_hint")
    print("PASS  profile max_tokens_hint values: lookup=150, structured=512, agent=512, code=1200, reasoning=1800")


# ---------------------------------------------------------------------------
# _scale_timeout
# ---------------------------------------------------------------------------

def test_scale_timeout_scales_with_budget():
    mod = _load_dispatch()
    # At 1 tok/s: 1200 tokens → ceil(1200/1)+60 = 1260s; > 300
    result = mod._scale_timeout(300, 1200)
    assert_true(result > 300, f"_scale_timeout(300, 1200) should exceed 300, got {result}")
    assert_eq(result, 1260, "_scale_timeout(300, 1200) at LOCAL_TOK_PER_SEC=1.0")
    print("PASS  _scale_timeout scales with token budget (1200 tok → 1260s)")


def test_scale_timeout_never_below_minimum():
    mod = _load_dispatch()
    # Small budget: 100 tokens → 160s; explicit 300 wins
    result = mod._scale_timeout(300, 100)
    assert_eq(result, 300, "_scale_timeout should not go below explicit minimum")
    print("PASS  _scale_timeout never falls below explicit minimum (300s floor)")


def test_scale_timeout_reasoning_profile():
    mod = _load_dispatch()
    # reasoning hint=1800 → ceil(1800/1)+60 = 1860s
    result = mod._scale_timeout(300, 1800)
    assert_eq(result, 1860, "_scale_timeout(300, 1800)")
    print("PASS  _scale_timeout(300, 1800) = 1860s (reasoning profile)")


def test_scale_timeout_env_calibration():
    """LOCAL_TOK_PER_SEC=2.0 should halve the computed timeout."""
    # Temporarily override the module constant
    mod = _load_dispatch()
    original = mod._LOCAL_TOK_PER_SEC
    try:
        mod._LOCAL_TOK_PER_SEC = 2.0
        # ceil(1200/2)+60 = 660; still > 300 so result = 660
        result = mod._scale_timeout(300, 1200)
        assert_eq(result, 660, "_scale_timeout at LOCAL_TOK_PER_SEC=2.0")
    finally:
        mod._LOCAL_TOK_PER_SEC = original
    print("PASS  LOCAL_TOK_PER_SEC=2.0 halves computed timeout (1200 tok → 660s)")


# ---------------------------------------------------------------------------
# _write_progress
# ---------------------------------------------------------------------------

def test_write_progress_creates_sidecar():
    mod = _load_dispatch()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "out.log.progress.json"
        mod._write_progress(p, tokens_out=45, max_tokens=1200, elapsed_s=46.0,
                            tok_per_sec=0.98, eta_s=1168.0, status="running")
        assert_true(p.exists(), ".progress.json not created by _write_progress")
        data = json.loads(p.read_text())
        assert_eq(data["status"], "running", "progress status")
        assert_eq(data["tokens_out"], 45, "progress tokens_out")
        assert_eq(data["max_tokens"], 1200, "progress max_tokens")
        assert_true("tok_per_sec" in data, "progress missing tok_per_sec")
        assert_true("eta_s" in data, "progress missing eta_s")
    print("PASS  _write_progress creates .progress.json with correct fields")


def test_write_progress_no_eta_when_done():
    mod = _load_dispatch()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "out.log.progress.json"
        mod._write_progress(p, tokens_out=1200, max_tokens=1200, elapsed_s=1230.0,
                            tok_per_sec=0.98, eta_s=None, status="done")
        data = json.loads(p.read_text())
        assert_eq(data["status"], "done", "done status")
        assert_true("eta_s" not in data, "eta_s should be absent when done")
    print("PASS  _write_progress omits eta_s when None (task done)")


def test_write_progress_atomic_no_tmp_leak():
    """The .progress.tmp scratch file must not survive after write."""
    mod = _load_dispatch()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "out.log.progress.json"
        tmp_path = p.with_suffix(".progress.tmp")
        mod._write_progress(p, tokens_out=10, max_tokens=500, elapsed_s=10.0,
                            tok_per_sec=1.0, eta_s=490.0, status="running")
        assert_true(not tmp_path.exists(), ".progress.tmp should be renamed, not left behind")
    print("PASS  _write_progress is atomic — no .tmp leak")


def test_write_progress_emits_agent_run_event():
    mod = _load_dispatch()
    saved_path = os.environ.get("AQ_AGENT_RUN_EVENTS_PATH")
    saved_root = os.environ.get("REPO_ROOT")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            event_path = Path(tmp) / "agent-run-events.jsonl"
            os.environ["AQ_AGENT_RUN_EVENTS_PATH"] = str(event_path)
            os.environ["REPO_ROOT"] = tmp
            p = Path(tmp) / "out.log.progress.json"
            mod._write_progress(
                p,
                tokens_out=10,
                max_tokens=500,
                elapsed_s=10.0,
                tok_per_sec=1.0,
                eta_s=490.0,
                status="running",
                run_id="test-progress-run",
            )
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
            latest = Path(tmp) / ".agents" / "observability" / "latest" / "test-progress-run.json"
            assert_eq(events[-1]["run_id"], "test-progress-run", "progress event run_id")
            assert_eq(events[-1]["event_type"], "model_call", "progress event type")
            assert_true(latest.exists(), "progress event latest projection missing")
    finally:
        if saved_path is None:
            os.environ.pop("AQ_AGENT_RUN_EVENTS_PATH", None)
        else:
            os.environ["AQ_AGENT_RUN_EVENTS_PATH"] = saved_path
        if saved_root is None:
            os.environ.pop("REPO_ROOT", None)
        else:
            os.environ["REPO_ROOT"] = saved_root
    print("PASS  _write_progress emits canonical agent-run event and latest projection")


def test_slot_scheduler_fails_closed_when_slot_unavailable():
    src = (LIB / "slot_scheduler.py").read_text(encoding="utf-8")
    assert_true(
        "class SlotWaitTimeout" in src,
        "slot_scheduler must expose a typed queue-wait timeout",
    )
    assert_true(
        "raise SlotWaitTimeout" in src,
        "slot_scheduler must fail closed instead of submitting when slot wait expires",
    )
    assert_true(
        "return  # /slots unavailable" not in src
        and "submit anyway" not in src,
        "slot_scheduler must not submit extra load when /slots is unavailable",
    )
    print("PASS  slot_scheduler fails closed when local slot cannot be observed free")


# ---------------------------------------------------------------------------
# task_config hint fallback
# ---------------------------------------------------------------------------

def test_task_config_hint_used_when_no_env():
    mod = _load_task_config()
    saved_direct = os.environ.pop("DIRECT_MAX_TOKENS", None)
    saved_llama = os.environ.pop("LLAMA_MAX_TOKENS", None)
    try:
        cfg = mod.TaskConfig.from_args(
            mode="direct",
            role="implementer",
            timeout_secs=300,
            max_tokens=None,
            llama_url="http://127.0.0.1:8080",
            hybrid_url="http://127.0.0.1:8003",
            ralph_url="http://127.0.0.1:8004",
            task_type="code",
            max_tokens_hint=1200,
        )
        assert_eq(cfg.max_tokens, 1200, "profile hint should be used when no env var is set")
    finally:
        if saved_direct is not None:
            os.environ["DIRECT_MAX_TOKENS"] = saved_direct
        if saved_llama is not None:
            os.environ["LLAMA_MAX_TOKENS"] = saved_llama
    print("PASS  max_tokens_hint used when no DIRECT_MAX_TOKENS/LLAMA_MAX_TOKENS env")


def test_task_config_env_overrides_hint():
    mod = _load_task_config()
    saved = os.environ.get("DIRECT_MAX_TOKENS")
    os.environ["DIRECT_MAX_TOKENS"] = "8192"
    try:
        cfg = mod.TaskConfig.from_args(
            mode="direct",
            role="implementer",
            timeout_secs=300,
            max_tokens=None,
            llama_url="http://127.0.0.1:8080",
            hybrid_url="http://127.0.0.1:8003",
            ralph_url="http://127.0.0.1:8004",
            task_type="code",
            max_tokens_hint=1200,
        )
        assert_eq(cfg.max_tokens, 8192, "DIRECT_MAX_TOKENS env must override profile hint")
    finally:
        if saved is None:
            del os.environ["DIRECT_MAX_TOKENS"]
        else:
            os.environ["DIRECT_MAX_TOKENS"] = saved
    print("PASS  DIRECT_MAX_TOKENS env overrides profile hint (env chain preserved)")


def test_task_config_explicit_overrides_hint():
    mod = _load_task_config()
    cfg = mod.TaskConfig.from_args(
        mode="direct",
        role="implementer",
        timeout_secs=300,
        max_tokens=4096,
        llama_url="http://127.0.0.1:8080",
        hybrid_url="http://127.0.0.1:8003",
        ralph_url="http://127.0.0.1:8004",
        task_type="lookup",
        max_tokens_hint=150,
    )
    assert_eq(cfg.max_tokens, 4096, "explicit max_tokens must override hint")
    print("PASS  explicit max_tokens overrides profile hint")


# ---------------------------------------------------------------------------
# Static source checks in dispatch.py
# ---------------------------------------------------------------------------

def test_incremental_write_in_direct_runner():
    """DirectRunner.run() must open the output file at stream start, not at end."""
    src = (LIB / "dispatch.py").read_text()
    # The key pattern: open(output_file, "w", ...) inside the urlopen context
    assert_true(
        'open(output_file, "w", encoding="utf-8") as out_fh' in src,
        "DirectRunner.run() must open output_file for writing at stream start (Phase 163)",
    )
    assert_true(
        "out_fh.flush()" in src,
        "DirectRunner.run() must flush after each content chunk (Phase 163)",
    )
    print("PASS  DirectRunner.run() opens output file at stream start with flush")


def test_watch_subcommand_in_parser():
    src = (LIB / "dispatch.py").read_text()
    assert_true(
        '"watch"' in src or "'watch'" in src,
        "dispatch.py must define a 'watch' subcommand",
    )
    assert_true(
        "_cmd_watch" in src,
        "dispatch.py must have a _cmd_watch handler",
    )
    print("PASS  dispatch.py has 'watch' subcommand and _cmd_watch handler")


def test_scale_timeout_called_for_direct_mode():
    src = (LIB / "dispatch.py").read_text()
    assert_true(
        "_scale_timeout" in src,
        "dispatch.py must define and call _scale_timeout",
    )
    # Verify it's called for direct mode in main()
    main_pos = src.find("def main()")
    assert_true(main_pos > 0, "main() not found in dispatch.py")
    main_body = src[main_pos:]
    assert_true(
        "_scale_timeout(" in main_body,
        "_scale_timeout() must be called in main() for direct-mode tasks",
    )
    print("PASS  _scale_timeout defined and called in main() for direct-mode tasks")


def test_progress_sidecar_update_in_direct_runner():
    src = (LIB / "dispatch.py").read_text()
    direct_runner_pos = src.find("class DirectRunner:")
    assert_true(direct_runner_pos > 0, "DirectRunner class not found")
    # Find run() method inside DirectRunner
    run_pos = src.find("def run(self, config: TaskConfig", direct_runner_pos)
    assert_true(run_pos > 0, "DirectRunner.run() not found")
    # Find the next class definition after DirectRunner to bound our search
    next_class = src.find("\nclass ", direct_runner_pos + 1)
    runner_body = src[run_pos:next_class] if next_class > 0 else src[run_pos:]
    assert_true(
        "_write_progress(" in runner_body,
        "DirectRunner.run() must call _write_progress() for sidecar updates",
    )
    assert_true(
        "except SlotWaitTimeout as exc:" in runner_body
        and '"queued_timeout"' in runner_body,
        "DirectRunner.run() must surface slot-wait timeout as queued_timeout",
    )
    assert_true(
        '"running"' in runner_body,
        "DirectRunner.run() must write 'running' status during stream",
    )
    assert_true(
        '"done"' in runner_body,
        "DirectRunner.run() must write 'done' status on completion",
    )
    print("PASS  DirectRunner.run() calls _write_progress with running/done status")


if __name__ == "__main__":
    passed = failed = 0
    tests = [
        test_max_tokens_hint_in_all_profiles,
        test_max_tokens_hint_values,
        test_scale_timeout_scales_with_budget,
        test_scale_timeout_never_below_minimum,
        test_scale_timeout_reasoning_profile,
        test_scale_timeout_env_calibration,
        test_write_progress_creates_sidecar,
        test_write_progress_no_eta_when_done,
        test_write_progress_atomic_no_tmp_leak,
        test_write_progress_emits_agent_run_event,
        test_slot_scheduler_fails_closed_when_slot_unavailable,
        test_task_config_hint_used_when_no_env,
        test_task_config_env_overrides_hint,
        test_task_config_explicit_overrides_hint,
        test_incremental_write_in_direct_runner,
        test_watch_subcommand_in_parser,
        test_scale_timeout_called_for_direct_mode,
        test_progress_sidecar_update_in_direct_runner,
    ]
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as exc:
            print(f"FAIL  {t.__name__}: {exc}")
            failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} tests passed")
    if failed:
        sys.exit(1)
