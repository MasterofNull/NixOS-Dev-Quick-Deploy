#!/usr/bin/env python3
"""Targeted checks for aq-bitnet-feasibility."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-bitnet-feasibility.py"
SPEC = importlib.util.spec_from_file_location("aq_bitnet_feasibility", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-bitnet-feasibility module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    viable_report = MODULE.build_report(
        {
            "system": "x86_64-linux",
            "cpu_vendor": "amd",
            "gpu_vendor": "amd",
            "system_ram_gb": 27,
        },
        command_overrides={
            "python3": {"available": True, "path": "/bin/python3", "minimum": "3.9", "version": "Python 3.13.1", "meets_minimum": True},
            "cmake": {"available": True, "path": "/bin/cmake", "minimum": "3.22", "version": "cmake version 3.31.0", "meets_minimum": True},
            "clang": {"available": True, "path": "/bin/clang", "minimum": "18", "version": "clang version 18.1.8", "meets_minimum": True},
            "git": {"available": True, "path": "/bin/git", "minimum": "required", "version": "git version 2.49.0", "meets_minimum": True},
        },
    )
    assert_true(viable_report["sidecar_viable"] is True, "expected sidecar viability on supported x86_64 host")
    assert_true(bool(viable_report["preferred_models"]), "expected at least one preferred model")
    assert_true(
        viable_report["preferred_models"][0]["name"] == "BitNet-b1.58-2B-4T",
        "expected official 2B model to be the leading preferred candidate",
    )

    blocked_report = MODULE.build_report(
        {
            "system": "x86_64-linux",
            "cpu_vendor": "amd",
            "gpu_vendor": "amd",
            "system_ram_gb": 27,
        },
        command_overrides={
            "python3": {"available": True, "path": "/bin/python3", "minimum": "3.9", "version": "Python 3.13.1", "meets_minimum": True},
            "cmake": {"available": True, "path": "/bin/cmake", "minimum": "3.22", "version": "cmake version 3.31.0", "meets_minimum": True},
            "clang": {"available": False, "path": "", "minimum": "18", "version": "", "meets_minimum": False},
            "git": {"available": True, "path": "/bin/git", "minimum": "required", "version": "git version 2.49.0", "meets_minimum": True},
        },
    )
    assert_true(blocked_report["sidecar_viable"] is False, "missing clang should block feasibility")
    assert_true("missing_requirement:clang" in blocked_report["blockers"], "clang blocker missing")
    assert_true(
        any("clang>=18" in action for action in blocked_report["next_actions"]),
        "missing clang remediation guidance missing",
    )

    print("PASS: aq-bitnet-feasibility reports supported-host recommendations and build blockers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
