#!/usr/bin/env python3
"""sweep-enabled-units: each finding class is detected from captured systemd facts, a healthy unit is not flagged,
and a host without systemd skips with exit 0. Uses fixtures only, never live systemd."""
import copy
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/governance/sweep-enabled-units.py"
spec = importlib.util.spec_from_loader("sweep", importlib.machinery.SourceFileLoader("sweep", str(SCRIPT)))
sw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sw)

NOW = 1_800_000_000
CK = "/home/u/repo"


def svc(name, **kw):
    p = {"Id": name, "LoadState": "loaded", "ActiveState": "active", "SubState": "running", "Result": "success",
         "NRestarts": "0", "Type": "simple", "RemainAfterExit": "no", "UnitFileState": "enabled",
         "ExecMainStartTimestamp": f"@{NOW - 100}", "ExecStart": "{ path=/nix/store/x/bin/py ; argv[]=/nix/store/x/bin/py /nix/store/y/s.py ; }",
         "Description": "d", "Environment": "", "StateDirectory": "", "LogsDirectory": "", "ConditionResult": "yes",
         "TriggeredBy": "", "Unit": "", "LastTriggerUSec": "", "TimersCalendar": "", "TimersMonotonic": ""}
    p.update(kw)
    return p


def timer(name, **kw):
    p = svc(name, Type="", Result="success", Unit=name[:-6] + ".service", SubState="waiting",
            ExecMainStartTimestamp="", ActiveEnterTimestamp=f"@{NOW - 10 * 86400}",
            LastTriggerUSec=f"@{NOW - 600}", TimersMonotonic="{ OnUnitActiveUSec=15min ; next_elapse=1min }")
    p.update(kw)
    return p


def base():
    units = {u["Id"]: u for u in (
        svc("ai-good.service"),
        svc("ai-tick.service", Type="oneshot", ActiveState="inactive", SubState="dead", TriggeredBy="ai-tick.timer",
            StateDirectory="ai-tick"),
        timer("ai-tick.timer"))}
    return {"systemd": True, "now": NOW, "uptime": 10 * 86400, "checkout_markers": [CK],
            "nix": {"system": {}, "user": {}, "dynamic": 0},
            "scopes": {"system": {"unit_files": {n: "enabled" for n in units}, "units": units},
                       "user": {"unit_files": {}, "units": {}}},
            "fs": {"/var/lib/ai-tick": {"exists": True, "mtime": NOW - 300, "is_dir": True, "empty": False}}}


def classes(data):
    r = sw.analyse(data)
    return {(f["class"], f["unit"]) for f in r["findings"]}


def put(d, unit):
    d["scopes"]["system"]["units"][unit["Id"]] = unit
    d["scopes"]["system"]["unit_files"][unit["Id"]] = unit.get("UnitFileState", "enabled")


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def healthy_not_flagged():
    got = classes(base())
    assert got == set(), got


@case
def failed():
    d = base()
    put(d, svc("ai-bad.service", ActiveState="failed", SubState="failed", Result="exit-code"))
    assert ("FAILED", "ai-bad.service") in classes(d)


@case
def failed_long_running_inactive():
    d = base()
    put(d, svc("ai-dead.service", ActiveState="inactive", SubState="dead"))
    assert ("FAILED", "ai-dead.service") in classes(d)


@case
def never_ran_timer():
    d = base()
    put(d, timer("ai-never.timer", LastTriggerUSec=""))
    assert ("NEVER_RAN", "ai-never.timer") in classes(d)


@case
def never_ran_service():
    d = base()
    put(d, svc("ai-idle.service", ActiveState="inactive", SubState="dead", ExecMainStartTimestamp=""))
    assert ("NEVER_RAN", "ai-idle.service") in classes(d)


@case
def timer_not_yet_due_is_unknown_not_flagged():
    d = base()
    put(d, timer("ai-new.timer", LastTriggerUSec="", ActiveEnterTimestamp=f"@{NOW - 60}"))
    d["uptime"] = 60
    r = sw.analyse(d)
    assert ("NEVER_RAN", "ai-new.timer") not in classes(d)
    assert any(u["unit"] == "ai-new.timer" for u in r["unknown"])


@case
def stale_timer():
    d = base()
    put(d, timer("ai-old.timer", LastTriggerUSec=f"@{NOW - 10 * 86400}"))
    assert ("STALE_TIMER", "ai-old.timer") in classes(d)


