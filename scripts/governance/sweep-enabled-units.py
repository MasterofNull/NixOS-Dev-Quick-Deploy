#!/usr/bin/env python3
"""sweep-enabled-units: check every project systemd unit and timer against live state.

Recovery sweep P2.3 (.agents/plans/system-integrity-recovery/DESIGN.md, section P2). Read-only: only
`systemctl list-unit-files|show|cat` and filesystem stats; no unit, tracker or backlog edits. A fact that
cannot be determined is reported as "unknown" and is never counted as a pass. Without systemd (CI) the
script says so and exits 0 with a skip reason.

Scope filter (names): SCOPE_RE below, system and user scope, unioned with every literal unit name that a
nix/ module declares under systemd.{services,timers,sockets,paths} / systemd.user.*. Names built with
${...} cannot be resolved statically and are counted as `nix_dynamic_unresolved`.

Finding classes:
  FAILED           enabled/in-scope unit failed, or a long-running service sits inactive after exiting
  NEVER_RAN        timer or service enabled long enough ago to have fired but never did
  STALE_TIMER      timer last fired far beyond its interval, or its last service run did not succeed
  NO_OUTPUT        service succeeded but its declared state/log path is missing or stale
  DECLARED_MISSING a nix module declares a unit that does not exist, or it exists disabled
  RESTART_LOOP     NRestarts above threshold
  RETIRED_REF      unit name/ExecStart/Environment/Description mentions antigravity (retired IDE lane)
  BROKEN_EXEC      ExecStart executable or a checkout-path script argument no longer exists

Usage: sweep-enabled-units.py [--json] [--report PATH] [--fail-on CLASS,...] [--repo DIR]
                              [--fixture FILE] [--dump-fixture FILE]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

DEFAULT_REPO = Path(__file__).resolve().parents[2]
CLASSES = ("FAILED", "NEVER_RAN", "STALE_TIMER", "NO_OUTPUT", "DECLARED_MISSING", "RESTART_LOOP",
           "RETIRED_REF", "BROKEN_EXEC")
SCOPE_RE = re.compile(
    r"^(ai-|aq-|aidb|prsi|llama|coordinator|switchboard|dashboard|command-center|hybrid|mcp-|redis-mcp|"
    r"qdrant|postgresql|nixos-ai|ralph|harness|agentic|antigravity)", re.I)
UNIT_SUFFIXES = (".service", ".timer", ".socket", ".path", ".target")
RESTART_LIMIT = 5
STALE_FACTOR = 3.0
GRACE_S = 600
NEVER_RAN_MIN_AGE_S = 3600
SHOW_PROPS = ("Id,LoadState,ActiveState,SubState,Result,NRestarts,ExecMainStatus,ExecMainStartTimestamp,"
              "ExecMainExitTimestamp,ActiveEnterTimestamp,InactiveEnterTimestamp,ExecStart,Type,"
              "RemainAfterExit,FragmentPath,UnitFileState,Description,Environment,StateDirectory,"
              "LogsDirectory,ConditionResult,TriggeredBy,Triggers,Unit,LastTriggerUSec,"
              "TimersCalendar,TimersMonotonic,WorkingDirectory")
ENV_DIR_RE = re.compile(r"(STATE|LOG|OUTPUT|REPORT|DATA)[A-Z_]*(DIR|PATH)$")
LONG_RUNNING = {"simple", "exec", "notify", "notify-reload", "forking", "dbus", "idle"}
NIX_DECL_RE = re.compile(r"systemd\.(user\.)?(services|timers|sockets|paths)\.(\"[^\"]+\"|[A-Za-z0-9_${}-]+)\s*=")


def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


def to_epoch(v):
    """systemctl --timestamp=unix yields '@N'; empty, '0' and '@0' mean never."""
    v = (v or "").strip()
    if v.startswith("@"):
        v = v[1:]
    try:
        n = int(float(v))
    except ValueError:
        return None
    return n if n > 0 else None


def parse_show(text):
    props = {}
    for line in text.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            props.setdefault(k, v)
            if k in ("TimersCalendar", "TimersMonotonic"):
                props[k] = props[k] if props[k] == v else props[k] + "\n" + v
    return props


def parse_show_multi(text):
    """Parse `systemctl show a b c` output: blocks separated by blank lines; repeated timer keys joined."""
    out = []
    for block in text.strip().split("\n\n"):
        props = {}
        for line in block.splitlines():
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k in ("TimersCalendar", "TimersMonotonic") and k in props:
                props[k] += "\n" + v
            else:
                props.setdefault(k, v)
        if props.get("Id"):
            out.append(props)
    return out


def in_scope(name):
    return name.endswith(UNIT_SUFFIXES) and bool(SCOPE_RE.match(name))


def scan_nix(repo):
    """Literal unit names declared in nix/ modules. Returns (system, user, dynamic_count)."""
    system, user, dyn = {}, {}, 0
    root = Path(repo) / "nix"
    for p in sorted(root.rglob("*.nix")) if root.is_dir() else []:
        try:
            lines = p.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            m = NIX_DECL_RE.search(line)
            if not m:
                continue
            nm = m.group(3).strip('"')
            if "${" in nm:
                dyn += 1
                continue
            kind = {"services": "service", "timers": "timer", "sockets": "socket", "paths": "path"}[m.group(2)]
            block = "\n".join(lines[i:i + 40])
            nxt = re.search(r"\n\s*systemd\.", "\n".join(lines[i + 1:i + 40]))
            if nxt:
                block = "\n".join(lines[i:i + 1 + "\n".join(lines[i + 1:i + 40])[:nxt.start()].count("\n") + 1])
            rec = {"file": os.path.relpath(p, repo), "line": i + 1,
                   "wanted_by": "wantedBy" in block}
            (user if m.group(1) else system).setdefault(f"{nm}.{kind}", rec)
    return system, user, dyn


def collect_scope(scope, nix_names):
    flag = ["--user"] if scope == "user" else []
    rc, out = run(["systemctl", *flag, "list-unit-files", "--no-legend", "--no-pager", "--all"])
    files = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            files[parts[0]] = parts[1]
    names = sorted({n for n in files if in_scope(n)} | {n for n in nix_names if n in files})
    props = []
    for i in range(0, len(names), 40):
        _, o = run(["systemctl", *flag, "show", "--timestamp=unix", "--no-pager", "-p", SHOW_PROPS, *names[i:i + 40]])
        props += parse_show_multi(o)
    return {"unit_files": files, "units": {p["Id"]: p for p in props}}


CONTRACTS_REL = "config/sweep-output-contracts.json"


def load_contracts(repo):
    """Per-unit output contracts for units whose proof of work is not a file mtime under a declared path."""
    try:
        raw = json.loads((Path(repo) / CONTRACTS_REL).read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict) and not k.startswith("_")}


def journal_marker_epoch(unit, scope, marker):
    """Epoch of the newest journal line of `unit` matching regex `marker`, or None."""
    flag = ["--user"] if scope == "user" else []
    rc, out = run(["journalctl", *flag, "-u", unit, "-g", marker, "-n", "1", "-o", "short-unix", "--no-pager", "-q"])
    first = out.strip().split(None, 1)[0] if out.strip() else ""
    try:
        return int(float(first))
    except ValueError:
        return None


def contract_env_nonzero(props, name):
    m = re.search(r"(?:^|\s)\"?" + re.escape(name) + r"=(\S*?)\"?(?:\s|$)", props.get("Environment") or "")
    return bool(m) and m.group(1).strip() not in ("", "0", "false", "no")


def exec_paths(execstart):
    """Executable paths and absolute argv words from systemctl's ExecStart= property text."""
    exes, args = [], []
    for m in re.finditer(r"path=(\S+) ; argv\[\]=([^;]*);", execstart or ""):
        exes.append(m.group(1))
        args += [a for a in m.group(2).split()[1:] if a.startswith("/")]
    return exes, args


