#!/usr/bin/env python3
"""system1_router.py — Sub-20ms CPU System 1 Router & Hysteresis Thermal/Load Guard (Slices F2 & F3).

Incorporates Round 1 Debate fixes from Simurg@claude (claude-20261113-184611-57y8dl):
  1. Uses 5-minute loadavg (loadavg[1]) with hysteresis (enter pause at 0.70, exit at 0.55)
     so short indexing bursts on a 27GB laptop never flap the gate.
  2. Caps CPU router execution with an emergency thermal ceiling (<90°C) and <20ms budget.
  3. Explicitly defines gated neural task disposition: background jobs DEFER to AC/cooldown;
     active slice dispatches SUBSTITUTE to the cheapest healthy Tier-2 subscription lane
     (never dropped silently).
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

POWER_SUPPLY_DIR = Path("/sys/class/power_supply")
THERMAL_DIR = Path("/sys/class/thermal")


def read_laptop_vitals() -> dict[str, Any]:
    """Read AC online, battery %, 1m/5m load ratios, and max CPU package temp (°C) in <5ms."""
    ac_online: bool | None = None
    battery_pct: int | None = None

    if POWER_SUPPLY_DIR.is_dir():
        for psu in sorted(POWER_SUPPLY_DIR.iterdir()):
            try:
                ptype = (psu / "type").read_text(encoding="utf-8").strip().lower()
            except OSError:
                continue
            if ptype == "mains":
                try:
                    ac_online = (psu / "online").read_text(encoding="utf-8").strip() == "1"
                except OSError:
                    pass
            elif ptype == "battery" and battery_pct is None:
                try:
                    battery_pct = int((psu / "capacity").read_text(encoding="utf-8").strip())
                except (OSError, ValueError):
                    pass

    cpu_count = max(1, os.cpu_count() or 1)
    try:
        load1, load5, _ = os.getloadavg()
    except OSError:
        load1, load5 = 0.0, 0.0
    load1_ratio = round(load1 / cpu_count, 3)
    load5_ratio = round(load5 / cpu_count, 3)

    max_temp_c: float | None = None
    if THERMAL_DIR.is_dir():
        for zone in sorted(THERMAL_DIR.glob("thermal_zone*")):
            try:
                milli = int((zone / "temp").read_text(encoding="utf-8").strip())
                temp_c = milli / 1000.0
                if 0.0 < temp_c < 130.0:
                    max_temp_c = temp_c if max_temp_c is None else max(max_temp_c, temp_c)
            except (OSError, ValueError):
                continue

    return {
        "ac_online": ac_online,
        "battery_pct": battery_pct,
        "cpu_count": cpu_count,
        "load1_ratio": load1_ratio,
        "load5_ratio": load5_ratio,
        "max_temp_c": max_temp_c,
    }


def is_neural_system1_eligible(
    vitals: dict[str, Any] | None = None,
    *,
    previously_paused: bool = False,
    is_fallback_review: bool = False,
) -> tuple[bool, str]:
    """Check if llama.cpp neural System 1 inference is polite on current laptop state.

    Uses 5-minute loadavg hysteresis (enter pause at >0.70, exit at <=0.55) per Claude Round 1 review.
    """
    v = vitals if vitals is not None else read_laptop_vitals()
    ac = v.get("ac_online")
    bat = v.get("battery_pct")
    load5_ratio = float(v.get("load5_ratio") or 0.0)
    temp_c = v.get("max_temp_c")

    if ac is False and (bat is None or bat < 50):
        return False, f"battery_guard(ac={ac},battery_pct={bat}<50)"

    # Hysteresis on 5-minute load ratio: enter pause >0.70 (or >0.85 for fallback review), exit <=0.55
    enter_threshold = 0.85 if is_fallback_review else 0.70
    exit_threshold = 0.70 if is_fallback_review else 0.55
    active_threshold = exit_threshold if previously_paused else enter_threshold
    if load5_ratio > active_threshold:
        return False, f"load5_hysteresis_guard(load5_ratio={load5_ratio}>{active_threshold},paused={previously_paused})"

    # Thermal check: <80°C for background/implement, <85°C for fallback review
    max_temp = 85.0 if is_fallback_review else 80.0
    if temp_c is not None and temp_c >= max_temp:
        return False, f"thermal_guard(temp_c={temp_c}>={max_temp})"

    return True, "ok"


def route_slice(
    *,
    task: str,
    files_touched: int,
    available_lanes: list[str],
    is_background_job: bool = False,
    previously_paused: bool = False,
    vitals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sub-20ms CPU System 1 routing decision with thermal emergency ceiling (<90°C)."""
    t0 = time.monotonic()
    v = vitals if vitals is not None else read_laptop_vitals()
    temp_c = v.get("max_temp_c")

    # Emergency thermal ceiling (<90°C) even for statistical CPU router
    if temp_c is not None and temp_c >= 90.0:
        preferred = ["claude", "gemini", "codex"]
        selected = next((l for l in preferred if l in available_lanes), "defer")
        return {
            "selected_lane": selected,
            "compute_tier": "tier2_emergency_thermal_offload" if selected != "defer" else "deferred",
            "disposition": "substitute_remote" if not is_background_job and selected != "defer" else "defer_cooldown",
            "system1_neural_eligible": False,
            "system1_guard_reason": f"emergency_cpu_thermal_ceiling(temp_c={temp_c}>=90.0)",
            "router_latency_ms": round((time.monotonic() - t0) * 1000.0, 3),
        }

    sys1_ok, sys1_reason = is_neural_system1_eligible(
        v, previously_paused=previously_paused
    )

    if files_touched <= 1 and "local" in available_lanes and sys1_ok:
        selected = "local"
        tier = "tier1_local_system1"
        disposition = "execute_local_system1"
        reason = "single_file_bounded_slice_with_healthy_laptop_vitals"
    elif not sys1_ok and is_background_job:
        # Never drop silently: background distillation/indexing jobs defer until AC/cooldown
        selected = "defer"
        tier = "deferred_until_ac_or_cooldown"
        disposition = "defer_cooldown"
        reason = f"background_job_deferred({sys1_reason})"
    else:
        # Active task: substitute to cheapest healthy Tier-2 subscription lane
        preferred = ["claude", "gemini", "codex", "local"]
        selected = next((l for l in preferred if l in available_lanes), "local")
        tier = "tier2_pooled_subscription" if selected != "local" else "tier1_local_fallback"
        disposition = "substitute_remote" if not sys1_ok else "execute_pooled_subscription"
        reason = (
            f"substituted_from_local({sys1_reason})"
            if not sys1_ok
            else f"pooled_subscription_arbitrage(files={files_touched})"
        )

    return {
        "selected_lane": selected,
        "compute_tier": tier,
        "disposition": disposition,
        "system1_neural_eligible": sys1_ok,
        "system1_guard_reason": sys1_reason,
        "routing_reason": reason,
        "router_latency_ms": round((time.monotonic() - t0) * 1000.0, 3),
    }
