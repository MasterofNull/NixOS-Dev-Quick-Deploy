#!/usr/bin/env python3
"""Hardware capability probe for generated local inference profiles."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any


PROFILE_PATH = Path("config/hardware-profile.generated.json")
GPU_LAYER_CEILING = 12
GIB = 1024**3


def _read_text(path: Path, undetected: list[str], label: str | None = None) -> str | None:
    try:
        return path.read_text(errors="replace")
    except Exception:
        undetected.append(label or str(path))
        return None


def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except Exception:
        return None


def _run_lspci(undetected: list[str]) -> str | None:
    if shutil.which("lspci") is None:
        undetected.append("lspci")
        return None
    try:
        return subprocess.run(
            ["lspci", "-nn"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout
    except Exception:
        undetected.append("lspci")
        return None


def _enumerate_pci_devices(sys_root: Path, undetected: list[str]) -> list[dict[str, Any]] | None:
    """Driver-INDEPENDENT PCI inventory from /sys/bus/pci/devices/*.

    Presence and identity of every device come from sysfs PCI attributes
    (class, vendor, device), NOT from loaded drivers, DRM state, nvidia-smi, or
    lspci. A device exists on the bus regardless of whether its driver
    initialized — critical on a live installer where a discrete GPU may only
    have `nouveau`/`vesa` (or nothing) bound (antigravity review, PRD v2 §96).
    Returns a deterministic (BDF-sorted) list; None when the PCI sysfs tree is
    absent (recorded in `undetected`), so the caller emits insufficient_evidence
    rather than guessing.
    """
    pci_root = sys_root / "bus" / "pci" / "devices"
    if not pci_root.is_dir():
        undetected.append(str(pci_root))
        return None
    try:
        entries = sorted(pci_root.iterdir(), key=lambda p: p.name)
    except OSError:
        undetected.append(str(pci_root))
        return None
    devices: list[dict[str, Any]] = []
    for entry in entries:
        cls = _read_text(entry / "class", [], None)
        vendor = _read_text(entry / "vendor", [], None)
        device = _read_text(entry / "device", [], None)
        devices.append(
            {
                "bdf": entry.name,  # domain:bus:device.function, e.g. 0000:03:00.0
                "pci_class": cls.strip().lower() if cls else None,
                "vendor_id": vendor.strip().lower() if vendor else None,
                "device_id": device.strip().lower() if device else None,
            }
        )
    return devices


def _is_display_class(pci_class: str | None) -> bool:
    """PCI base class 0x03 = display controller (0300 VGA, 0302 3D, 0380 other).
    Class is the driver-independent authority for 'this is a GPU'."""
    if not pci_class:
        return False
    c = pci_class.lower()
    if c.startswith("0x"):
        c = c[2:]
    return c[:2] == "03"


def _parse_cpuinfo(text: str | None, undetected: list[str]) -> dict[str, Any]:
    if not text:
        return {
            "model": None,
            "cores": None,
            "threads": None,
            "isa_flags": {"avx2": None, "avx512": None, "neon": None},
        }

    model = None
    physical_cores: set[tuple[str, str]] = set()
    logical = 0
    flags: set[str] = set()
    for block in text.strip().split("\n\n"):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip()] = value.strip()
        if fields:
            logical += 1
        model = model or fields.get("model name") or fields.get("Hardware") or fields.get("Processor")
        if "physical id" in fields and "core id" in fields:
            physical_cores.add((fields["physical id"], fields["core id"]))
        raw_flags = fields.get("flags") or fields.get("Features") or ""
        flags.update(raw_flags.lower().split())

    avx512 = any(flag.startswith("avx512") for flag in flags)
    cores = len(physical_cores) or None
    if cores is None:
        siblings = []
        for line in text.splitlines():
            if line.startswith("cpu cores") and ":" in line:
                try:
                    siblings.append(int(line.split(":", 1)[1].strip()))
                except ValueError:
                    pass
        cores = max(siblings) if siblings else os.cpu_count()

    return {
        "model": model,
        "cores": cores,
        "threads": logical or os.cpu_count(),
        "isa_flags": {
            "avx2": True if "avx2" in flags else False,
            "avx512": True if avx512 else False,
            "neon": True if ("neon" in flags or "asimd" in flags) else False,
        },
    }


def _parse_meminfo(text: str | None) -> dict[str, int | None]:
    if not text:
        return {"total_bytes": None, "available_bytes": None}
    values: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        parts = raw.strip().split()
        if parts and parts[0].isdigit():
            values[key] = int(parts[0]) * 1024
    return {
        "total_bytes": values.get("MemTotal"),
        "available_bytes": values.get("MemAvailable"),
    }


def _gpu_lines_from_lspci(lspci_text: str | None) -> list[str]:
    if not lspci_text:
        return []
    needles = (" vga ", " 3d controller", " display controller")
    return [line for line in lspci_text.splitlines() if any(needle in line.lower() for needle in needles)]


def _drm_index_by_bdf(sys_root: Path, undetected: list[str]) -> dict[str, dict[str, Any]]:
    """DRM VRAM/card evidence keyed by PCI BDF (driver-DEPENDENT enrichment).

    A GPU whose driver never bound simply has no DRM entry here — that means
    'no VRAM evidence', NOT 'no GPU' (presence is decided by PCI class, below).
    """
    drm_root = sys_root / "class" / "drm"
    index: dict[str, dict[str, Any]] = {}
    if not drm_root.is_dir():
        undetected.append(str(drm_root))
        return index
    try:
        cards = sorted(drm_root.glob("card[0-9]"))
    except Exception:
        undetected.append(str(drm_root))
        return index
    for card in cards:
        device = card / "device"
        bdf = None
        try:
            if device.is_symlink():
                bdf = os.path.basename(os.readlink(device))
        except OSError:
            bdf = None
        rec = {
            "card": card.name,
            "bdf": bdf,
            "vendor_id": (_read_text(device / "vendor", [], None) or "").strip().lower() or None,
            "device_id": (_read_text(device / "device", [], None) or "").strip().lower() or None,
            "vram_total_bytes": _read_int(device / "mem_info_vram_total"),
            "visible_vram_bytes": _read_int(device / "mem_info_vis_vram_total"),
        }
        index[bdf or card.name] = rec
    return index


def _detect_gpu(
    sys_root: Path,
    lspci_text: str | None,
    undetected: list[str],
    pci_devices: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """GPU presence + identity, driver-INDEPENDENT (PRD v2 §96).

    PRIMARY evidence is the PCI class from the sysfs inventory (a display-class
    device exists on the bus whether or not a driver bound). DRM sysfs and
    `lspci -nn` are enrichment only (VRAM, human description) and never decide
    presence. When the PCI inventory is unavailable the outcome degrades to an
    explicit `insufficient_evidence` rather than guessing.
    """
    drm_by_bdf = _drm_index_by_bdf(sys_root, undetected)
    lspci_gpus = _gpu_lines_from_lspci(lspci_text)
    gpus: list[dict[str, Any]] = []
    outcome = "detected"

    if pci_devices is not None:
        for dev in pci_devices:
            if not _is_display_class(dev.get("pci_class")):
                continue
            bdf = dev.get("bdf")
            drm = drm_by_bdf.get(bdf, {})
            gpus.append(
                {
                    "card": drm.get("card"),
                    "bdf": bdf,
                    "vendor_id": dev.get("vendor_id") or drm.get("vendor_id"),
                    "device_id": dev.get("device_id") or drm.get("device_id"),
                    "pci_class": dev.get("pci_class"),
                    "vram_total_bytes": drm.get("vram_total_bytes"),
                    "visible_vram_bytes": drm.get("visible_vram_bytes"),
                    "evidence": "pci" + ("+drm" if drm else ""),
                }
            )
    else:
        # No driver-independent PCI inventory — degrade to DRM, then lspci.
        outcome = "insufficient_evidence"
        for rec in drm_by_bdf.values():
            entry = dict(rec)
            entry["pci_class"] = None
            entry["evidence"] = "drm"
            gpus.append(entry)

    if gpus and lspci_gpus:
        for gpu, line in zip(gpus, lspci_gpus):
            gpu.setdefault("description", line)
    elif not gpus and lspci_gpus:
        for line in lspci_gpus:
            gpus.append(
                {
                    "card": None,
                    "bdf": None,
                    "vendor_id": None,
                    "device_id": None,
                    "pci_class": None,
                    "vram_total_bytes": None,
                    "visible_vram_bytes": None,
                    "description": line,
                    "evidence": "lspci",
                }
            )

    if not gpus:
        undetected.append("gpu")
        return {
            "present": False,
            "outcome": "none" if pci_devices is not None else "insufficient_evidence",
            "devices": [],
            "primary": None,
        }

    primary = dict(gpus[0])
    desc = " ".join(str(gpu.get("description") or "") for gpu in gpus).lower()
    vendor_ids = {str(gpu.get("vendor_id") or "").lower() for gpu in gpus}
    is_amd = "amd" in desc or "advanced micro devices" in desc or "0x1002" in vendor_ids
    is_amd_apu = is_amd and any(
        marker in desc
        for marker in (
            "renoir",
            "cezanne",
            "radeon vega mobile",
            "radeon vega series",
        )
    )
    has_dedicated = any((gpu.get("vram_total_bytes") or 0) > 0 for gpu in gpus)
    shared = bool(is_amd_apu or (is_amd and not has_dedicated))
    if shared:
        primary["memory_type"] = "shared"
        primary["vram_total_bytes"] = None
    elif has_dedicated:
        primary["memory_type"] = "dedicated"
    else:
        primary["memory_type"] = None
        undetected.append("gpu_vram")

    return {"present": True, "outcome": outcome, "devices": gpus, "primary": primary}


def _detect_npu(lspci_text: str | None) -> dict[str, Any]:
    if not lspci_text:
        return {"present": None, "hints": []}
    patterns = ("npu", "neural", "ai accelerator", "ipu", "vpu", "gaudi", "habanalabs")
    hints = [line for line in lspci_text.splitlines() if any(pattern in line.lower() for pattern in patterns)]
    return {"present": bool(hints), "hints": hints}


def _present_paths(root: Path, pattern: str) -> list[str] | None:
    if not root.is_dir():
        return None
    try:
        return sorted(str(path) for path in root.glob(pattern))
    except Exception:
        return None


def hardware_class_for_ram(total_ram_bytes: int | None) -> str | None:
    if total_ram_bytes is None:
        return None
    gib = total_ram_bytes / GIB
    if gib < 4:
        return "embedded"
    if gib < 16:
        return "laptop"
    if gib < 64:
        return "desktop"
    return "server"


def _model_size_for_class(hardware_class: str | None) -> dict[str, Any]:
    table = {
        "embedded": {"max_local_model_b_params": 4, "quant_ladder_step": "Q2_K"},
        "laptop": {"max_local_model_b_params": 14, "quant_ladder_step": "Q4_K_M"},
        "desktop": {"max_local_model_b_params": 35, "quant_ladder_step": "Q4_K_M"},
        "server": {"max_local_model_b_params": 70, "quant_ladder_step": "Q5_K_M"},
    }
    return table.get(hardware_class) or {"max_local_model_b_params": None, "quant_ladder_step": None}


def derive_profile(ram: dict[str, int | None], gpu: dict[str, Any]) -> dict[str, Any]:
    total_ram = ram.get("total_bytes")
    hw_class = hardware_class_for_ram(total_ram)
    ram_gib = (total_ram or 0) / GIB
    gpu_present = bool(gpu.get("present"))
    primary = gpu.get("primary") or {}
    memory_type = primary.get("memory_type")
    dedicated_vram = primary.get("vram_total_bytes") or 0

    if not gpu_present:
        gpu_layers = 0
    elif memory_type == "shared":
        gpu_layers = min(GPU_LAYER_CEILING, 12 if ram_gib >= 24 else 8 if ram_gib >= 16 else 4)
    elif dedicated_vram:
        gpu_layers = min(GPU_LAYER_CEILING, max(1, int(dedicated_vram / GIB) * 4))
    else:
        gpu_layers = min(GPU_LAYER_CEILING, 4)

    ctx_table = {"embedded": 2048, "laptop": 4096, "desktop": 8192, "server": 16384}
    token_table = {"embedded": 512, "laptop": 1024, "desktop": 2048, "server": 4096}
    return {
        "hardware_class": hw_class,
        "model_size_class": _model_size_for_class(hw_class),
        "suggested_n_gpu_layers": gpu_layers,
        "suggested_ctx_size": ctx_table.get(hw_class),
        "suggested_max_tokens": token_table.get(hw_class),
        "tok_per_sec_estimate": None,
    }


def probe_hardware(
    proc_root: Path | str = Path("/proc"),
    sys_root: Path | str = Path("/sys"),
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    undetected: list[str] = []
    proc_root = Path(proc_root)
    sys_root = Path(sys_root)
    repo_root = Path(repo_root or Path.cwd())

    cpuinfo = _read_text(proc_root / "cpuinfo", undetected, "/proc/cpuinfo")
    meminfo = _read_text(proc_root / "meminfo", undetected, "/proc/meminfo")
    lspci_text = _run_lspci(undetected)
    pci_devices = _enumerate_pci_devices(sys_root, undetected)

    ram = _parse_meminfo(meminfo)
    gpu = _detect_gpu(sys_root, lspci_text, undetected, pci_devices)
    thermal_zones = _present_paths(sys_root / "class" / "thermal", "thermal_zone*")
    batteries = _present_paths(sys_root / "class" / "power_supply", "BAT*")
    if thermal_zones is None:
        undetected.append("/sys/class/thermal")
    if batteries is None:
        undetected.append("/sys/class/power_supply")

    try:
        disk = shutil.disk_usage(repo_root)
        disk_free = disk.free
    except Exception:
        undetected.append("repo_root_disk")
        disk_free = None

    result = {
        "schema_version": 2,
        "cpu": _parse_cpuinfo(cpuinfo, undetected),
        "ram": ram,
        "pci_devices": pci_devices,
        "gpu": gpu,
        "npu": _detect_npu(lspci_text),
        "thermal": {"zones_present": thermal_zones},
        "battery": {"present": bool(batteries) if batteries is not None else None, "devices": batteries},
        "disk": {"repo_root_free_bytes": disk_free},
        "os": {"system": platform.system() or None, "release": platform.release() or None, "kernel": platform.version() or None},
        "derived": {},
        "undetected": sorted(set(undetected)),
    }
    result["derived"] = derive_profile(ram, gpu)
    return result


def write_profile(profile: dict[str, Any], output_path: Path, force: bool = False) -> None:
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists; pass --force to overwrite")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe hardware and emit a generated inference profile.")
    parser.add_argument("--write", action="store_true", help=f"write JSON to {PROFILE_PATH}")
    parser.add_argument("--force", action="store_true", help="allow --write to overwrite an existing generated profile")
    parser.add_argument("--output", type=Path, default=PROFILE_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    profile = probe_hardware()
    if args.write:
        try:
            write_profile(profile, args.output, force=args.force)
        except Exception as exc:
            print(f"hw_probe: {exc}", file=os.sys.stderr)
            return 1
    print(json.dumps(profile, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