def fs_facts(paths):
    out = {}
    for p in paths:
        try:
            st = os.stat(p)
        except FileNotFoundError:
            out[p] = {"exists": False, "mtime": None}
            continue
        except OSError:
            out[p] = {"exists": True, "mtime": None, "unreadable": True}
            continue
        newest = st.st_mtime
        if os.path.isdir(p):
            try:
                for e in os.scandir(p):
                    try:
                        newest = max(newest, e.stat().st_mtime) if e.name != "." else newest
                    except OSError:
                        pass
                out[p] = {"exists": True, "mtime": int(newest), "is_dir": True,
                          "empty": not any(True for _ in os.scandir(p))}
            except OSError:
                out[p] = {"exists": True, "mtime": None, "is_dir": True, "unreadable": True}
        else:
            out[p] = {"exists": True, "mtime": int(newest), "is_dir": False}
    return out


def declared_outputs(props, scope):
    paths = []
    base = ("/var/lib", "/var/log") if scope == "system" else (os.path.expanduser("~/.local/state"),) * 2
    for key, root in (("StateDirectory", base[0]), ("LogsDirectory", base[1])):
        for d in (props.get(key) or "").split():
            paths.append(d if d.startswith("/") else f"{root}/{d}")
    for m in re.finditer(r"([A-Z][A-Z0-9_]*)=(/[^\s]+)", props.get("Environment") or ""):
        if ENV_DIR_RE.search(m.group(1)) and not m.group(2).startswith("/nix/store"):
            paths.append(m.group(2))
    return sorted(set(paths))