@case
def timer_last_run_failed():
    d = base()
    put(d, timer("ai-lf.timer"))
    put(d, svc("ai-lf.service", Type="oneshot", ActiveState="inactive", SubState="dead", Result="exit-code", TriggeredBy="ai-lf.timer"))
    assert ("STALE_TIMER", "ai-lf.timer") in classes(d)


@case
def no_output_stale_and_missing():
    d = base()
    d["fs"]["/var/lib/ai-tick"]["mtime"] = NOW - 30 * 86400
    assert ("NO_OUTPUT", "ai-tick.service") in classes(d)
    d = base()
    d["fs"]["/var/lib/ai-tick"] = {"exists": False, "mtime": None}
    assert ("NO_OUTPUT", "ai-tick.service") in classes(d)


@case
def no_output_unknown_not_pass_or_fail():
    d = base()
    d["fs"]["/var/lib/ai-tick"] = {"exists": True, "mtime": None, "is_dir": True, "unreadable": True}
    r = sw.analyse(d)
    assert ("NO_OUTPUT", "ai-tick.service") not in classes(d)
    assert any(u["unit"] == "ai-tick.service" for u in r["unknown"])


@case
def declared_missing_and_disabled():
    d = base()
    d["nix"]["system"]["ai-gone.service"] = {"file": "nix/m.nix", "line": 3, "wanted_by": True}
    d["nix"]["system"]["ai-off.timer"] = {"file": "nix/m.nix", "line": 9, "wanted_by": True}
    d["scopes"]["system"]["unit_files"]["ai-off.timer"] = "disabled"
    got = classes(d)
    assert ("DECLARED_MISSING", "ai-gone.service") in got and ("DECLARED_MISSING", "ai-off.timer") in got, got


@case
def restart_loop():
    d = base()
    put(d, svc("ai-loop.service", NRestarts="40", ActiveState="activating", SubState="auto-restart"))
    assert ("RESTART_LOOP", "ai-loop.service") in classes(d)


@case
def retired_ref():
    d = base()
    put(d, svc("ai-wake.service", ExecStart="{ path=/bin/sh ; argv[]=/bin/sh -c wake-antigravity-ide ; }"))
    d["fs"]["/bin/sh"] = {"exists": True, "mtime": 1}
    assert ("RETIRED_REF", "ai-wake.service") in classes(d)


@case
def broken_exec_checkout_script_and_missing_binary():
    d = base()
    put(d, svc("ai-chk.service", ExecStart=f"{{ path=/nix/store/x/bin/py ; argv[]=/nix/store/x/bin/py {CK}/scripts/gone.py ; }}"))
    put(d, svc("ai-bin.service", ExecStart="{ path=/opt/gone/bin/tool ; argv[]=/opt/gone/bin/tool ; }"))
    d["fs"][f"{CK}/scripts/gone.py"] = {"exists": False, "mtime": None}
    d["fs"]["/opt/gone/bin/tool"] = {"exists": False, "mtime": None}
    got = classes(d)
    assert ("BROKEN_EXEC", "ai-chk.service") in got and ("BROKEN_EXEC", "ai-bin.service") in got, got
    d["fs"][f"{CK}/scripts/gone.py"] = {"exists": True, "mtime": 1}
    assert ("BROKEN_EXEC", "ai-chk.service") not in classes(d)


@case
def out_of_scope_names_ignored_by_filter():
    assert sw.in_scope("ai-x.service") and sw.in_scope("llama-cpp.service") and not sw.in_scope("sshd.service")


@case
def no_systemd_skips_exit_0():
    env = {**os.environ, "PATH": "/nonexistent"}
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "SKIP" in r.stdout, (r.returncode, r.stdout, r.stderr)


@case
def cli_fixture_json_report_and_fail_on():
    with tempfile.TemporaryDirectory() as t:
        d = base()
        put(d, svc("ai-bad.service", ActiveState="failed", SubState="failed", Result="exit-code"))
        fx, rp = Path(t, "f.json"), Path(t, "r.md")
        fx.write_text(json.dumps(d))
        r = subprocess.run([sys.executable, str(SCRIPT), "--fixture", str(fx), "--json", "--report", str(rp)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr  # report-only by default
        assert json.loads(r.stdout)["counts"]["FAILED"] == 1 and "| FAILED |" in rp.read_text()
        r = subprocess.run([sys.executable, str(SCRIPT), "--fixture", str(fx), "--fail-on", "FAILED"], capture_output=True, text=True)
        assert r.returncode == 1


def main():
    bad = 0
    for fn in CASES:
        try:
            fn()
            print(f"ok   {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"FAIL {fn.__name__}: {e!r}")
    print("PASS" if not bad else f"FAIL: {bad} case(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
