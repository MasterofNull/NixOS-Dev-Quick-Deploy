#!/usr/bin/env python3
"""Wiring tests for the routine payload audit: tier0.d report, health-monitor signal/alert, 6b measurement."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "scripts" / "ai" / "aq-payload-audit"
WRAPPER = ROOT / "scripts" / "governance" / "tier0.d" / "check-payload-audit.sh"
MONITOR = ROOT / "scripts" / "health" / "ai-stack-health-monitor.py"

HIGH = {"lane": "codex", "check_id": "6b", "severity": "high", "measured": "1 plan-quota exhaustion(s) in 2 days",
        "threshold": "zero", "evidence_path": ".agents/delegation/outputs/x.log (resets soon)", "suggested_fix": "route"}
MED = {"lane": "claude", "check_id": "1", "severity": "medium", "measured": "26000 bytes",
       "threshold": "<24 KB", "evidence_path": "CLAUDE.md", "suggested_fix": "trim"}


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def fake_audit(tmp: Path, findings: list[dict], exit_code: int = 0) -> Path:
    summary = {"total": len(findings), "high": sum(f["severity"] == "high" for f in findings),
               "medium": sum(f["severity"] == "medium" for f in findings), "info": 0}
    script = tmp / "fake-audit.py"
    script.write_text("import json,sys\nprint(json.dumps({'findings': %r, 'summary': %r}))\nsys.exit(%d)\n"
                      % (findings, summary, exit_code))
    return script


def run_wrapper(mode: str, audit: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(WRAPPER), mode], capture_output=True, text=True,
                          env={**os.environ, "PAYLOAD_AUDIT_BIN": str(audit)})


def test_tier0_wrapper():
    with tempfile.TemporaryDirectory() as d:
        audit = fake_audit(Path(d), [HIGH, MED])
        r = run_wrapper("--pre-commit", audit)
        check(r.returncode == 0 and "SKIP" in r.stdout, f"pre-commit must skip: {r.stdout}{r.stderr}")
        r = run_wrapper("--maintenance", audit)
        check(r.returncode == 0, "maintenance report must never block even with a HIGH finding")
        check("WARN HIGH codex/6b" in r.stdout and "1 high, 1 medium" in r.stdout, r.stdout)
        broken = Path(d) / "broken.py"
        broken.write_text("import sys\nprint('boom')\nsys.exit(3)\n")
        r = run_wrapper("--maintenance", broken)
        check(r.returncode == 0 and "audit could not run" in r.stdout, f"unrunnable audit is reported: {r.stdout}")
    # The gate must discover the wrapper (tier0.d glob) and it must be executable like its siblings.
    check(os.access(WRAPPER, os.X_OK), "wrapper must be executable")


def load_monitor():
    sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
    spec = importlib.util.spec_from_file_location("monitor_payload_under_test", MONITOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_monitor_signal_and_alert():
    mon = load_monitor()
    from attention_queue import AlertSpec
    pushed: list[dict] = []
    mon.push = lambda **spec: (AlertSpec(**spec).validate(), pushed.append(spec))

    with tempfile.TemporaryDirectory() as d:
        mon._PAYLOAD_AUDIT = fake_audit(Path(d), [HIGH, MED])
        audit = mon.run_payload_audit()
        check(audit["state"] == "findings" and audit["high"] == 1 and audit["medium"] == 1, str(audit))
        mon.alert_payload_audit(audit)
        check(len(pushed) == 1, "one HIGH finding set -> exactly one alert")
        check(pushed[0]["severity"] == "medium" and pushed[0]["dedup_key"] == "payload-audit-high",
              "HIGH payload findings are a medium attention alert, not an outage")
        check("codex 6b" in pushed[0]["title"], pushed[0]["title"])

        pushed.clear()
        mon._PAYLOAD_AUDIT = fake_audit(Path(d), [MED])
        audit = mon.run_payload_audit()
        mon.alert_payload_audit(audit)
        check(audit["state"] == "findings" and not pushed, "medium-only findings: recorded in status, no alert")

        mon._PAYLOAD_AUDIT = fake_audit(Path(d), [])
        check(mon.run_payload_audit()["state"] == "ok", "no findings -> ok")

        bad = Path(d) / "bad.py"
        bad.write_text("print('not json')\n")
        mon._PAYLOAD_AUDIT = bad
        audit = mon.run_payload_audit()
        check(audit["state"] == "unknown" and "error" in audit, "unparseable audit must read unknown, never ok")
        pushed.clear()
        mon.alert_payload_audit(audit)
        check(not pushed, "unknown state raises no payload alert")

        # main() writes the audit into the status file the dashboard/RSI sweep read.
        mon._PAYLOAD_AUDIT = fake_audit(Path(d), [HIGH])
        mon._PHASES = ["0"]
        mon.run_aq_qa = lambda phase: {"tests": []}
        statuses: list[dict] = []
        mon.write_status = statuses.append
        pushed.clear()
        check(mon.main() == 0, "monitor exits 0")
        check(statuses[0]["payload_audit"]["high"] == 1, "status file carries payload_audit")
        check(len(pushed) == 1, "main() raises the payload alert")


def make_log(outputs: Path, name: str, body: str, age_days: float = 0) -> None:
    p = outputs / name
    p.write_text(body)
    t = time.time() - age_days * 86400
    os.utime(p, (t, t))


def test_6b_measurement():
    with tempfile.TemporaryDirectory() as d:
        repo, home = Path(d) / "repo", Path(d) / "home"
        outputs = repo / ".agents" / "delegation" / "outputs"
        outputs.mkdir(parents=True)
        home.mkdir()
        make_log(outputs, "codex-echo.log", "task text: quota exhaustion is handled by routing; usage limit docs\n")
        make_log(outputs, "codex-real-old.log", "x\nERROR: You've hit your usage limit. try again at Nov 12th, 2026 1:05 AM.\n", age_days=5)

        def findings(days: str):
            r = subprocess.run([sys.executable, str(AUDIT), "--json", "--repo", str(repo), "--home", str(home), "--days", days],
                               capture_output=True, text=True)
            return [f for f in json.loads(r.stdout)["findings"] if f["check_id"] == "6b"]

        check(findings("2") == [], "echoed prose and out-of-window logs must not raise 6b (--days must be honoured)")
        got = findings("7")
        check(len(got) == 1 and got[0]["severity"] == "low", "real ERROR line whose reset has passed is low, not HIGH")
        check("since reset" in got[0]["measured"], got[0]["measured"])
        check("codex-real-old.log" in got[0]["evidence_path"] and "resets Nov 12th, 2026 1:05 AM" in got[0]["evidence_path"],
              got[0]["evidence_path"])
        check("not overspend" in got[0]["suggested_fix"], "fix text must say quota, not spend")


def test_6b_reset_severity():
    import importlib.machinery
    from datetime import datetime
    loader = importlib.machinery.SourceFileLoader("aq_payload_audit_t", str(AUDIT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    now = datetime(2026, 11, 12, 12, 0)

    def sev(line: str, age_days: float = 0.1) -> str:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            outputs = repo / ".agents" / "delegation" / "outputs"
            outputs.mkdir(parents=True)
            p = outputs / "codex-x.log"
            p.write_text("x\n" + line + "\n")
            t = now.timestamp() - age_days * 86400
            os.utime(p, (t, t))
            got = mod.check_codex_dispatch_history(repo, 7, now=now)
            return got[0].severity

    base = "ERROR: You've hit your usage limit. try again at "
    check(sev(base + "Nov 12th, 2026 1:05 AM.") == "low", "past dated reset -> low")
    check(sev(base + "Nov 12th, 2026 3:05 PM.") == "high", "future dated reset -> high")
    check(sev(base + "4:29 AM.", age_days=0.4) == "low", "time-only reset after log time, already passed -> low")
    check(sev(base + "11:59 PM.") == "high", "time-only reset still ahead -> high")
    check(sev(base + "soon.") == "high", "unparseable -> high")
    check(sev("ERROR: usage limit reached") == "high", "no reset time -> high")


def test_home_side_duplicate_and_imports():
    with tempfile.TemporaryDirectory() as d:
        repo, home = Path(d) / "repo", Path(d) / "home"
        (repo / ".claude" / "rules").mkdir(parents=True)
        (home / ".claude" / "rules").mkdir(parents=True)
        (repo / ".claude" / "rules" / "lean-ctx.md").write_text("rules\n")
        (home / ".claude" / "rules" / "lean-ctx.md").write_text("rules\n")
        (home / ".claude" / "CLAUDE.md").write_text("home\n@extra.md\n")
        (home / ".claude" / "extra.md").write_text("y" * 5000)

        def audit():
            r = subprocess.run([sys.executable, str(AUDIT), "--json", "--repo", str(repo), "--home", str(home)],
                               capture_output=True, text=True)
            return json.loads(r.stdout)

        data = audit()
        dup = [f for f in data["findings"] if f["check_id"] == "1-dup"]
        check(len(dup) == 1 and dup[0]["severity"] == "low", f"identical home copy is LOW: {dup}")
        check("home-side duplicate" in dup[0]["measured"], dup[0]["measured"])
        check("~/.claude/rules/lean-ctx.md" in dup[0]["suggested_fix"] and "@rules/lean-ctx.md" in dup[0]["suggested_fix"]
              and "~/.claude/CLAUDE.md" in dup[0]["suggested_fix"], "exact owner action named")
        check(data["summary"]["high"] == 0 and data["summary"]["medium"] == 0 and data["summary"]["low"] == 1,
              "a home-side duplicate is not a repo defect: no medium/high")

        # Home @-imports count toward the payload: push the total over 24 KB only via the import.
        (home / ".claude" / "extra.md").write_text("y" * 25000)
        check(any(f["check_id"] == "1" for f in audit()["findings"]), "home CLAUDE.md @-import bytes are counted")

    # The repo copy stays: it is how a fresh clone receives the lean-ctx rules.
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", ".claude/rules/lean-ctx.md"], capture_output=True, text=True)
    check(r.stdout.strip() == ".claude/rules/lean-ctx.md", "repo copy must remain tracked")


def main() -> int:
    failed = 0
    for fn in (test_tier0_wrapper, test_monitor_signal_and_alert, test_6b_measurement, test_6b_reset_severity, test_home_side_duplicate_and_imports):
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
