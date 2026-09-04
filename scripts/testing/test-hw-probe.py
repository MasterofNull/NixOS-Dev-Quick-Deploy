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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _make_pci_device(sys_root: Path, bdf: str, pci_class: str, vendor: str, device: str) -> None:
    """Create a hermetic /sys/bus/pci/devices/<bdf> node (driver-independent)."""
    base = sys_root / "bus" / "pci" / "devices" / bdf
    _write(base / "class", pci_class + "\n")
    _write(base / "vendor", vendor + "\n")
    _write(base / "device", device + "\n")


def assert_required_keys(profile: dict) -> None:
    for key in ("cpu", "ram", "pci_devices", "gpu", "npu", "thermal", "battery", "disk", "os", "derived", "undetected"):
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


def test_pci_gpu_detected_without_driver() -> None:
    """The live-ISO case: a GPU on the PCI bus with NO DRM/driver bound is still detected."""
    hw_probe = load_hw_probe()
    with tempfile.TemporaryDirectory() as tmp:
        sys_root = Path(tmp) / "sys"
        # Discrete NVIDIA GPU present on the bus; no /sys/class/drm (driver not bound yet).
        _make_pci_device(sys_root, "0000:01:00.0", "0x030000", "0x10de", "0x2482")
        undetected: list[str] = []
        pci = hw_probe._enumerate_pci_devices(sys_root, undetected)
        assert pci is not None and len(pci) == 1, pci
        gpu = hw_probe._detect_gpu(sys_root, None, undetected, pci)
    assert gpu["present"] is True, gpu
    assert gpu["outcome"] == "detected", gpu
    assert gpu["primary"]["vendor_id"] == "0x10de", gpu
    assert gpu["primary"]["device_id"] == "0x2482", gpu
    assert gpu["primary"]["pci_class"] == "0x030000", gpu
    # PCI-only evidence: no DRM card, no lspci text.
    assert gpu["primary"]["evidence"] == "pci", gpu
    assert gpu["primary"]["card"] is None, gpu


def test_no_pci_inventory_is_insufficient_evidence() -> None:
    """No PCI sysfs and no lspci -> conservative, explicit insufficient_evidence."""
    hw_probe = load_hw_probe()
    with tempfile.TemporaryDirectory() as tmp:
        sys_root = Path(tmp) / "sys"  # no /sys/bus/pci at all
        undetected: list[str] = []
        pci = hw_probe._enumerate_pci_devices(sys_root, undetected)
        assert pci is None, pci
        gpu = hw_probe._detect_gpu(sys_root, None, undetected, pci)
    assert gpu["present"] is False, gpu
    assert gpu["outcome"] == "insufficient_evidence", gpu
    assert gpu["primary"] is None, gpu


def test_pci_multi_gpu_deterministic_order() -> None:
    """Multiple display-class devices are all detected, BDF-sorted; non-display filtered out."""
    hw_probe = load_hw_probe()
    with tempfile.TemporaryDirectory() as tmp:
        sys_root = Path(tmp) / "sys"
        # Added out of BDF order; a non-display device is present and must be excluded.
        _make_pci_device(sys_root, "0000:01:00.0", "0x030000", "0x10de", "0x2482")  # dGPU
        _make_pci_device(sys_root, "0000:00:02.0", "0x030000", "0x8086", "0x9a49")  # iGPU
        _make_pci_device(sys_root, "0000:00:1f.0", "0x060100", "0x8086", "0x43a0")  # ISA bridge
        undetected: list[str] = []
        pci = hw_probe._enumerate_pci_devices(sys_root, undetected)
        assert pci is not None and len(pci) == 3, pci
        gpu = hw_probe._detect_gpu(sys_root, None, undetected, pci)
    assert gpu["present"] is True, gpu
    assert len(gpu["devices"]) == 2, gpu  # only the two display-class devices
    assert gpu["devices"][0]["bdf"] == "0000:00:02.0", gpu
    assert gpu["devices"][1]["bdf"] == "0000:01:00.0", gpu


def main() -> int:
    host_profile = test_cli_runs_cleanly()
    test_bogus_roots_degrade()
    test_ram_class_edges()
    test_write_refuses_existing_without_force()
    test_pci_gpu_detected_without_driver()
    test_no_pci_inventory_is_insufficient_evidence()
    test_pci_multi_gpu_deterministic_order()
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
