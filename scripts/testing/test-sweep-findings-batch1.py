#!/usr/bin/env python3
"""Regression for sweep findings batch 1: output contracts in sweep-enabled-units, the gap-remediation
unit running its script directly and logging empty runs, a stateless lease authority, and the switchboard
budget path being writable and non-fatal. Fixtures and a fake psql only; no live systemd or network."""
import importlib.machinery
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_loader(
    "sweep", importlib.machinery.SourceFileLoader("sweep", str(REPO / "scripts/governance/sweep-enabled-units.py")))
sw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sw)

NOW = 1_800_000_000


def svc(name, **kw):
    p = {"Id": name, "LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead", "Result": "success",
         "NRestarts": "0", "Type": "oneshot", "RemainAfterExit": "no", "UnitFileState": "enabled",
         "ExecMainStartTimestamp": f"@{NOW - 100}", "ExecStart": "{ path=/nix/store/x/bin/py ; argv[]=/nix/store/x/bin/py /nix/store/y/s.py ; }",
         "Description": "d", "Environment": "", "StateDirectory": "", "LogsDirectory": "", "ConditionResult": "yes",
         "TriggeredBy": "", "Unit": "", "LastTriggerUSec": "", "TimersCalendar": "", "TimersMonotonic": ""}
    p.update(kw)
    return p


def timer(name):
    return svc(name, Type="", SubState="waiting", ActiveState="active", Unit=name[:-6] + ".service",
               ExecMainStartTimestamp="", ActiveEnterTimestamp=f"@{NOW - 10 * 86400}", LastTriggerUSec=f"@{NOW - 600}",
               TimersMonotonic="{ OnUnitActiveUSec=1h ; next_elapse=1min }")


def data(unit_props, contracts, markers, fs=None):
    units = {"ai-w.service": svc("ai-w.service", TriggeredBy="ai-w.timer", **unit_props), "ai-w.timer": timer("ai-w.timer")}
    return {"systemd": True, "now": NOW, "uptime": 10 * 86400, "checkout_markers": ["/r"],
            "nix": {"system": {}, "user": {}, "dynamic": 0},
            "scopes": {"system": {"unit_files": {n: "enabled" for n in units}, "units": units},
                       "user": {"unit_files": {}, "units": {}}},
            "fs": fs or {}, "contracts": contracts, "journal_markers": markers}


def no_output(d):
    return [f for f in sw.analyse(d)["findings"] if f["class"] == "NO_OUTPUT"]


def test_journal_marker():
    c = {"ai-w.service": {"journal_marker": "x"}}
    dirfact = {"/var/log/ai-w": {"exists": True, "mtime": NOW - 200 * 86400, "is_dir": True, "empty": False}}
    props = {"LogsDirectory": "ai-w"}
    assert no_output(data(props, {}, {}, dirfact)), "stale log dir with no contract must still be NO_OUTPUT"
    assert not no_output(data(props, c, {"system:ai-w.service": NOW - 600}, dirfact)), "fresh marker must pass"
    stale = no_output(data(props, c, {"system:ai-w.service": NOW - 5 * 86400}, dirfact))
    assert stale and "journal marker" in stale[0]["evidence"], stale
    never = no_output(data(props, c, {"system:ai-w.service": None}, dirfact))
    assert never and "never" in never[0]["evidence"], never


def test_conditional_path():
    p = "/var/lib/nixos-ai-stack/optimizer/b.json"
    c = {"ai-w.service": {"conditional_paths": {p: "CAP"}}}
    fs = {p: {"exists": False, "mtime": None}}
    off = {"Environment": f"CAP=0 BUD={p}", "StateDirectory": ""}
    on = {"Environment": f"CAP=5000 BUD={p}"}
    # ENV_DIR_RE matches names ending in STATE/LOG/OUTPUT/REPORT/DATA..PATH|DIR
    off["Environment"] = f"CAP=0 X_STATE_PATH={p}"
    on["Environment"] = f"CAP=5000 X_STATE_PATH={p}"
    assert no_output(data(off, {}, {}, fs)), "baseline: missing declared path flagged without contract"
    assert not no_output(data(off, c, {}, fs)), "cap off: path must not be expected"
    assert no_output(data(on, c, {}, fs)), "cap on: missing path must be flagged"


def test_shipped_contracts_are_real():
    raw = json.loads((REPO / "config/sweep-output-contracts.json").read_text())
    units = {k: v for k, v in raw.items() if not k.startswith("_")}
    assert set(units) >= {"ai-mcp-process-watch.service", "ai-autonomous-improvement.service", "ai-switchboard.service"}
    for name, c in units.items():
        assert c.get("why"), f"{name}: contract needs a why"
        assert c.get("journal_marker") or c.get("conditional_paths"), name
    assert sw.load_contracts(REPO) == units
    # marker for each journal contract must match what the scripts really print
    assert "Checked %d services" in (REPO / "scripts/testing/check-mcp-processes.sh").read_text()
    assert "Metrics inserted" in (REPO / "ai-stack/autonomous-improvement/autonomous_loop.py").read_text()


