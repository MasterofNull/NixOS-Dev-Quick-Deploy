#!/usr/bin/env python3
"""Slice-brief `checks:` and `caps:` parser, validator and per-run measurement.

Brief format (see .agent/skills/slice-authoring/SKILL.md section 9):

    checks:
      command: python3 scripts/testing/test-x.py
      end_state: exit 0 and the output ends with OK
    caps:
      tier: medium            # small | medium | large; sets the defaults below
      input_tokens: 12000     # optional override
      output_tokens: 4000     # optional override
      max_turns: 8
      stop_condition: stop and report to the orchestrator when any cap is hit

Legacy flat fields (check_command, token_budget, turn_cap) are accepted as aliases.

Configuration (no hardwired limits): the tier table comes from config/brief-caps-tiers.json
(override the path with AQ_BRIEF_TIERS_FILE; built-in defaults apply if unreadable); caps are
clamped to the lane context size when known (AQ_BRIEF_LANE_CTX, or AQ_BRIEF_LANE_MODEL naming a
model in config/model-coordinator.json); the checks FAIL date is overridable with
AQ_BRIEF_CHECKS_FAIL_FROM (ISO date, or "never").

Enforcement: validation only (WARN now, FAIL from CHECKS_FAIL_FROM). Token caps are enforced
by a delegate only where it has a hook (delegate-to-local passes output_tokens as max_tokens);
everywhere else they are recorded for measurement in <delegation-dir>/brief-caps.jsonl.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# Built-in fallbacks; config/brief-caps-tiers.json (or AQ_BRIEF_TIERS_FILE) overrides them.
_BUILTIN_TIERS = {
    "small": {"input_tokens": 2000, "output_tokens": 500, "max_turns": 4},
    "medium": {"input_tokens": 12000, "output_tokens": 4000, "max_turns": 8},
    "large": {"input_tokens": 24000, "output_tokens": 8000, "max_turns": 12},
}
DEFAULT_TIER = "medium"
_BUILTIN_CLAMP = {"input_fraction": 0.5, "output_fraction": 0.25}
_REPO = Path(__file__).resolve().parents[3]
TIERS_FILE = _REPO / "config" / "brief-caps-tiers.json"
COORDINATOR_FILE = _REPO / "config" / "model-coordinator.json"
# Policy default (missing `checks` is WARN before, FAIL on/after); AQ_BRIEF_CHECKS_FAIL_FROM overrides.
_DEFAULT_CHECKS_FAIL_FROM = _dt.date(2026, 12, 2)
CHECKS_FAIL_FROM = _DEFAULT_CHECKS_FAIL_FROM
DEFAULT_STOP = "stop and report to the orchestrator when any cap is hit"
LOG = "brief-caps.jsonl"

def _read_json(path: Path) -> dict:
    try:
        v = json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def load_config() -> dict:
    """Tier table, default tier and lane clamp fractions; invalid entries fall back to built-ins."""
    raw = _read_json(Path(os.environ.get("AQ_BRIEF_TIERS_FILE") or TIERS_FILE))
    tiers: dict = {}
    for name, vals in (raw.get("tiers") or {}).items():
        try:
            tiers[str(name).lower()] = {k: int(vals[k]) for k in ("input_tokens", "output_tokens", "max_turns")
                                        if int(vals[k]) > 0}
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if len(tiers[str(name).lower()]) != 3:
            del tiers[str(name).lower()]
    if not tiers:
        tiers = {k: dict(v) for k, v in _BUILTIN_TIERS.items()}
    clamp = dict(_BUILTIN_CLAMP)
    for k, v in (raw.get("lane_clamp") or {}).items():
        try:
            if k in clamp and 0 < float(v) <= 1:
                clamp[k] = float(v)
        except (TypeError, ValueError):
            pass
    default = str(raw.get("default_tier") or "").lower()
    if default not in tiers:
        default = DEFAULT_TIER if DEFAULT_TIER in tiers else sorted(tiers)[0]
    return {"tiers": tiers, "default_tier": default, "lane_clamp": clamp}


def lane_context() -> Optional[int]:
    """Lane context size in tokens, or None when unknown (then caps are not clamped)."""
    env = os.environ.get("AQ_BRIEF_LANE_CTX", "").strip()
    if env:
        try:
            n = int(env.replace("_", ""))
            return n if n > 0 else None
        except ValueError:
            return None
    model = os.environ.get("AQ_BRIEF_LANE_MODEL", "").strip()
    if model:
        n = ((_read_json(COORDINATOR_FILE).get("models") or {}).get(model) or {}).get("max_context_tokens")
        return n if isinstance(n, int) and n > 0 else None
    return None


def checks_fail_from() -> Optional[_dt.date]:
    """Date from which missing `checks` is an error; None means never. Env wins over the default."""
    env = os.environ.get("AQ_BRIEF_CHECKS_FAIL_FROM", "").strip()
    if not env:
        return CHECKS_FAIL_FROM
    if env.lower() in ("never", "off", "none"):
        return None
    try:
        return _dt.date.fromisoformat(env)
    except ValueError:
        return CHECKS_FAIL_FROM


_KV = re.compile(r"^(\s*)(?:-\s+)?([A-Za-z_][\w-]*):\s*(.*?)\s*$")


def _scalar(v: str) -> str:
    v = re.sub(r"\s+#.*$", "", v).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def parse_brief(text: str) -> dict:
    """Return {'checks': {...}, 'caps': {...}} from top-level blocks plus legacy flat fields."""
    out: dict = {"checks": {}, "caps": {}}
    block: Optional[str] = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _KV.match(line)
        if not m:
            continue
        indent, key, val = len(m.group(1)), m.group(2), _scalar(m.group(3))
        if indent == 0:
            block = key if key in out and not val else None
            if block:
                continue
            if key == "check_command" and val:
                out["checks"].setdefault("command", val)
            elif key == "token_budget" and val:
                out["caps"].setdefault("token_budget", val)
            elif key == "turn_cap" and val:
                out["caps"].setdefault("max_turns", val)
        elif block:
            out[block][key] = val
    return out


def resolve_caps(caps: dict, lane_ctx: Optional[int] = None) -> dict:
    """Apply tier defaults; explicit values win. Raises ValueError on a bad tier or number.

    Tier-derived token caps are clamped to the lane context (lane_ctx, else lane_context());
    explicit brief values are the author's choice and are only flagged via `clamped_to_lane`
    when they exceed the lane budget, never silently changed.
    """
    cfg = load_config()
    tiers = cfg["tiers"]
    tier = (caps.get("tier") or cfg["default_tier"]).lower()
    if tier not in tiers:
        raise ValueError(f"unknown tier {tier!r}; use one of {sorted(tiers)}")
    res: dict = dict(tiers[tier])
    ctx = lane_ctx if lane_ctx is not None else lane_context()
    limits: dict = {}
    if ctx:
        limits = {"input_tokens": max(1, int(ctx * cfg["lane_clamp"]["input_fraction"])),
                  "output_tokens": max(1, int(ctx * cfg["lane_clamp"]["output_fraction"]))}
        for k, lim in limits.items():
            res[k] = min(res[k], lim)
    for k in ("input_tokens", "output_tokens", "max_turns"):
        if caps.get(k) not in (None, ""):
            try:
                n = int(str(caps[k]).replace("_", ""))
            except ValueError:
                raise ValueError(f"caps.{k} must be an integer, got {caps[k]!r}") from None
            if n <= 0:
                raise ValueError(f"caps.{k} must be positive")
            res[k] = n
    if caps.get("token_budget") and "input_tokens" not in caps:
        # Legacy single budget: treat as the input cap; output stays at the tier default.
        try:
            n = int(str(caps["token_budget"]).replace("_", ""))
        except ValueError:
            raise ValueError(f"caps.token_budget must be an integer, got {caps['token_budget']!r}") from None
        if n <= 0:
            raise ValueError("caps.token_budget must be positive")
        res["input_tokens"] = n
    res["tier"] = tier
    if limits:
        res["lane_ctx"] = ctx
        res["over_lane_budget"] = sorted(k for k, lim in limits.items() if res[k] > lim)
    res["stop_condition"] = caps.get("stop_condition") or DEFAULT_STOP
    return res


def validate(text: str, today: Optional[_dt.date] = None) -> dict:
    """Return {'errors': [...], 'warnings': [...], 'caps': resolved-or-None}."""
    today = today or _dt.date.today()
    b = parse_brief(text)
    errors: list[str] = []
    warnings: list[str] = []
    if not b["checks"].get("command"):
        msg = "missing required 'checks.command' (deterministic command plus checks.end_state)"
        fail_from = checks_fail_from()
        if fail_from is not None and today >= fail_from:
            errors.append(msg)
        elif fail_from is not None:
            warnings.append(msg + f"; becomes FAIL on {fail_from.isoformat()}")
        else:
            warnings.append(msg)
    elif not b["checks"].get("end_state"):
        warnings.append("checks.end_state not stated: say what a pass looks like")
    if not b["caps"]:
        warnings.append(f"no 'caps' block; tier defaults ({load_config()['default_tier']}) will be recorded")
    resolved = None
    try:
        resolved = resolve_caps(b["caps"])
    except ValueError as e:
        errors.append(str(e))
    return {"errors": errors, "warnings": warnings, "caps": resolved}


def measure(delegation_dir: Path, run_id: str, brief_text: str, *, lane: str = "local",
            turns: Optional[int] = None, now: Optional[str] = None) -> dict:
    """Append actual-vs-cap tokens/turns for one run to <delegation-dir>/brief-caps.jsonl.

    Actuals come from the registry row (dispatch folds .usage.json into it) and fall back to
    outputs/<run_id>.log.usage.json; elapsed time comes from the .timing.json receipt.
    """
    d = Path(delegation_dir)
    row: dict = {}
    try:
        for ln in (d / "registry.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("id") == run_id:
                row = r
    except OSError:
        pass
    out_file = Path(row.get("output_file") or d / "outputs" / f"{run_id}.log")
    side = _load(Path(str(out_file) + ".usage.json"))
    tin = row.get("tokens_in") if isinstance(row.get("tokens_in"), int) else side.get("tokens_in")
    tout = row.get("tokens_out") if isinstance(row.get("tokens_out"), int) else side.get("tokens_out")
    timing = _load(Path(str(out_file) + ".timing.json"))
    b = parse_brief(brief_text)
    try:
        caps = resolve_caps(b["caps"])
    except ValueError:
        caps = resolve_caps({})
    def within(actual, cap):
        return None if not isinstance(actual, int) else actual <= cap
    rec = {
        "schema": "aq.brief-caps.v1",
        "recorded_at": now or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": run_id,
        "lane": lane,
        "tier": caps["tier"],
        "checks_declared": bool(b["checks"].get("command")),
        "caps": {k: caps[k] for k in ("input_tokens", "output_tokens", "max_turns")},
        "actual": {"input_tokens": tin if isinstance(tin, int) else None,
                   "output_tokens": tout if isinstance(tout, int) else None,
                   "turns": turns},
        "within_caps": {"input_tokens": within(tin, caps["input_tokens"]),
                        "output_tokens": within(tout, caps["output_tokens"]),
                        "turns": within(turns, caps["max_turns"])},
        "elapsed_seconds": timing.get("request_elapsed_seconds"),
    }
    d.mkdir(parents=True, exist_ok=True)
    fd = os.open(d / LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (json.dumps(rec, sort_keys=True) + "\n").encode())
    finally:
        os.close(fd)
    return rec


def _load(p: Path) -> dict:
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def summarize(records: list[dict]) -> dict:
    """Raw counts for the scoreboard: runs, unknown actuals, and over-cap runs per dimension."""
    s = {"runs": len(records), "no_checks_declared": 0,
         "over_cap": {"input_tokens": 0, "output_tokens": 0, "turns": 0},
         "unknown": {"input_tokens": 0, "output_tokens": 0, "turns": 0}}
    for r in records:
        if not r.get("checks_declared"):
            s["no_checks_declared"] += 1
        for k, v in (r.get("within_caps") or {}).items():
            if k in s["over_cap"]:
                if v is None:
                    s["unknown"][k] += 1
                elif v is False:
                    s["over_cap"][k] += 1
    return s


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="WARN/FAIL on a brief file (exit 1 on errors)")
    v.add_argument("file")
    o = sub.add_parser("output-tokens", help="print the resolved output_tokens cap")
    o.add_argument("file")
    m = sub.add_parser("measure", help="append actual-vs-cap for one run")
    m.add_argument("file")
    m.add_argument("--run-id", required=True)
    m.add_argument("--delegation-dir", required=True)
    m.add_argument("--lane", default="local")
    m.add_argument("--turns", type=int)
    a = ap.parse_args(argv)
    text = Path(a.file).read_text(encoding="utf-8")
    if a.cmd == "validate":
        r = validate(text)
        for w in r["warnings"]:
            print(f"WARN: {w}")
        for e in r["errors"]:
            print(f"FAIL: {e}")
        if r["caps"]:
            print("caps: " + json.dumps(r["caps"], sort_keys=True))
        return 1 if r["errors"] else 0
    if a.cmd == "output-tokens":
        try:
            print(resolve_caps(parse_brief(text)["caps"])["output_tokens"])
        except ValueError:
            return 1
        return 0
    print(json.dumps(measure(Path(a.delegation_dir), a.run_id, text, lane=a.lane, turns=a.turns),
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