def collect(repo):
    nix_sys, nix_user, dyn = scan_nix(repo)
    data = {"systemd": True, "now": int(time.time()), "repo": str(repo), "checkout_markers": [str(repo)],
            "nix": {"system": nix_sys, "user": nix_user, "dynamic": dyn}, "scopes": {}, "fs": {}}
    try:
        data["uptime"] = int(float(Path("/proc/uptime").read_text().split()[0]))
    except (OSError, ValueError):
        data["uptime"] = None
    paths = set()
    for scope, nx in (("system", nix_sys), ("user", nix_user)):
        data["scopes"][scope] = collect_scope(scope, nx)
        for p in data["scopes"][scope]["units"].values():
            exes, args = exec_paths(p.get("ExecStart"))
            paths.update(x for x in exes + args if not x.startswith("/nix/store"))
            paths.update(declared_outputs(p, scope))
    data["fs"] = fs_facts(sorted(paths))
    data["contracts"] = load_contracts(repo)
    data["journal_markers"] = {}
    for scope in ("system", "user"):
        for uid in data["scopes"][scope]["units"]:
            c = data["contracts"].get(uid)
            if c and c.get("journal_marker"):
                data["journal_markers"][f"{scope}:{uid}"] = journal_marker_epoch(uid, scope, c["journal_marker"])
    return data


def calendar_interval(spec):
    """Rough seconds between runs for an OnCalendar expression; None when it cannot be told."""
    s = spec.strip().lower()
    table = {"minutely": 60, "hourly": 3600, "daily": 86400, "weekly": 604800, "monthly": 2678400,
             "yearly": 31536000, "annually": 31536000, "quarterly": 7948800, "semiannually": 15811200}
    if s in table:
        return table[s]
    m = re.search(r"\*:(?:\*|\d+)?/(\d+)", s) or re.search(r"\*:0/(\d+)", s)
    if m:
        return int(m.group(1)) * 60
    m = re.search(r"\*-\*-\*\s+\*/(\d+):", s)
    if m:
        return int(m.group(1)) * 3600
    if re.search(r"\*-\*-\*\s+\*:", s) or re.match(r"^\*:\d+", s):
        return 3600
    if re.match(r"^(mon|tue|wed|thu|fri|sat|sun)", s):
        return 604800
    if re.search(r"\*-\*-\*\s+\d+:\d+", s):
        return 86400
    if re.search(r"\*-\*-\d+", s) or re.search(r"\*-\d+-\d+", s):
        return 2678400 if s.count("-") >= 2 and "*-*-" in s else 31536000
    return None


def timer_interval(props):
    cands = []
    for line in (props.get("TimersCalendar") or "").splitlines():
        m = re.search(r"OnCalendar=([^;}]*)", line)
        if m:
            iv = calendar_interval(m.group(1))
            if iv:
                cands.append(iv)
    for line in (props.get("TimersMonotonic") or "").splitlines():
        m = re.search(r"(OnUnitActiveUSec|OnUnitInactiveUSec)=([^;}]*)", line)
        if m:
            sec = parse_span(m.group(2))
            if sec:
                cands.append(sec)
    return min(cands) if cands else None


