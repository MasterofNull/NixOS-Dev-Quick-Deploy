#!/usr/bin/env python3
"""model_budget — derive a per-device model rebudget policy from hw_probe (WS-EDGE).

Operator insight (god-tier prompt 6): the SMALL_RESIDENT rebudget should NOT be
a one-time manual quant decision for one machine — it should be HARDWARE-DRIVEN,
so every new environment/device auto-configures its own model plan. This layer
consumes hw_probe's detection and outputs a budget: main-model size+quant, KV
budget, and whether a small resident model (SMALL_RESIDENT tier) fits — plus the
concrete deployment knobs.

Pure policy over measured facts; no I/O beyond calling hw_probe. Deterministic
so it can drive a generated Nix profile (the E1 -> profile pipeline).

CLI:
    model_budget.py            # print the budget for THIS host (JSON)
    model_budget.py --summary  # one-line human summary
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Optional

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

# Reserve for OS + page cache headroom (never allocate the last GB).
_OS_RESERVE_GB = 3.0
# KV cache budget scales gently with context; anchor from the Renoir baseline.
_KV_BUDGET_GB = 1.0
# Approx GGUF resident size per billion params by quant (GB/B), measured-ish.
_QUANT_GB_PER_B = {"Q8_0": 1.05, "Q6_K": 0.82, "Q5_K_S": 0.66, "Q5_K_M": 0.70,
                   "Q4_K_M": 0.58, "Q4_K_S": 0.54, "Q3_K_M": 0.46, "Q2_K": 0.35}
# Small resident model candidates per available small-budget (GB -> spec).
_SMALL_CANDIDATES = [
    (2.0, {"b_params": 1.7, "quant": "Q6_K", "example": "Qwen2.5-1.5B-Instruct Q6_K"}),
    (1.2, {"b_params": 1.5, "quant": "Q4_K_M", "example": "Qwen2.5-1.5B-Instruct Q4_K_M"}),
    (0.7, {"b_params": 0.6, "quant": "Q4_K_M", "example": "Qwen2.5-0.5B-Instruct Q4_K_M"}),
]


def _ram_total_gb(probe: dict) -> Optional[float]:
    tb = ((probe.get("ram") or {}).get("total_bytes"))
    return round(tb / 1e9, 1) if tb else None


def _quant_size_gb(b_params: float, quant: str) -> float:
    return round(b_params * _QUANT_GB_PER_B.get(quant, 0.6), 1)


def derive_budget(probe: dict) -> dict[str, Any]:
    """Return the model budget policy for a probed host."""
    derived = probe.get("derived") or {}
    hw_class = derived.get("hardware_class")
    msc = derived.get("model_size_class") or {}
    main_b = float(msc.get("max_local_model_b_params") or 0) or 7.0
    main_quant = msc.get("quant_ladder_step") or "Q4_K_M"
    ram_gb = _ram_total_gb(probe) or 8.0

    main_size = _quant_size_gb(main_b, main_quant)
    usable = ram_gb - _OS_RESERVE_GB - _KV_BUDGET_GB
    slack_at_current = round(usable - main_size, 1)

    # Can a small resident model fit alongside the main model at current quant?
    small = _pick_small(slack_at_current)
    small_fits_now = small is not None

    # If not, would a one-step quant-down of the main model free enough?
    quant_down = _quant_down(main_quant)
    freed = None
    small_after_quantdown = None
    if not small_fits_now and quant_down:
        size_after = _quant_size_gb(main_b, quant_down)
        freed = round(main_size - size_after, 1)
        small_after_quantdown = _pick_small(round(usable - size_after, 1))

    # Recommendation policy per hardware class.
    if small_fits_now:
        rec = "deploy_small_resident_now"
        reason = f"{slack_at_current}GB slack fits a small resident model at current quant"
    elif small_after_quantdown:
        rec = "quant_down_then_small_resident"
        reason = (f"only {slack_at_current}GB slack at {main_quant}; "
                  f"{main_quant}->{quant_down} frees ~{freed}GB to fit a small resident model")
    else:
        rec = "single_model_only"
        reason = f"{ram_gb}GB cannot host a second resident model even after quant-down; use fleet node or defer"

    return {
        "hardware_class": hw_class,
        "ram_total_gb": ram_gb,
        "os_reserve_gb": _OS_RESERVE_GB,
        "kv_budget_gb": _KV_BUDGET_GB,
        "main_model": {"b_params": main_b, "quant": main_quant, "size_gb": main_size},
        "slack_gb_at_current_quant": slack_at_current,
        "small_resident": {
            "fits_at_current_quant": small_fits_now,
            "candidate_now": small,
            "requires_quant_down": (not small_fits_now and small_after_quantdown is not None),
            "quant_down_to": quant_down if (not small_fits_now and small_after_quantdown) else None,
            "freed_by_quant_down_gb": freed,
            "candidate_after_quant_down": small_after_quantdown,
        },
        "recommendation": rec,
        "reason": reason,
    }


def _pick_small(budget_gb: float) -> Optional[dict]:
    for need, spec in _SMALL_CANDIDATES:
        if budget_gb >= need:
            return {**spec, "size_gb": _quant_size_gb(spec["b_params"], spec["quant"])}
    return None


def _quant_down(quant: str) -> Optional[str]:
    ladder = ["Q8_0", "Q6_K", "Q5_K_M", "Q5_K_S", "Q4_K_M", "Q4_K_S", "Q3_K_M", "Q2_K"]
    try:
        i = ladder.index(quant)
    except ValueError:
        return "Q4_K_M"
    return ladder[i + 1] if i + 1 < len(ladder) else None


def budget_for_host() -> dict[str, Any]:
    import hw_probe  # type: ignore
    probe = hw_probe.probe() if hasattr(hw_probe, "probe") else json.loads(
        __import__("subprocess").run([sys.executable, os.path.join(_LIB, "hw_probe.py")],
                                     capture_output=True, text=True).stdout)
    return derive_budget(probe)


if __name__ == "__main__":
    b = budget_for_host()
    if "--summary" in sys.argv:
        sr = b["small_resident"]
        detail = (sr["candidate_now"] or sr["candidate_after_quant_down"] or {}).get("example", "n/a")
        print(f"[{b['hardware_class']}] {b['ram_total_gb']}GB · main "
              f"{b['main_model']['b_params']}B {b['main_model']['quant']} "
              f"({b['main_model']['size_gb']}GB) · slack {b['slack_gb_at_current_quant']}GB · "
              f"{b['recommendation']} → small: {detail}")
    else:
        print(json.dumps(b, indent=2))
