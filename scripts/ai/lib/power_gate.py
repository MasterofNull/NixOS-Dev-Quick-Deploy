#!/usr/bin/env python3
"""Power/thermal gate for local llama.cpp work. Fail closed on any unreadable sensor.

Rule: run only if (AC online OR battery >= 50%) AND 5-min loadavg is not "busy"
(hysteresis: enter at >= 0.70*ncpu, leave at <= 0.55*ncpu) AND CPU temp < 80 C.
Sensor parsing mirrors scripts/ai/aq-keep-awake (an extensionless script, so not
importable); the CPU-specific temp source here avoids its all-zones max, which
includes non-CPU board sensors.

CLI exit codes: 0 = run, 5 = deferred (reason + readings on stdout).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

DEFER_EXIT = 5
MIN_BATTERY_PCT = 50
BUSY_ENTER = 0.70
BUSY_LEAVE = 0.55
MAX_TEMP_C = 80.0
CPU_HWMON = ("k10temp", "coretemp", "zenpower")
CPU_ZONES = ("x86_pkg_temp",)


def _read(p: Path) -> str | None:
    try:
        return p.read_text().strip()
    except OSError:
        return None


def read_power(root: Path) -> tuple[bool | None, int | None]:
    """Return (ac_online, lowest_battery_pct); None = unreadable."""
    ac: bool | None = None
    bat: int | None = None
    if root.is_dir():
        for d in sorted(root.iterdir()):
            t = _read(d / "type")
            if t == "Mains":
                on = _read(d / "online")
                if on in ("0", "1"):
                    ac = bool(ac) or on == "1"
            elif t == "Battery":
                cap = _read(d / "capacity")
                if cap and cap.isdigit():
                    bat = int(cap) if bat is None else min(bat, int(cap))
    return ac, bat


def read_cpu_temp(sys_root: Path) -> float | None:
    """CPU package temp in C from hwmon (k10temp/coretemp) or x86_pkg_temp zone."""
    temps: list[float] = []
    for h in sorted((sys_root / "class/hwmon").glob("hwmon*")):
        if _read(h / "name") in CPU_HWMON:
            for f in h.glob("temp*_input"):
                v = _read(f)
                if v and v.lstrip("-").isdigit():
                    temps.append(int(v) / 1000.0)
    for z in sorted((sys_root / "class/thermal").glob("thermal_zone*")):
        if _read(z / "type") in CPU_ZONES:
            v = _read(z / "temp")
            if v and v.lstrip("-").isdigit():
                temps.append(int(v) / 1000.0)
    return max(temps) if temps else None


def read_load5(proc_loadavg: Path) -> float | None:
    raw = _read(proc_loadavg)
    try:
        return float((raw or "").split()[1])
    except (IndexError, ValueError):
        return None


def _load_busy(load5: float, ncpu: int, state_file: Path | None) -> bool:
    prev = state_file is not None and _read(state_file) == "busy"
    busy = load5 > BUSY_LEAVE * ncpu if prev else load5 >= BUSY_ENTER * ncpu
    if state_file is not None:
        try:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text("busy" if busy else "clear")
        except OSError:
            pass  # hysteresis aid only; losing it falls back to the enter threshold
    return busy


def evaluate(
    sys_root: Path = Path("/sys"),
    proc_loadavg: Path = Path("/proc/loadavg"),
    ncpu: int | None = None,
    state_file: Path | None = None,
) -> dict:
    ncpu = ncpu or os.cpu_count() or 1
    ac, bat = read_power(sys_root / "class/power_supply")
    temp = read_cpu_temp(sys_root)
    load5 = read_load5(proc_loadavg)
    readings = {
        "ac": ac,
        "battery_pct": bat,
        "load5": load5,
        "ncpu": ncpu,
        "cpu_temp_c": temp,
    }
    reasons: list[str] = []
    if ac is None and bat is None:
        reasons.append("power state unreadable")
    elif not ac and (bat is None or bat < MIN_BATTERY_PCT):
        reasons.append(f"on battery below {MIN_BATTERY_PCT}% (battery={bat})")
    if load5 is None:
        reasons.append("loadavg unreadable")
    elif _load_busy(load5, ncpu, state_file):
        reasons.append(
            f"load5 {load5:.2f} busy (ncpu={ncpu}, enter>={BUSY_ENTER * ncpu:.2f}, "
            f"leave<={BUSY_LEAVE * ncpu:.2f})"
        )
    if temp is None:
        reasons.append("cpu temp unreadable")
    elif temp >= MAX_TEMP_C:
        reasons.append(f"cpu temp {temp:.0f}C >= {MAX_TEMP_C:.0f}C")
    return {"ok": not reasons, "reasons": reasons, "readings": readings}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="power/thermal gate for local inference")
    ap.add_argument("--state-file", type=Path)
    ap.add_argument("--defer-log", type=Path, help="append a JSON line when deferring")
    ap.add_argument("--task", default="", help="short task label for the defer log")
    ap.add_argument(
        "--sys-root",
        type=Path,
        default=Path(os.environ.get("AQ_POWER_GATE_SYS", "/sys")),
    )
    ap.add_argument(
        "--proc-loadavg",
        type=Path,
        default=Path(os.environ.get("AQ_POWER_GATE_LOADAVG", "/proc/loadavg")),
    )
    a = ap.parse_args(argv)
    d = evaluate(a.sys_root, a.proc_loadavg, state_file=a.state_file)
    r = d["readings"]
    line = (
        f"ac={r['ac']} battery={r['battery_pct']}% load5={r['load5']}/{r['ncpu']}cpu "
        f"cpu_temp={r['cpu_temp_c']}C"
    )
    if d["ok"]:
        print(f"power-gate: RUN ({line})")
        return 0
    print(
        f"power-gate: DEFER ({'; '.join(d['reasons'])}) [{line}] - nothing launched; retry later "
        "or override with --ignore-power-gate / AQ_LOCAL_POWER_GATE=0"
    )
    if a.defer_log:
        try:
            a.defer_log.parent.mkdir(parents=True, exist_ok=True)
            with a.defer_log.open("a") as f:
                f.write(
                    json.dumps({"ts": int(time.time()), "task": a.task[:200], **d})
                    + "\n"
                )
        except OSError:
            pass
    return DEFER_EXIT


if __name__ == "__main__":
    sys.exit(main())