def parse_span(txt):
    units = {"us": 1e-6, "ms": 1e-3, "s": 1, "min": 60, "h": 3600, "d": 86400, "w": 604800, "month": 2629800, "y": 31557600}
    total = 0.0
    for n, u in re.findall(r"([\d.]+)\s*(month|min|ms|us|[smhdwy])", txt.strip()):
        total += float(n) * units[u]
    return total or None


def fmt_age(sec):
    sec = int(sec)
    for unit, n in (("d", 86400), ("h", 3600), ("m", 60)):
        if sec >= n:
            return f"{sec // n}{unit}"
    return f"{sec}s"


def analyse(data):
    """Pure function over collected facts. Returns the result dict."""
    findings, unknown = [], []
    now = data["now"]
    fs = data.get("fs", {})
    checked = {"system": 0, "user": 0}
    timers = []
    seen_exec_markers = data.get("checkout_markers") or []

    def add(cls, unit, scope, evidence, sev):
        findings.append({"class": cls, "unit": unit, "scope": scope, "severity": sev, "evidence": evidence})

    def unk(unit, scope, what):
        unknown.append({"unit": unit, "scope": scope, "what": what})

    for scope, sc in data["scopes"].items():
        units, files = sc["units"], sc["unit_files"]
        for name, p in sorted(units.items()):
            if p.get("LoadState") == "not-found":
                continue
            checked[scope] += 1
            active, sub, ufs = p.get("ActiveState", ""), p.get("SubState", ""), p.get("UnitFileState", "") or files.get(name, "")
            result = p.get("Result", "")
            typ = p.get("Type", "")
            is_timer = name.endswith(".timer")
            enabled = ufs in ("enabled", "enabled-runtime", "alias") or ufs == "static" and active == "active"
            triggered = bool((p.get("TriggeredBy") or "").strip())
            last_start = to_epoch(p.get("ExecMainStartTimestamp"))
            cond_skipped = p.get("ConditionResult") == "no"

            # RETIRED_REF
            hay = " ".join(p.get(k, "") for k in ("Id", "ExecStart", "Environment", "Description", "FragmentPath"))
            if "antigravity" in hay.lower():
                add("RETIRED_REF", name, scope, f"mentions antigravity (state={active}/{ufs}); IDE lane retired, nothing may wake it",
                    "high" if active in ("active", "activating") or enabled else "medium")

            # BROKEN_EXEC
            exes, args = exec_paths(p.get("ExecStart"))
            for x in exes:
                if x.startswith("/nix/store"):
                    continue
                if fs.get(x, {}).get("exists") is False:
                    add("BROKEN_EXEC", name, scope, f"ExecStart executable missing: {x}", "high" if enabled else "medium")
                elif x not in fs:
                    unk(name, scope, f"exec path {x} not stat-ed")
            for a in args:
                if a.startswith("/nix/store"):
                    continue
                if any(a.startswith(mk) for mk in seen_exec_markers) and fs.get(a, {}).get("exists") is False:
                    add("BROKEN_EXEC", name, scope, f"ExecStart script from checkout path missing: {a}", "high" if enabled else "medium")

            # RESTART_LOOP
            try:
                nr = int(p.get("NRestarts") or 0)
            except ValueError:
                nr = 0
            if nr >= RESTART_LIMIT:
                add("RESTART_LOOP", name, scope, f"NRestarts={nr} (state={active}/{sub}, result={result})", "high")

            # FAILED
            if active == "failed" or (result not in ("", "success") and not is_timer):
                add("FAILED", name, scope, f"ActiveState={active}/{sub} Result={result} ExecMainStatus={p.get('ExecMainStatus')}",
                    "high" if enabled else "medium")
            elif (enabled and not is_timer and not triggered and typ in LONG_RUNNING and active == "inactive"
                  and p.get("RemainAfterExit") != "yes" and not name.endswith(".target")):
                if cond_skipped:
                    unk(name, scope, "enabled long-running service inactive because a Condition* is false")
                elif last_start:
                    add("FAILED", name, scope, f"enabled {typ} service inactive; last started {fmt_age(now - last_start)} ago, Result={result}", "high")

            # NEVER_RAN (services)
            if (enabled and not is_timer and not name.endswith((".target", ".socket", ".path")) and not triggered
                    and active == "inactive" and not last_start and not cond_skipped
                    and p.get("RemainAfterExit") != "yes"):
                add("NEVER_RAN", name, scope, f"enabled service inactive, never started, no timer/path/socket triggers it", "medium")

            # timers
            if is_timer and ufs in ("enabled", "enabled-runtime", "static") or (is_timer and active == "active"):
                last = to_epoch(p.get("LastTriggerUSec"))
                iv = timer_interval(p)
                activated = to_epoch(p.get("ActiveEnterTimestamp"))
                uptime = data.get("uptime")
                tinfo = {"timer": name, "scope": scope, "last_trigger": last, "interval_s": iv, "active": active}
                svc = p.get("Unit") or name[:-6] + ".service"
                sp = units.get(svc)
                tinfo["last_service_result"] = sp.get("Result") if sp else None
                timers.append(tinfo)
                if active != "active":
                    add("FAILED", name, scope, f"enabled timer is {active}/{sub}", "high")
                elif not last:
                    age = (now - activated) if activated else None
                    # boot-relative timers are only judgeable once the host has been up past the threshold
                    ref_age = min(x for x in (age, uptime) if x is not None) if (age is not None or uptime is not None) else None
                    if ref_age is None:
                        unk(name, scope, "timer never triggered and age unknown")
                    elif ref_age > max(NEVER_RAN_MIN_AGE_S, (iv or 0) + GRACE_S):
                        add("NEVER_RAN", name, scope,
                            f"timer active {fmt_age(ref_age)} (interval {fmt_age(iv) if iv else 'unknown'}) with no trigger", "medium")
                    else:
                        unk(name, scope, f"timer not yet due (active {fmt_age(ref_age)})")
                else:
                    if iv is None:
                        unk(name, scope, f"timer interval not derivable; last fired {fmt_age(now - last)} ago")
                    elif now - last > iv * STALE_FACTOR + GRACE_S:
                        add("STALE_TIMER", name, scope,
                            f"last fired {fmt_age(now - last)} ago; interval ~{fmt_age(iv)} (limit {STALE_FACTOR:g}x)", "medium")
                if sp and last and sp.get("Result") not in ("", "success"):
                    add("STALE_TIMER", name, scope, f"last run of {svc} did not succeed: Result={sp.get('Result')}", "high")

            # NO_OUTPUT (service that succeeded)
            if name.endswith(".service") and result == "success" and (last_start or active == "active") and not cond_skipped:
                outs = declared_outputs(p, scope)
                contract = (data.get("contracts") or {}).get(name) or {}
                for cp, env in (contract.get("conditional_paths") or {}).items():
                    if cp in outs and not contract_env_nonzero(p, env):
                        outs.remove(cp)  # only written when `env` is enabled; not enabled here
                if contract.get("journal_marker"):
                    tm0 = next((t for t in sc["units"].values()
                                if t.get("Id", "").endswith(".timer") and (t.get("Unit") or t["Id"][:-6] + ".service") == name), None)
                    iv0 = timer_interval(tm0) if tm0 else None
                    lim0 = (iv0 * STALE_FACTOR + GRACE_S) if iv0 else None
                    seen = (data.get("journal_markers") or {}).get(f"{scope}:{name}", "absent")
                    if seen == "absent" or lim0 is None:
                        unk(name, scope, "journal output contract present but marker evidence or run interval unavailable")
                    elif seen is None or now - seen > lim0:
                        add("NO_OUTPUT", name, scope,
                            f"journal marker /{contract['journal_marker']}/ not seen in the last {fmt_age(lim0)}"
                            + (f" (last {fmt_age(now - seen)} ago)" if seen else " (never)"), "medium")
                    continue
                if not outs:
                    unk(name, scope, "no declared state/log path (StateDirectory, LogsDirectory, *_DIR env) to check output against")
                else:
                    tm = next((t for t in data["scopes"][scope]["units"].values()
                               if t.get("Id", "").endswith(".timer") and (t.get("Unit") or t["Id"][:-6] + ".service") == name), None)
                    iv = timer_interval(tm) if tm else None
                    limit = (iv * STALE_FACTOR + GRACE_S) if iv else None
                    for o in outs:
                        f = fs.get(o)
                        if f is None:
                            unk(name, scope, f"output path {o} not stat-ed")
                        elif not f.get("exists"):
                            add("NO_OUTPUT", name, scope, f"declared output path missing: {o}", "medium")
                        elif f.get("unreadable") or f.get("mtime") is None:
                            unk(name, scope, f"output path {o} unreadable without privilege")
                        elif f.get("is_dir") and f.get("empty"):
                            add("NO_OUTPUT", name, scope, f"declared output dir empty: {o}", "medium")
                        elif limit and now - f["mtime"] > limit:
                            add("NO_OUTPUT", name, scope,
                                f"{o} last written {fmt_age(now - f['mtime'])} ago; run interval ~{fmt_age(iv)}", "medium")
                        elif not limit:
                            unk(name, scope, f"{o} exists (written {fmt_age(now - f['mtime'])} ago) but no run interval to judge staleness")

    # DECLARED_MISSING
    for scope in ("system", "user"):
        files = data["scopes"].get(scope, {}).get("unit_files", {})
        for nm, rec in sorted(data["nix"].get(scope, {}).items()):
            if not nm.endswith((".service", ".timer", ".socket", ".path")):
                continue
            if nm not in files:
                add("DECLARED_MISSING", nm, scope,
                    f"declared at {rec['file']}:{rec['line']} but no unit file is installed (may sit behind a disabled mkIf)",
                    "medium" if rec.get("wanted_by") else "low")
            elif files[nm] in ("disabled", "masked") and rec.get("wanted_by"):
                add("DECLARED_MISSING", nm, scope,
                    f"declared with wantedBy at {rec['file']}:{rec['line']} but unit file state is {files[nm]}", "medium")

    counts = {c: sum(1 for f in findings if f["class"] == c) for c in CLASSES}
    sev = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (sev.get(f["severity"], 3), CLASSES.index(f["class"]), f["unit"]))
    return {"skipped": False, "now": now, "units_checked": checked, "timers_checked": len(timers), "timers": timers,
            "nix_declared": {s: len(data["nix"].get(s, {})) for s in ("system", "user")},
            "nix_dynamic_unresolved": data["nix"].get("dynamic", 0),
            "counts": counts, "findings": findings, "unknown": unknown}


