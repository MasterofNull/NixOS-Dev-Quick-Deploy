#!/run/current-system/sw/bin/python3
"""Fixture-driven tests for scripts/maintenance/aq-auto-update.

Every external command is replaced through AQ_AUTO_UPDATE_CMD_<NAME> by a stub that
appends "<NAME> <args>" to a log, so the tests assert exactly which side effects ran.
No real nix/systemctl/network is touched.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "maintenance" / "aq-auto-update"
IN_WINDOW = "2026-10-04T02:30:00+00:00"      # Sunday 02:30 UTC
OUT_WINDOW = "2026-10-05T02:30:00+00:00"     # Monday
SIDE_EFFECTS = {"FLAKE_UPDATE", "PIN_WATCH", "STOP_LLAMA", "START_LLAMA", "BUILD", "SET_PROFILE",
                "SWITCH", "RSI", "WATCHDOG_ARM", "WATCHDOG_DISARM"}

STUB = """#!/bin/sh
name="$1"; shift
echo "$name $*" >> "$STUB_LOG"
case "$name" in
  BUILD) ln -sfn "$NEW_CLOSURE" result ;;
  QA) grep '^SWITCH' "$STUB_LOG" | tail -1 | grep -q "$NEW_CLOSURE" && [ -n "$FAIL_AFTER_SWITCH" ] && exit 1 ;;
  SWITCH) [ -n "$SWITCH_RC" ] && exit "$SWITCH_RC" ;;
