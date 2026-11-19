#!/usr/bin/env python3
"""Power/thermal gate for local llama.cpp work. Fail closed on any unreadable sensor.

Rule: run only if (AC online OR battery >= MIN_BATTERY_PCT) AND 5-min loadavg is not "busy"
(hysteresis: enter at >= 0.70*ncpu, leave at <= 0.55*ncpu) AND CPU temp < max temp.

Limits are not hardwired to one machine:
  AQ_POWER_GATE_MIN_BATTERY_PCT  battery floor, default 50 (clamped 0..100)
  AQ_POWER_GATE_MAX_TEMP_C       temp ceiling; default = lowest CPU critical/high trip point
                                 (thermal_zone trip_point_*_temp, hwmon temp*_crit/_max)
                                 minus AQ_POWER_GATE_TEMP_MARGIN_C (default 15), clamped to
                                 [50, 100]; falls back to 80 C when no trip point is readable.
Sensor parsing mirrors scripts/ai/aq-keep-awake (an extensionless script, so not
importable); the CPU-specific temp source here avoids its all-zones max, which
includes non-CPU board sensors.

CLI exit codes: 0 = run, 5 = deferred (reason + readings on stdout).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

DEFER_EXIT = 5
MIN_BATTERY_PCT = 50  # default; AQ_POWER_GATE_MIN_BATTERY_PCT overrides
BUSY_ENTER = 0.70
BUSY_LEAVE = 0.55
MAX_TEMP_C = 80.0  # fallback when no trip point is readable; AQ_POWER_GATE_MAX_TEMP_C overrides
TEMP_MARGIN_C = 15.0
TEMP_FLOOR_C = 50.0
TEMP_CEIL_C = 100.0
TRIP_TYPES = ("critical", "hot", "high")
CPU_HWMON = ("k10temp", "coretemp", "zenpower")
CPU_ZONES = ("x86_pkg_temp",)


def _read(p: Path) -> str | None:
    try:
        return p.read_text().strip()
    except OSError:
        return None


def _env_float(name: str) -> float | None:
    """Finite float override, else None (caller uses its derived default).

    float() accepts "nan"/"inf"; nan makes `temp >= max` always false and nan floors clamp
    to 0, both silently disabling the gate, so non-finite values are rejected with a warning.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        v = float(raw)
    except ValueError:
        print(f"power-gate: WARN ignoring invalid {name}={raw!r}; using derived default", file=sys.stderr)
        return None
    if not math.isfinite(v):
        print(f"power-gate: WARN ignoring non-finite {name}={raw!r}; using derived default", file=sys.stderr)
        return None
    return v


def min_battery_pct() -> int:
    v = _env_float("AQ_POWER_GATE_MIN_BATTERY_PCT")
    return MIN_BATTERY_PCT if v is None else int(min(100.0, max(0.0, v)))


def cpu_trip_points(sys_root: Path) -> list[float]:
    """Critical/high trip temps (C) of CPU sensors: thermal trips plus hwmon crit/max."""
    out: list[float] = []

    def add(p: Path) -> None:
        v = _read(p)
        if v and v.isdigit() and int(v) > 0:
            out.append(int(v) / 1000.0)

    for z in sorted((sys_root / "class/thermal").glob("thermal_zone*")):
        if _read(z / "type") in CPU_ZONES:
            for t in z.glob("trip_point_*_type"):
                if _read(t) in TRIP_TYPES:
                    add(t.with_name(t.name.replace("_type", "_temp")))
    for h in sorted((sys_root / "class/hwmon").glob("hwmon*")):
        if _read(h / "name") in CPU_HWMON:
            for suffix in ("crit", "max"):
                for f in h.glob(f"temp*_{suffix}"):
                    add(f)
    return out


def max_temp_c(sys_root: Path = Path("/sys")) -> float:
    v = _env_float("AQ_POWER_GATE_MAX_TEMP_C")
    if v is not None:
        return v
    trips = cpu_trip_points(sys_root)
    if not trips:
        return MAX_TEMP_C
    margin = _env_float("AQ_POWER_GATE_TEMP_MARGIN_C")
    margin = TEMP_MARGIN_C if margin is None else max(0.0, margin)
    return min(TEMP_CEIL_C, max(TEMP_FLOOR_C, min(trips) - margin))


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
    min_bat = min_battery_pct()
    max_temp = max_temp_c(sys_root)
    readings["max_temp_c"] = max_temp
    if ac is None and bat is None:
        reasons.append("power state unreadable")
    elif not ac and (bat is None or bat < min_bat):
        reasons.append(f"on battery below {min_bat}% (battery={bat})")
    if load5 is None:
        reasons.append("loadavg unreadable")
    elif _load_busy(load5, ncpu, state_file):
        reasons.append(
            f"load5 {load5:.2f} busy (ncpu={ncpu}, enter>={BUSY_ENTER * ncpu:.2f}, "
            f"leave<={BUSY_LEAVE * ncpu:.2f})"
        )
    if temp is None:
        reasons.append("cpu temp unreadable")
    elif temp >= max_temp:
        reasons.append(f"cpu temp {temp:.0f}C >= {max_temp:.0f}C")
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
            fd = os.open(a.defer_log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(fd, "a") as f:  # 0600 like outcome-receipts.jsonl: task text is prompt-derived
                f.write(
                    json.dumps({"ts": int(time.time()), "task": a.task[:200], **d})
                    + "\n"
                )
        except OSError:
            pass
    return DEFER_EXIT


if __name__ == "__main__":
    sys.exit(main())