def render_report(res, day, argv, notes):
    L = [f"# {day} sweep-enabled-units", "",
         "## Objective",
         "Recovery sweep P2.3 (system-integrity-recovery): every enabled project unit and timer is running and producing "
         "output, judged from live systemd state. Report only; no unit, tracker or backlog was changed.", "",
         "## Workflow/Session IDs",
         f"Branch feat/sweep-enabled-units, date {day}, host live systemd (system + user scope).", "",
         "## Delegation Decision",
         "Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17, bounded single-script slice with fixtures).", "",
         "## Commands Executed",
         f"- `scripts/governance/sweep-enabled-units.py {' '.join(argv)}`".rstrip(),
         "- `systemctl [--user] list-unit-files --all`, `systemctl [--user] show --timestamp=unix -p <props> <units>` (read-only)",
         "- Filesystem stat of ExecStart paths, StateDirectory/LogsDirectory and `*_DIR` environment paths", "",
         "## Scope and filter",
         f"- Name filter: `{SCOPE_RE.pattern}` (case-insensitive), unioned with literal unit names declared in `nix/` "
         f"(system {res['nix_declared']['system']}, user {res['nix_declared']['user']}); "
         f"{res['nix_dynamic_unresolved']} `${{...}}`-named declarations cannot be resolved statically.",
         f"- Units checked: system {res['units_checked']['system']}, user {res['units_checked']['user']}; "
         f"timers evaluated: {res['timers_checked']}.",
         "- Interval rules: OnUnitActive/Inactive span, or a rough OnCalendar estimate; STALE_TIMER = last fired beyond "
         f"{STALE_FACTOR:g}x interval + {GRACE_S}s; NEVER_RAN = timer or service up > {NEVER_RAN_MIN_AGE_S}s (and past its interval) with no run; "
         f"RESTART_LOOP = NRestarts >= {RESTART_LIMIT}.", "",
         "## Validation Evidence", "", "Counts per class:", "", "| Class | Count |", "|---|---|"]
    L += [f"| {c} | {n} |" for c, n in res["counts"].items()]
    L += ["", f"Total findings: {len(res['findings'])}. Unknown (not counted as pass): {len(res['unknown'])}.", "",
          "Findings:", "", "| # | Sev | Class | Scope | Unit | Evidence |", "|---|---|---|---|---|---|"]
    for i, f in enumerate(res["findings"], 1):
        ev = f["evidence"].replace("|", "\\|")
        L.append(f"| {i} | {f['severity']} | {f['class']} | {f['scope']} | `{f['unit']}` | {ev} |")
    if not res["findings"]:
        L.append("| - | - | - | - | none | - |")
    L += ["", "Unknown / not determinable:", ""]
    unk_by = {}
    for u in res["unknown"]:
        unk_by.setdefault(re.sub(r"/\S+|\d+\w*", "<x>", u["what"]), []).append(u["unit"])
    for what, us in sorted(unk_by.items(), key=lambda kv: -len(kv[1])):
        L.append(f"- {what}: {len(us)} units (e.g. {', '.join(sorted(set(us))[:4])})")
    if not unk_by:
        L.append("- none")
    L += ["", "Notes:", ""] + [f"- {n}" for n in notes]
    L += ["", "## Rollback Plan", "Delete this report and the sweep script; nothing else was changed.", ""]
    return "\n".join(L)