def test_gap_remediate_logs_empty_run():
    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "bin"
        fake.mkdir()
        psql = fake / "psql"
        psql.write_text("#!/bin/sh\ncat >/dev/null\n")
        psql.chmod(psql.stat().st_mode | stat.S_IXUSR)
        logdir = Path(td) / "log"
        idle = Path(td) / "idle-loadavg"
        idle.write_text("0.00 0.00 0.00 1/1 1\n")  # keep the load guard out of this test on a busy host
        env = {"PATH": f"{fake}:{os.environ['PATH']}", "HOME": td, "GAP_REMEDIATION_LOG_DIR": str(logdir),
               "GAP_LOADAVG_FILE": str(idle)}
        r = subprocess.run(["bash", str(REPO / "scripts/ai/aq-gap-auto-remediate"), "--limit", "5"],
                           env=env, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        lines = [json.loads(x) for f in logdir.glob("remediation-*.jsonl") for x in f.read_text().splitlines()]
        assert lines and lines[0]["type"] == "summary" and lines[0]["total"] == 0, lines
        r = subprocess.run(["bash", str(REPO / "scripts/ai/aq-gap-auto-remediate"), "--dry-run"],
                           env={**env, "GAP_REMEDIATION_LOG_DIR": str(Path(td) / "dry")}, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and not (Path(td) / "dry").exists(), "dry run must not write a log"


def test_gap_remediate_defers_under_load():
    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "bin"
        fake.mkdir()
        marker = Path(td) / "psql-called"
        psql = fake / "psql"
        psql.write_text(f"#!/bin/sh\ntouch {marker}\ncat >/dev/null\n")
        psql.chmod(psql.stat().st_mode | stat.S_IXUSR)
        loadavg = Path(td) / "loadavg"
        loadavg.write_text("999.00 999.00 999.00 1/1 1\n")
        logdir = Path(td) / "log"
        env = {"PATH": f"{fake}:{os.environ['PATH']}", "HOME": td, "GAP_REMEDIATION_LOG_DIR": str(logdir),
               "GAP_LOADAVG_FILE": str(loadavg)}
        script = str(REPO / "scripts/ai/aq-gap-auto-remediate")
        r = subprocess.run(["bash", script, "--limit", "5"], env=env, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "DEFERRED: CPU load too high" in r.stderr, r.stderr
        assert not marker.exists(), "deferred run must not start work"
        rows = [json.loads(x) for f in logdir.glob("remediation-*.jsonl") for x in f.read_text().splitlines()]
        assert len(rows) == 1 and rows[0]["type"] == "deferred" and "CPU load too high" in rows[0]["reason"], rows
        assert rows[0]["success"] == 0 and rows[0]["total"] == 0
        # below the threshold the same script runs and records a normal summary
        loadavg.write_text("0.00 0.00 0.00 1/1 1\n")
        r = subprocess.run(["bash", script, "--limit", "5"], env=env, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and marker.exists(), r.stderr
        # threshold comes from RALPH_MAX_CPU_PERCENT, like ralph-wiggum
        loadavg.write_text("999.00 999.00 999.00 1/1 1\n")
        r = subprocess.run(["bash", script, "--limit", "5"], env={**env, "RALPH_MAX_CPU_PERCENT": "100000"},
                           capture_output=True, text=True, timeout=60)
        assert "DEFERRED" not in r.stderr, r.stderr


def test_nix_declarations():
    ai = (REPO / "nix/modules/roles/ai-stack.nix").read_text()
    i = ai.index("systemd.services.ai-gap-auto-remediate")
    unit = ai[i:ai.index("systemd.timers.ai-gap-auto-remediate")]
    exec_line = next(x for x in unit.splitlines() if x.strip().startswith("ExecStart"))
    assert "aq-ralph-task" not in exec_line and "scripts/ai/aq-gap-auto-remediate --limit 5 --verify" in exec_line, exec_line
    lease = (REPO / "nix/modules/services/lease-signing-authority.nix").read_text()
    assert 'StateDirectory =' not in lease and 'RuntimeDirectory = "aq-lease-signing-authority"' in lease
    swb = (REPO / "nix/modules/services/switchboard.nix").read_text()
    assert "ReadWritePaths = [localAgentStateDir" in swb and "mutableOptimizerDir];" in swb


def test_budget_save_failure_not_fatal():
    src = (REPO / "ai-stack/switchboard/switchboard.py").read_text()
    i = src.index("        _budget_state_save(used)")
    assert src[i - 40:i].strip().endswith("try:") and "except OSError" in src[i:i + 200]


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:  # noqa: BLE001
                fails += 1
                print(f"FAIL {name}: {exc!r}")
    sys.exit(1 if fails else 0)
