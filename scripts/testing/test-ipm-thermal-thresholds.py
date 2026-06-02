#!/usr/bin/env python3
"""Regression coverage for Phase 99.1 IPM thermal threshold env var support."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IPM_PATH = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "inference_param_manager.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_ipm(**env_overrides):
    """Load IPM module with optional env var overrides."""
    for k, v in env_overrides.items():
        os.environ[k] = str(v)
    loader = importlib.machinery.SourceFileLoader("ipm", str(IPM_PATH))
    spec = importlib.util.spec_from_loader("ipm", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    for k in env_overrides:
        os.environ.pop(k, None)
    return mod


def test_default_thresholds():
    """83/73/88 defaults unblock batch at 81°C Renoir Tctl."""
    mod = _load_ipm()
    ipm = mod.InferenceParamManager()
    # 81°C — Renoir APU normal idle, must be "warn" not "critical" with new defaults
    ipm._state.temp_cpu_c = 81.0
    ipm._state.temp_gpu_c = None
    tier = ipm._determine_thermal_tier()
    assert_true(tier == "warn", f"81°C should be 'warn' with default 83°C critical threshold, got '{tier}'")


def test_critical_at_threshold():
    mod = _load_ipm()
    ipm = mod.InferenceParamManager()
    ipm._state.temp_cpu_c = 83.0
    ipm._state.temp_gpu_c = None
    tier = ipm._determine_thermal_tier()
    assert_true(tier == "critical", f"83°C exactly should be 'critical', got '{tier}'")


def test_shutdown_at_88():
    mod = _load_ipm()
    ipm = mod.InferenceParamManager()
    ipm._state.temp_cpu_c = 88.0
    ipm._state.temp_gpu_c = None
    tier = ipm._determine_thermal_tier()
    assert_true(tier == "shutdown", f"88°C should be 'shutdown', got '{tier}'")


def test_optimal_below_warn():
    mod = _load_ipm()
    ipm = mod.InferenceParamManager()
    ipm._state.temp_cpu_c = 70.0
    ipm._state.temp_gpu_c = None
    tier = ipm._determine_thermal_tier()
    assert_true(tier == "optimal", f"70°C should be 'optimal' with 73°C warn threshold, got '{tier}'")


def test_env_override_critical():
    """THERMAL_CRITICAL_C env var is respected."""
    mod = _load_ipm(THERMAL_CRITICAL_C="90")
    ipm = mod.InferenceParamManager()
    ipm._state.temp_cpu_c = 85.0
    ipm._state.temp_gpu_c = None
    tier = ipm._determine_thermal_tier()
    assert_true(tier != "critical", f"85°C should not be 'critical' when THERMAL_CRITICAL_C=90, got '{tier}'")


def test_no_temps_returns_unknown():
    mod = _load_ipm()
    ipm = mod.InferenceParamManager()
    ipm._state.temp_cpu_c = None
    ipm._state.temp_gpu_c = None
    tier = ipm._determine_thermal_tier()
    assert_true(tier == "unknown", f"no sensors should return 'unknown', got '{tier}'")


if __name__ == "__main__":
    tests = [
        ("default thresholds: 81°C is warn (unblocks batch)", test_default_thresholds),
        ("critical at exactly 83°C", test_critical_at_threshold),
        ("shutdown at 88°C", test_shutdown_at_88),
        ("optimal below 73°C warn", test_optimal_below_warn),
        ("THERMAL_CRITICAL_C env override respected", test_env_override_critical),
        ("no sensors returns unknown", test_no_temps_returns_unknown),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1
    if failed:
        print(f"\n{failed}/{len(tests)} tests FAILED")
        sys.exit(1)
    print(f"\n{len(tests)}/{len(tests)} tests passed")