def sweep_notes(data):
    notes = ["Output checks use declared paths, except units listed in `config/sweep-output-contracts.json`, whose proof of work is a "
             "journal marker (non-file output) or a path that is only written when a setting is on. A service with no declared "
             "path and no contract is `unknown`, not a pass.",
             "NO_OUTPUT staleness uses the newest mtime under the declared path; a unit that writes only when something changes can look stale.",
             "DECLARED_MISSING does not evaluate the module option gating (mkIf/enable); a unit declared behind a disabled option is still reported (medium when it declares wantedBy, else low).",
             "Units whose state can only be read as root (for example journal of other users, protected state dirs) show as unknown."]
    if data.get("scopes", {}).get("user", {}).get("units") == {}:
        notes.append("User-scope systemd returned no matching units (no user bus in this environment?).")
    return notes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    ap.add_argument("--report", help="write the dated markdown report to this path")
    ap.add_argument("--fail-on", default="", help="comma list of classes that make the exit status non-zero (default: report only)")
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--fixture", help="analyse captured collector output (JSON) instead of live systemd")
    ap.add_argument("--dump-fixture", help="write the collected live facts to this JSON file")
    ap.add_argument("--date", default=date.today().isoformat())
    a = ap.parse_args(argv)
    fail = [c for c in a.fail_on.split(",") if c]
    bad = [c for c in fail if c not in CLASSES]
    if bad:
        ap.error(f"unknown class {bad}; choose from {CLASSES}")
    if a.fixture:
        data = json.loads(Path(a.fixture).read_text())
    elif not (shutil.which("systemctl") and os.path.isdir("/run/systemd/system")):
        msg = "sweep-enabled-units: SKIP: no systemd on this host (CI or container); nothing to sweep, exit 0"
        print(json.dumps({"skipped": True, "reason": "no systemd"}) if a.json else msg)
        return 0
    else:
        data = collect(a.repo)
    if a.dump_fixture:
        Path(a.dump_fixture).write_text(json.dumps(data, indent=1))
    res = analyse(data)
    if a.report:
        Path(a.report).write_text(render_report(res, a.date, sys.argv[1:] if argv is None else argv, sweep_notes(data)))
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"sweep-enabled-units: system={res['units_checked']['system']} user={res['units_checked']['user']} "
              f"units, {res['timers_checked']} timers, {len(res['unknown'])} unknown")
        for k, v in res["counts"].items():
            print(f"  {k:18} {v}")
        for f in res["findings"]:
            print(f"  [{f['class']}] {f['scope']}:{f['unit']}: {f['evidence']}")
    return 1 if any(res["counts"][c] for c in fail) else 0


if __name__ == "__main__":
    sys.exit(main())
