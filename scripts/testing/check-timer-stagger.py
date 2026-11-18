#!/usr/bin/env python3
"""Assert every ai-*/aq-* systemd timer in the host config is staggered.

Evaluates systemd.timers (no build, no switch) and requires, per matching
timer: RandomizedDelaySec > 0, AccuracySec set, Persistent not true
(catch-up stampede), plus distinct heavy-unit boot slots. See
nix/modules/core/timer-stagger.nix and
docs/harness-first/evidence/2026-11-18-timer-stagger.md.

Usage: check-timer-stagger.py [--host hyperd-ai-dev] [--json-file timers.json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

PREFIXES = ("ai-", "aq-")
HEAVY = (
    "ai-prsi-orchestrator", "ai-optimizer", "ai-aidb-reindex", "ai-prompt-eval",
    "ai-local-training-loop", "ai-training-ingest", "ai-gap-auto-remediate",
)
APPLY = "ts: builtins.mapAttrs (n: t: t.timerConfig or {}) ts"
UNITS = {"us": 1e-6, "ms": 1e-3, "s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "d": 86400}


def seconds(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    total = 0.0
    for num, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([a-z]*)", str(value)):
        total += float(num) * UNITS.get(unit or "s", 0)
    return total


def load(host: str, json_file: str | None) -> dict:
    if json_file:
        with open(json_file, encoding="utf-8") as fh:
            return json.load(fh)
    cmd = ["nice", "-n", "19", "nix", "eval", "--json",
           f".#nixosConfigurations.{host}.config.systemd.timers", "--apply", APPLY]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        raise SystemExit(f"FAIL: nix eval exited {res.returncode}")
    return json.loads(res.stdout)


def check(timers: dict) -> list[str]:
    errs: list[str] = []
    scoped = {n: c for n, c in timers.items() if n.startswith(PREFIXES)}
    if not scoped:
        return ["no ai-*/aq-* timers found (wrong host or eval shape?)"]
    for name, cfg in sorted(scoped.items()):
        if seconds(cfg.get("RandomizedDelaySec", 0)) <= 0:
            errs.append(f"{name}: RandomizedDelaySec missing or 0")
        if not cfg.get("AccuracySec"):
            errs.append(f"{name}: AccuracySec unset")
        if cfg.get("Persistent") is True:
            errs.append(f"{name}: Persistent=true (boot catch-up stampede)")
    slots: dict[float, str] = {}
    for name in HEAVY:
        boot = timers.get(name, {}).get("OnBootSec")
        if boot is None:
            continue
        sec = seconds(boot)
        if sec in slots:
            errs.append(f"{name}: OnBootSec {boot} collides with {slots[sec]}")
        slots[sec] = name
    print(f"checked {len(scoped)} ai-*/aq-* timers; {len(slots)} heavy boot slots")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="hyperd-ai-dev")
    ap.add_argument("--json-file")
    args = ap.parse_args()
    errs = check(load(args.host, args.json_file))
    for e in errs:
        print(f"FAIL: {e}", file=sys.stderr)
    print("PASS" if not errs else f"FAIL ({len(errs)} issues)")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
