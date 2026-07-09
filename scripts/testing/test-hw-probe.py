#!/usr/bin/env python3
"""Focused tests for scripts/ai/lib/hw_probe.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HW_PROBE_PATH = REPO_ROOT / "scripts" / "ai" / "lib" / "hw_probe.py"


def load_hw_probe():
    spec = importlib.util.spec_from_file_location("hw_probe", HW_PROBE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_required_keys(profile: dict) -> None:
    for key in ("cpu", "ram", "gpu", "npu", "thermal", "battery", "disk", "os", "derived", "undetected"):
        assert key in profile, key
    for key in (
        "hardware_class",
        "model_size_class",
        "suggested_n_gpu_layers",
        "suggested_ctx_size",
        "suggested_max_tokens",
        "tok_per_sec_estimate",
    ):
        assert key in profile["derived"], key


def test_cli_runs_cleanly() -> dict:
    result = subprocess.run(
        [sys.executable, str(HW_PROBE_PATH)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    profile = json.loads(result.stdout)
    assert_required_keys(profile)
    assert profile["derived"]["tok_per_sec_estimate"] is None
    assert profile["derived"]["suggested_n_gpu_layers"] <= 12
    description = str((profile["gpu"]["primary"] or {}).get("description") or "").lower()
    if any(marker in description for marker in ("renoir", "cezanne", "radeon vega mobile")):
        assert profile["gpu"]["primary"]["memory_type"] == "shared"
    return profile


def test_bogus_roots_degrade() -> None:
    hw_probe = load_hw_probe()
    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "missing"
        profile = hw_probe.probe_hardware(proc_root=missing, sys_root=missing, repo_root=missing)
    assert_required_keys(profile)
    assert profile["cpu"]["model"] is None
    assert profile["cpu"]["cores"] is None
    assert profile["cpu"]["threads"] is None
    assert profile["ram"]["total_bytes"] is None
    assert profile["derived"]["hardware_class"] is None
    assert profile["derived"]["suggested_n_gpu_layers"] in (0, 4)
    assert "/proc/cpuinfo" in profile["undetected"]
    assert "/proc/meminfo" in profile["undetected"]


def test_ram_class_edges() -> None:
    hw_probe = load_hw_probe()
    cases = (
        (4 * hw_probe.GIB - 1, "embedded"),
        (4 * hw_probe.GIB, "laptop"),
        (16 * hw_probe.GIB - 1, "laptop"),
        (16 * hw_probe.GIB, "desktop"),
        (64 * hw_probe.GIB - 1, "desktop"),
        (64 * hw_probe.GIB, "server"),
    )
    for total_bytes, expected in cases:
        assert hw_probe.hardware_class_for_ram(total_bytes) == expected


def test_write_refuses_existing_without_force() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "hardware-profile.generated.json"
        output.write_text('{"hand_authored": true}\n')
        blocked = subprocess.run(
            [sys.executable, str(HW_PROBE_PATH), "--write", "--output", str(output)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert blocked.returncode == 1
        assert json.loads(output.read_text()) == {"hand_authored": True}

        forced = subprocess.run(
            [sys.executable, str(HW_PROBE_PATH), "--write", "--force", "--output", str(output)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert forced.returncode == 0
        assert_required_keys(json.loads(output.read_text()))


def main() -> int:
    host_profile = test_cli_runs_cleanly()
    test_bogus_roots_degrade()
    test_ram_class_edges()
    test_write_refuses_existing_without_force()
    ram_gib = (host_profile["ram"]["total_bytes"] or 0) / (1024**3)
    print(
        "test-hw-probe: ok "
        f"hardware_class={host_profile['derived']['hardware_class']} "
        f"ram_gib={ram_gib:.1f} "
        f"gpu_layers={host_profile['derived']['suggested_n_gpu_layers']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