esac
exit 0
"""


class Fx:
    def __init__(self, tmp, kernel_change=False, slots=None, registry=None, loop_phase="COMPLETE",
                 now=IN_WINDOW, lease_ready=True, fail_after_switch=False, coord_ok=True):
        self.tmp = Path(tmp)
        t = self.tmp
        self.state, self.repo = t / "state", t / "repo"
        for d in (self.state, self.repo / ".agents" / "delegation", self.repo / ".agent" / "collaboration"):
            d.mkdir(parents=True, exist_ok=True)
        (self.repo / "flake.lock").write_text('{"v":1}')
        self.prev, self.new = t / "sys-prev", t / "sys-new"
        for d, k in ((self.prev, "kernelA"), (self.new, "kernelB" if kernel_change else "kernelA")):
            d.mkdir()
            (t / k).write_text(k)
            (d / "kernel").symlink_to(t / k)
        self.cur = t / "current-system"
        self.cur.symlink_to(self.prev)
        self.log = t / "stub.log"
        self.log.write_text("")
        stub = t / "stub.sh"
        stub.write_text(STUB)
        stub.chmod(0o755)
        (self.repo / ".agents" / "delegation" / "registry.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in (registry or [{"id": "a", "status": "done"}])))
        (self.repo / ".agent" / "collaboration" / "LOOP_STATE.json").write_text(json.dumps({"phase": loop_phase}))
        http = {"http://llama/slots": slots if slots is not None else [{"is_processing": False}],
                "http://llama/health": '{"status":"ok"}',
                "http://coord/health": '{"ok":true}' if coord_ok else None}
        if slots is False:
            del http["http://llama/slots"]
        (t / "http.json").write_text(json.dumps(http))
        (t / "meminfo").write_text("MemAvailable:   20000000 kB\n")
        if lease_ready:
            import datetime as dt
            n = dt.datetime.fromisoformat(now).timestamp()
            (self.state / "lease.json").write_text(json.dumps({"quiet_since": n - 1000, "last_observed": n - 60}))
        self.env = dict(os.environ)
        self.env.update({
            "AQ_AUTO_UPDATE_REPO": str(self.repo), "AQ_AUTO_UPDATE_STATE_DIR": str(self.state),
            "AQ_AUTO_UPDATE_NOW": now, "AQ_AUTO_UPDATE_CURRENT_SYSTEM": str(self.cur),
            "AQ_AUTO_UPDATE_LLAMA_URL": "http://llama", "AQ_AUTO_UPDATE_COORDINATOR_URL": "http://coord",
            "AQ_AUTO_UPDATE_HTTP_FIXTURE": str(t / "http.json"),
            "AQ_AUTO_UPDATE_MEMINFO": str(t / "meminfo"),
            "AQ_AUTO_UPDATE_ROOT_PATH": str(t), "AQ_AUTO_UPDATE_BOOT_PATH": str(t / "noboot"),
            "AQ_AUTO_UPDATE_MIN_FREE_ROOT_GB": "0", "AQ_AUTO_UPDATE_MIN_MEM_AVAILABLE_GB": "1",
            "AQ_AUTO_UPDATE_HEALTH_TIMEOUT": "0.3", "AQ_AUTO_UPDATE_HEALTH_INTERVAL": "0.05",
            "STUB_LOG": str(self.log), "NEW_CLOSURE": str(self.new),
        })
        if fail_after_switch:
            self.env["FAIL_AFTER_SWITCH"] = "1"
        for n in ("FLAKE_UPDATE", "PIN_WATCH", "STOP_LLAMA", "START_LLAMA", "BUILD", "SET_PROFILE", "SWITCH",
                  "DIFF", "FAILED_UNITS", "QA", "RSI", "WATCHDOG_ARM", "WATCHDOG_DISARM"):
            self.env["AQ_AUTO_UPDATE_CMD_" + n] = f"{stub} {n} {{closure}}"

    def run(self, *args):
        p = subprocess.run([sys.executable, str(SCRIPT), *args], env=self.env, capture_output=True, text=True,
                           cwd=str(self.repo))
        return p

    def calls(self):
        return [ln.split()[0] for ln in self.log.read_text().splitlines() if ln.strip()]

    def lines(self, name):
        return [ln for ln in self.log.read_text().splitlines() if ln.startswith(name + " ")]

    def status(self):
        return json.loads((self.state / "status.json").read_text())


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def t_lease_busy_defers():
    with tempfile.TemporaryDirectory() as d:
        fx = Fx(d, slots=[{"is_processing": True}])
        p = fx.run("run")
        check(p.returncode == 0, p.stderr)
        check(fx.status()["outcome"] == "deferred", fx.status())
        check(not SIDE_EFFECTS & set(fx.calls()), fx.calls())
    with tempfile.TemporaryDirectory() as d:  # registry row running
        fx = Fx(d, registry=[{"id": "x", "status": "running"}])
        fx.run("run")
        check(fx.status()["outcome"] == "deferred" and not SIDE_EFFECTS & set(fx.calls()), fx.calls())
    with tempfile.TemporaryDirectory() as d:  # aq-loop active
        fx = Fx(d, loop_phase="EXECUTE")
        fx.run("run")
        check(fx.status()["outcome"] == "deferred" and not SIDE_EFFECTS & set(fx.calls()), fx.calls())
    with tempfile.TemporaryDirectory() as d:  # idle but quiet window not yet elapsed
        fx = Fx(d, lease_ready=False)
        fx.run("run")
        check(fx.status()["outcome"] == "deferred" and not SIDE_EFFECTS & set(fx.calls()), fx.calls())


def t_unknown_signal_defers():
    with tempfile.TemporaryDirectory() as d:
        fx = Fx(d, slots=False)  # /slots unreadable
        fx.run("run")
        check(fx.status()["outcome"] == "deferred", fx.status())
        check("unknown" in fx.status()["reason"] or "lease" in fx.status()["reason"], fx.status())
        check(not SIDE_EFFECTS & set(fx.calls()), fx.calls())
    with tempfile.TemporaryDirectory() as d:  # corrupt registry
        fx = Fx(d)
        (fx.repo / ".agents" / "delegation" / "registry.jsonl").write_text("{not json\n")
        fx.run("run")
        check(fx.status()["outcome"] == "deferred" and not SIDE_EFFECTS & set(fx.calls()), fx.calls())


def t_outside_window_refuses():
    with tempfile.TemporaryDirectory() as d:
        fx = Fx(d, now=OUT_WINDOW)
        p = fx.run("run")
        check(p.returncode == 0, p.stderr)
        check(fx.status()["outcome"] == "refused", fx.status())
        check(fx.calls() == [], fx.calls())


def t_health_fail_rolls_back_to_recorded_closure():
    with tempfile.TemporaryDirectory() as d:
        fx = Fx(d, fail_after_switch=True)
        p = fx.run("run")
        check(p.returncode == 1, p.stderr)
        st = fx.status()
        check(st["rollback"] is True and st["previous_closure"] == str(fx.prev.resolve()), st)
        sw = fx.lines("SWITCH")
        check(len(sw) == 2, sw)
        check(sw[0].endswith(str(fx.new)) and sw[1].endswith(str(fx.prev.resolve())), sw)
        sp = fx.lines("SET_PROFILE")
        check(sp[-1].endswith(str(fx.prev.resolve())), sp)
        check(len(fx.lines("RSI")) == 1, fx.calls())
        check(st["outcome"] == "rolled-back" and st["rollback_healthy"] is True, st)
        check(fx.calls().index("STOP_LLAMA") < fx.calls().index("BUILD") < fx.calls().index("SWITCH"), fx.calls())
        check((fx.repo / "flake.lock").read_text() == '{"v":1}', "flake.lock not restored")
        check("REBOOT" not in " ".join(fx.calls()), fx.calls())


def t_kernel_change_records_pending_reboot():
    with tempfile.TemporaryDirectory() as d:
        fx = Fx(d, kernel_change=True)
        p = fx.run("run")
        check(p.returncode == 0, p.stderr)
        st = fx.status()
        check(st["outcome"] == "switched" and st["pending_reboot"] is True, st)
        check((fx.state / "pending-reboot").exists(), "no pending-reboot marker")
        check("reboot" not in " ".join(fx.calls()).lower(), fx.calls())
        check(fx.lines("RSI") == [], "no incident expected on success")
    with tempfile.TemporaryDirectory() as d:  # same kernel -> no marker
        fx = Fx(d, kernel_change=False)
        fx.run("run")
        check(fx.status()["outcome"] == "switched" and not (fx.state / "pending-reboot").exists(), fx.status())


def t_dry_run_has_no_side_effects():
    with tempfile.TemporaryDirectory() as d:
        fx = Fx(d)
        before = {p.name: p.read_text() for p in fx.state.iterdir()}
        lock_before = (fx.repo / "flake.lock").read_text()
        p = fx.run("run", "--dry-run")
        check(p.returncode == 0, p.stderr)
        check(not SIDE_EFFECTS & set(fx.calls()), fx.calls())
        check("DRY-RUN would run SWITCH" in p.stderr and "DRY-RUN would run BUILD" in p.stderr, p.stderr)
        check({q.name: q.read_text() for q in fx.state.iterdir()} == before, "state dir changed in dry-run")
        check((fx.repo / "flake.lock").read_text() == lock_before, "flake.lock changed")
        check(not (fx.state / "status.json").exists() and not (fx.state / "pending-reboot").exists(), "files written")



def t_repo_helpers_run_as_owner():
    # Root must never execute user-writable repo helpers directly.
    import importlib.machinery, importlib.util, os as _os
    from unittest import mock
    loader = importlib.machinery.SourceFileLoader("aq_auto_update_mod", str(SCRIPT))
    spec = importlib.util.spec_from_loader("aq_auto_update_mod", loader)
    mod = importlib.util.module_from_spec(spec); loader.exec_module(mod)
    calls = []
    fake = lambda argv, **kw: (calls.append(argv), subprocess.CompletedProcess(argv, 0, "", ""))[1]
    with mock.patch.dict(_os.environ, {"AQ_AUTO_UPDATE_RUN_AS": "owner"}), mock.patch.object(mod.subprocess, "run", fake):
        ctx = mod.Ctx()
        for name in ("FLAKE_UPDATE", "PIN_WATCH", "QA", "RSI"):
            ctx.cmd(name, ["helper"], side_effect=False)
        ctx.cmd("BUILD", ["nixos-rebuild", "build"], side_effect=False)
    assert all(c[:4] == ["runuser", "-u", "owner", "--"] for c in calls[:4]), calls
    assert calls[4][0] == "nixos-rebuild", calls[4]


def t_check_escalates_running_kernel_past_reboot_sla():
    # Patched != running: a newer installed kernel must be surfaced, then escalated past the SLA.
    with tempfile.TemporaryDirectory() as d:
        fx = Fx(d, kernel_change=True)
        fx.cur.unlink(); fx.cur.symlink_to(fx.new)          # installed: kernelB
        booted = fx.tmp / "booted-system"; booted.symlink_to(fx.prev)  # running: kernelA
        fx.env.update({"AQ_AUTO_UPDATE_BOOTED_SYSTEM": str(booted), "AQ_AUTO_UPDATE_REBOOT_SLA_HOURS": "24"})
        fx.run("check")
        st = fx.status()
        check(st["pending_reboot"] is True and st["pending_reboot_hours"] == 0.0, st)
        check(fx.lines("RSI") == [], "no incident inside the SLA")
        (fx.state / "pending-reboot").write_text(json.dumps({"since": "2026-09-29T00:00:00+00:00"}))
        fx.run("check")
        check(len(fx.lines("RSI")) == 1, fx.lines("RSI"))
        booted.unlink(); booted.symlink_to(fx.new)          # rebooted into kernelB
        fx.run("check")
        check(fx.status()["pending_reboot"] is False and not (fx.state / "pending-reboot").exists(), fx.status())

TESTS = [v for k, v in sorted(globals().items()) if k.startswith("t_")]

if __name__ == "__main__":
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc!r}")
    print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
    sys.exit(1 if failed else 0)
