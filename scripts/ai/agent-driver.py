#!/usr/bin/env python3
"""
agent_driver.py — Ephemeral Sub-Agent Runtime Controller

Executes isolated AI agent payloads through the physical core-pinning orchestrator,
capturing telemetry while preventing cache-state retention.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def verify_system_state() -> None:
    """Verifies that the host system satisfies hardware isolation requirements."""
    isolated_path = Path("/sys/devices/system/cpu/isolated")
    if not isolated_path.is_file():
        raise RuntimeError("Kernel isolation subsystem /sys/devices/system/cpu/isolated not present.")

    isolated_cores = isolated_path.read_text(encoding="utf-8").strip()
    if not any(core_range in isolated_cores for core_range in ("4-7", "4,5,6,7")):
        raise PermissionError(
            f"Hardware isolation failure: Cores 4-7 not in isolcpus (found: '{isolated_cores}')."
        )

    smt_path = Path("/sys/devices/system/cpu/smt/active")
    if smt_path.is_file() and smt_path.read_text(encoding="utf-8").strip() != "0":
        raise PermissionError("Hardware isolation failure: SMT is currently active.")


def run_agent_payload(orchestrator_bin: Path, payload_path: Path) -> int:
    """Invokes the orchestrator wrapper under strict subprocess isolation."""
    if not orchestrator_bin.is_file():
        raise FileNotFoundError(f"Orchestrator binary not found: {orchestrator_bin}")
    if not payload_path.is_file():
        raise FileNotFoundError(f"Agent payload script not found: {payload_path}")

    cmd = ["sudo", str(orchestrator_bin), str(payload_path.resolve())]

    print(f"[*] Dispatching isolated agent payload: {payload_path.name}")
    sys.stdout.flush()

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    # Stream stdout in real-time
    if process.stdout:
        for line in iter(process.stdout.readline, ""):
            print(f"[AGENT] {line}", end="")
            sys.stdout.flush()

    _, stderr_data = process.communicate()
    if process.returncode != 0:
        print(f"[-] Execution failure (code {process.returncode}):\n{stderr_data}", file=sys.stderr)

    return process.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Microarchitectural Isolation Agent Driver")
    parser.add_argument("payload", type=Path, help="Path to untrusted agent script to execute")
    parser.add_argument(
        "--orchestrator",
        type=Path,
        default=Path(__file__).resolve().parent / "orchestrate-sandbox.sh",
        help="Path to orchestrate-sandbox.sh",
    )
    args = parser.parse_args()

    try:
        verify_system_state()
        return run_agent_payload(args.orchestrator, args.payload)
    except Exception as exc:
        print(f"[-] Driver initialization error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
