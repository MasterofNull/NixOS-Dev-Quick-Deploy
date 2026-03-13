#!/usr/bin/env python3
"""Observe llama.cpp process and AMD GPU resource usage during a benchmark window."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_int(path: Path) -> int:
    text = read_text(path)
    try:
        return int(text)
    except ValueError:
        return 0


def system_cpu_ticks() -> int:
    stat = read_text(Path("/proc/stat"))
    if not stat:
        return 0
    first = stat.splitlines()[0].split()
    if len(first) < 2 or first[0] != "cpu":
        return 0
    total = 0
    for item in first[1:]:
        try:
            total += int(item)
        except ValueError:
            continue
    return total


def process_cpu_ticks(pid: int) -> int:
    stat = read_text(Path(f"/proc/{pid}/stat"))
    if not stat:
        return 0
    parts = stat.split()
    if len(parts) < 17:
        return 0
    try:
        return int(parts[13]) + int(parts[14])
    except ValueError:
        return 0


def process_rss_mb(pid: int) -> float:
    status = read_text(Path(f"/proc/{pid}/status"))
    if not status:
        return 0.0
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return round(int(parts[1]) / 1024.0, 3)
                except ValueError:
                    return 0.0
    return 0.0


def discover_llama_pid(service_name: str = "llama-cpp.service") -> int:
    value = read_text(Path(f"/run/systemd/system/{service_name}"))
    if value:
        return 0
    try:
        import subprocess

        result = subprocess.run(
            ["systemctl", "show", "-p", "MainPID", "--value", service_name],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return 0
        return int((result.stdout or "0").strip() or "0")
    except (OSError, ValueError):
        return 0


def find_amd_gpu_device() -> Optional[Path]:
    root = Path("/sys/class/drm")
    if not root.exists():
        return None
    for candidate in sorted(root.glob("card*/device")):
        if (candidate / "gpu_busy_percent").exists():
            return candidate
    return None


def gpu_sample(device: Optional[Path]) -> Dict[str, Any]:
    if device is None:
        return {
            "gpu_busy_percent": None,
            "vram_used_mb": None,
            "vram_total_mb": None,
            "gpu_temp_c": None,
            "gpu_power_watts": None,
        }

    hwmon_dirs = list((device / "hwmon").glob("*"))
    hwmon_dir = hwmon_dirs[0] if hwmon_dirs else None
    busy = read_int(device / "gpu_busy_percent")
    vram_used = read_int(device / "mem_info_vram_used")
    vram_total = read_int(device / "mem_info_vram_total")
    temp_mc = read_int(hwmon_dir / "temp1_input") if hwmon_dir else 0
    power_uw = read_int(hwmon_dir / "power1_average") if hwmon_dir else 0

    return {
        "gpu_busy_percent": float(busy),
        "vram_used_mb": round(vram_used / (1024.0 * 1024.0), 3) if vram_used else 0.0,
        "vram_total_mb": round(vram_total / (1024.0 * 1024.0), 3) if vram_total else 0.0,
        "gpu_temp_c": round(temp_mc / 1000.0, 3) if temp_mc else 0.0,
        "gpu_power_watts": round(power_uw / 1000000.0, 3) if power_uw else 0.0,
    }


def take_sample(pid: int, prev_proc: int, prev_total: int, cpu_count: int, device: Optional[Path]) -> Tuple[Dict[str, Any], int, int]:
    proc_now = process_cpu_ticks(pid)
    total_now = system_cpu_ticks()
    cpu_percent = 0.0
    if prev_proc > 0 and prev_total > 0 and total_now > prev_total:
        cpu_percent = ((proc_now - prev_proc) / float(total_now - prev_total)) * cpu_count * 100.0
        if cpu_percent < 0:
            cpu_percent = 0.0
    sample = {
        "timestamp": time.time(),
        "cpu_percent": round(cpu_percent, 3),
        "rss_mb": process_rss_mb(pid),
    }
    sample.update(gpu_sample(device))
    return sample, proc_now, total_now


def summarize_samples(samples: List[Dict[str, Any]], *, pid: int) -> Dict[str, Any]:
    if not samples:
        return {
            "status": "no_samples",
            "pid": pid,
            "sample_count": 0,
        }

    def values(name: str) -> List[float]:
        return [float(item[name]) for item in samples if item.get(name) is not None]

    def avg(name: str) -> Optional[float]:
        vals = values(name)
        return round(sum(vals) / len(vals), 3) if vals else None

    def peak(name: str) -> Optional[float]:
        vals = values(name)
        return round(max(vals), 3) if vals else None

    return {
        "status": "ok",
        "pid": pid,
        "sample_count": len(samples),
        "window_seconds": round(samples[-1]["timestamp"] - samples[0]["timestamp"], 3) if len(samples) > 1 else 0.0,
        "avg_cpu_percent": avg("cpu_percent"),
        "peak_cpu_percent": peak("cpu_percent"),
        "avg_rss_mb": avg("rss_mb"),
        "peak_rss_mb": peak("rss_mb"),
        "avg_gpu_busy_percent": avg("gpu_busy_percent"),
        "peak_gpu_busy_percent": peak("gpu_busy_percent"),
        "avg_gpu_power_watts": avg("gpu_power_watts"),
        "peak_gpu_power_watts": peak("gpu_power_watts"),
        "peak_gpu_temp_c": peak("gpu_temp_c"),
        "peak_vram_used_mb": peak("vram_used_mb"),
    }


def observe_window(pid: int, duration_seconds: float, sample_interval: float) -> Dict[str, Any]:
    device = find_amd_gpu_device()
    cpu_count = os.cpu_count() or 1
    prev_proc = process_cpu_ticks(pid)
    prev_total = system_cpu_ticks()
    samples: List[Dict[str, Any]] = []
    deadline = time.time() + duration_seconds
    while time.time() < deadline:
        time.sleep(sample_interval)
        sample, prev_proc, prev_total = take_sample(pid, prev_proc, prev_total, cpu_count, device)
        samples.append(sample)
    summary = summarize_samples(samples, pid=pid)
    summary["samples"] = samples
    summary["gpu_device"] = str(device) if device else ""
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Observe llama.cpp CPU/GPU/RSS for a bounded window.")
    parser.add_argument("--pid", type=int, default=0, help="PID to observe. Defaults to llama-cpp.service MainPID.")
    parser.add_argument("--service", default="llama-cpp.service", help="Service to resolve when --pid is not set.")
    parser.add_argument("--duration-seconds", type=float, default=10.0, help="Observation window.")
    parser.add_argument("--sample-interval", type=float, default=0.25, help="Sampling interval.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pid = args.pid or discover_llama_pid(args.service)
    if pid <= 0:
        raise SystemExit("ERROR: unable to resolve a live llama.cpp PID")
    print(json.dumps(observe_window(pid, args.duration_seconds, args.sample_interval), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
