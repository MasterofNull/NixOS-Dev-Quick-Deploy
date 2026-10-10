#!/usr/bin/env python3
"""rsi_sweep adapter + idempotence tests with fixtures; no systemctl, no network, no aq-qa run."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import rsi_lifecycle as rsi
import rsi_sweep as sw


def _proc(out, rc=0):
    return SimpleNamespace(stdout=out, stderr="", returncode=rc)


class AdapterTests(unittest.TestCase):
    def test_failed_units_parsed_and_instances_collapsed(self):
        out = "● foo.service loaded failed failed Foo\n● bar@abc123.service loaded failed failed Bar\n"
        state, f, _ = sw.adapter_failed_units(lambda: _proc(out))
        self.assertEqual(state, "findings")
        self.assertEqual([x["path"] for x in f], ["foo.service", "bar@*.service"])

    def test_failed_units_none_is_ok_and_error_is_unknown(self):
        self.assertEqual(sw.adapter_failed_units(lambda: _proc(""))[0], "ok")
        self.assertEqual(sw.adapter_failed_units(lambda: _proc("", 1))[0], "unknown")
        def boom(): raise OSError("no systemctl")
        self.assertEqual(sw.adapter_failed_units(boom)[0], "unknown")

    def test_qa_missing_stale_fresh(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "p.jsonl"
            self.assertEqual(sw.adapter_qa_phase0(p)[0], "unknown")
            recs = [{"check_id": "0.1.1", "state": "fail", "description": "x"},
                    {"check_id": "0.1.1", "state": "fail", "description": "x"},
                    {"check_id": "0.1.2", "state": "pass"},
                    {"check_id": "0.1.3", "state": "fail", "description": "y"},
                    {"check_id": "0.1.3", "state": "pass", "description": "y"}]
            p.write_text("garbage-cut-line\n" + "\n".join(json.dumps(r) for r in recs))
            state, f, _ = sw.adapter_qa_phase0(p, max_age_s=3600)
            self.assertEqual((state, [x["subject"] for x in f]), ("findings", ["aq-qa:0.1.1"]))
            state, f, d = sw.adapter_qa_phase0(p, max_age_s=3600, now=time.time() + 7200)
            self.assertEqual((state, f), ("unknown", []))
            self.assertIn("stale", d)

    def test_qa_no_phase0_records_is_unknown_not_ok(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "p.jsonl"
            for body in ("", "garbage\nmore garbage\n",
                         json.dumps({"check_id": "1.2.3", "state": "pass"})):  # no phase-0 record
                p.write_text(body)
                state, f, d = sw.adapter_qa_phase0(p, max_age_s=3600)
                self.assertEqual((state, f), ("unknown", []), body)
                self.assertIn("no phase-0", d)

    def test_qa_incomplete_run_without_failures_is_unknown(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "p.jsonl"
            p.write_text("\n".join(json.dumps(r) for r in [
                {"check_id": "0.1.1", "state": "pass"}, {"check_id": "0.1.2", "state": "running"}]))
            self.assertEqual(sw.adapter_qa_phase0(p, max_age_s=3600)[0], "unknown")
            p.write_text("\n".join(json.dumps(r) for r in [
                {"check_id": "0.1.1", "state": "pass"}, {"check_id": "0.1.2", "state": "pass"}]))
            self.assertEqual(sw.adapter_qa_phase0(p, max_age_s=3600)[0], "ok")

    def test_qa_fallback_to_health_monitor_with_failure(self):
        with tempfile.TemporaryDirectory() as t:
            progress = Path(t) / "progress.jsonl"
            monitor = Path(t) / "monitor.json"

            # Stale progress file
            progress.write_text(json.dumps({"check_id": "0.1.1", "state": "pass"}))
            os.utime(progress, (time.time() - 7200, time.time() - 7200))

            # Fresh monitor with 1 failure
            monitor_data = {
                "phase_results": [
                    {"phase": "0", "status": "failed", "returncode": 1, "total": 202,
                     "failures": [{"id": "0.10.44", "label": "execution-cell-adapter fixture contract drift"}]}
                ],
                "source": "ai-stack-health-monitor",
                "timestamp": "2026-10-09T03:04:17Z"
            }
            monitor.write_text(json.dumps(monitor_data))

            state, f, d = sw.adapter_qa_phase0(progress, max_age_s=3600, health_monitor_json=monitor, now=time.time())
            self.assertEqual(state, "findings")
            self.assertEqual(len(f), 1)
            self.assertEqual(f[0]["subject"], "aq-qa:0.10.44")
            self.assertEqual(f[0]["producer"], "aq-qa:phase0")
            self.assertIn("health-monitor", d)

    def test_qa_fallback_to_health_monitor_no_failures(self):
        with tempfile.TemporaryDirectory() as t:
            progress = Path(t) / "progress.jsonl"
            monitor = Path(t) / "monitor.json"

            # Stale progress file
            progress.write_text(json.dumps({"check_id": "0.1.1", "state": "pass"}))
            os.utime(progress, (time.time() - 7200, time.time() - 7200))

            # Fresh monitor with 0 failures
            monitor_data = {
                "phase_results": [
                    {"phase": "0", "status": "passed", "returncode": 0, "total": 202, "failures": []}
                ],
                "source": "ai-stack-health-monitor",
                "timestamp": "2026-10-09T03:04:17Z"
            }
            monitor.write_text(json.dumps(monitor_data))

            state, f, d = sw.adapter_qa_phase0(progress, max_age_s=3600, health_monitor_json=monitor, now=time.time())
            self.assertEqual(state, "ok")
            self.assertEqual(f, [])
            self.assertIn("202", d)
            self.assertIn("health-monitor", d)

    def test_qa_both_stale_is_unknown(self):
        with tempfile.TemporaryDirectory() as t:
            progress = Path(t) / "progress.jsonl"
            monitor = Path(t) / "monitor.json"

            # Both stale
            progress.write_text(json.dumps({"check_id": "0.1.1", "state": "pass"}))
            os.utime(progress, (time.time() - 7200, time.time() - 7200))

            monitor_data = {"phase_results": [{"phase": "0", "status": "passed", "returncode": 0, "total": 202}]}
            monitor.write_text(json.dumps(monitor_data))
            os.utime(monitor, (time.time() - 7200, time.time() - 7200))

            state, f, d = sw.adapter_qa_phase0(progress, max_age_s=3600, health_monitor_json=monitor, now=time.time())
            self.assertEqual(state, "unknown")
            self.assertEqual(f, [])
            self.assertIn("stale", d)

    def test_qa_fresh_progress_preferred_over_monitor(self):
        with tempfile.TemporaryDirectory() as t:
            progress = Path(t) / "progress.jsonl"
            monitor = Path(t) / "monitor.json"

            # Fresh progress with pass
            recs = [{"check_id": "0.1.1", "state": "pass"}]
            progress.write_text("\n".join(json.dumps(r) for r in recs))

            # Fresh monitor with failure
            monitor_data = {
                "phase_results": [
                    {"phase": "0", "status": "failed", "returncode": 1, "total": 202,
                     "failures": [{"id": "0.10.44", "label": "some failure"}]}
                ]
            }
            monitor.write_text(json.dumps(monitor_data))

            state, f, d = sw.adapter_qa_phase0(progress, max_age_s=3600, health_monitor_json=monitor, now=time.time())
            self.assertEqual(state, "ok")
            self.assertEqual(f, [])
            self.assertIn("aq-qa progress", d)  # Should prefer progress source

    def test_summary_never_calls_unknown_healthy(self):
        out = []
        adapters = {"a": lambda: ("ok", [], "fine"), "b": lambda: ("unknown", [], "stale")}
        with patch("builtins.print", side_effect=lambda *a, **k: out.append(a[0])):
            sw.run(dry_run=True, as_json=True, adapters=adapters)
        summary = json.loads(out[0])
        self.assertIs(summary["healthy"], False)
        self.assertEqual(summary["healthy_sources"], ["a"])

    def test_payload_audit_identity_excludes_measurements(self):
        def audit(measured, threshold):
            return json.dumps({"findings": [{"lane": "claude", "check_id": 1, "severity": "high",
                "measured": measured, "threshold": threshold, "evidence_path": "CLAUDE.md", "suggested_fix": "trim"}]})
        f1 = sw.adapter_payload_audit(lambda: _proc(audit(51234, "<= 40000 bytes")))[1][0]
        f2 = sw.adapter_payload_audit(lambda: _proc(audit(61999, "<= 40000 bytes")))[1][0]
        for key in ("subject", "producer", "path", "authority", "os_error"):
            self.assertEqual(f1[key], f2[key], key)
        self.assertIn("51234", f1["root_fix"])  # measurement stays visible, outside identity
        self.assertNotEqual(f1["root_fix"], f2["root_fix"])

    def test_payload_audit_only_high(self):
        out = json.dumps({"findings": [
            {"lane": "claude", "check_id": 1, "severity": "high", "measured": 9, "threshold": "5", "evidence_path": "CLAUDE.md", "suggested_fix": "trim"},
            {"lane": "codex", "check_id": 5, "severity": "medium", "measured": 1, "threshold": "2", "evidence_path": "x", "suggested_fix": ""}]})
        state, f, _ = sw.adapter_payload_audit(lambda: _proc(out))
        self.assertEqual((state, len(f)), ("findings", 1))
        self.assertEqual(sw.adapter_payload_audit(lambda: _proc("not json"))[0], "unknown")

    def test_code_scanning_missing_alerts_is_unknown(self):
        self.assertEqual(sw.adapter_code_scanning("/nonexistent/alerts.json")[0], "unknown")

    def test_code_scanning_stale_export_is_unknown(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "a.json"
            p.write_text("[]")
            state, f, d = sw.adapter_code_scanning(p, max_age_s=3600, now=time.time() + 7200)
        self.assertEqual((state, f), ("unknown", []))
        self.assertIn("stale", d)

    def test_code_scanning_plans_from_fixture(self):
        alert = {"state": "open", "rule": {"security_severity_level": "high"},
                 "most_recent_instance": {"category": "trivy-custom-aidb", "message": {"text":
                     "Package: transformers\nInstalled Version: 4.57.6\nFixed Version: 5.10.0"}}}
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "a.json"
            p.write_text(json.dumps([alert]))
            state, f, _ = sw.adapter_code_scanning(p)
        self.assertEqual(state, "findings")
        self.assertNotIn("5.10.0", f[0]["os_error"])  # fixed version stays out of identity


def _alert(category, pkg, installed, state, **extra):
    return {"state": state, "most_recent_instance": {
        "category": category, "commit_sha": "abcdef1234567890",
        "message": {"text": f"Package: {pkg}\nInstalled Version: {installed}\nFixed Version: 9.9"}}, **extra}


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for name, value in {"_RUNTIME": root, "_BACKLOG": root / "b.md", "_WORKAROUNDS": root / "w.md"}.items():
            p = patch.object(rsi, name, value); p.start(); self.addCleanup(p.stop)
        p = patch.object(rsi, "_event"); p.start(); self.addCleanup(p.stop)
        self.ids = {}
        for pkg in ("wheel", "setuptools", "ghost"):
            self.ids[pkg] = rsi.failure("a", "s", "github-code-scanning:trivy-custom-x", "Dockerfile",
                                        "trivy", f"{pkg} 1.0 vulnerable")

    def incidents(self):
        return json.loads((rsi._RUNTIME / "rsi-incidents.json").read_text())["incidents"]

    def test_resolves_only_on_positive_closed_evidence(self):
        cat = "trivy-custom-x"
        alerts = [_alert(cat, "wheel", "1.0", "fixed", fixed_at="2026-10-01T00:00:00Z"),
                  _alert(cat, "wheel", "1.0", "dismissed"),
                  _alert(cat, "setuptools", "1.0", "fixed"),
                  _alert(cat, "setuptools", "1.0", "open")]   # one still open: stays open
        # "ghost" has no alerts at all: missing data must not resolve
        with patch("builtins.print"):
            self.assertEqual(sw.reconcile(alerts=alerts), 0)
        inc = self.incidents()
        self.assertEqual(inc[self.ids["wheel"]]["status"], "resolved")
        res = inc[self.ids["wheel"]]["resolution"]
        self.assertIn("upstream fix verified", res["root_cause"])
        self.assertIn("2 alerts", res["root_cause"])
        self.assertIn("abcdef123456", res["root_cause"])
        self.assertEqual((res["regression"], res["validation"]), ("trivy rescan", "alert state fixed"))
        self.assertEqual(inc[self.ids["setuptools"]]["status"], "open")
        self.assertEqual(inc[self.ids["ghost"]]["status"], "open")
        text = rsi._BACKLOG.read_text()
        self.assertIn(f"[DONE", text)
        self.assertIn(f"[OPEN] rsi-{self.ids['wheel']} ", text)  # append-only: OPEN stays
        self.assertIn(f"[DONE] rsi-{self.ids['wheel']} ", text)
        self.assertNotIn(f"[DONE] rsi-{self.ids['ghost']} ", text)
        self.assertIn(f"[OPEN] rsi-{self.ids['ghost']} ", text)

    def test_dry_run_changes_nothing_and_fetch_failure_is_unknown(self):
        alerts = [_alert("trivy-custom-x", "wheel", "1.0", "fixed")]
        with patch("builtins.print"):
            sw.reconcile(alerts=alerts, dry_run=True)
        self.assertEqual(self.incidents()[self.ids["wheel"]]["status"], "open")
        intake = sw._load_intake()
        with patch.object(intake, "_fetch_alerts_from_github", side_effect=intake.AlertSourceError("gh down")), \
             patch.object(sw, "_load_intake", return_value=intake), patch("builtins.print"):
            self.assertEqual(sw.reconcile(), 2)
        self.assertEqual(self.incidents()[self.ids["wheel"]]["status"], "open")

    def test_non_code_scanning_incidents_ignored(self):
        other = rsi.failure("a", "s", "hook", "p", "a", "wheel 1.0 vulnerable")
        with patch("builtins.print"):
            sw.reconcile(alerts=[_alert("hook", "wheel", "1.0", "fixed")])
        self.assertEqual(self.incidents()[other]["status"], "open")


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for name, value in {"_RUNTIME": root, "_BACKLOG": root / "b.md", "_WORKAROUNDS": root / "w.md"}.items():
            p = patch.object(rsi, name, value); p.start(); self.addCleanup(p.stop)
        p = patch.object(rsi, "_event"); p.start(); self.addCleanup(p.stop)

    def ledger(self):
        return json.loads((rsi._RUNTIME / "rsi-incidents.json").read_text())["incidents"]

    def test_two_sweeps_no_duplicates_and_unknown_recorded_as_unknown(self):
        finding = dict(subject="failed-unit:x.service", producer="systemd:failed-unit", path="x.service",
                       authority="systemd", os_error="unit x.service in failed state", severity="medium", root_fix="fix")
        adapters = {"failed-units": lambda: ("findings", [finding], "1"),
                    "aq-qa-phase0": lambda: ("unknown", [], "stale"),
                    "broken": lambda: 1 / 0}
        with patch("builtins.print"):
            sw.run(adapters=adapters)
            sw.run(adapters=adapters)
        inc = self.ledger()
        self.assertEqual(len(inc), 1)
        self.assertEqual(next(iter(inc.values()))["count"], 2)
        self.assertEqual(rsi._BACKLOG.read_text().count("[OPEN]"), 1)

    def test_two_payload_sweeps_with_different_measurements_one_incident(self):
        def audit(m):
            return _proc(json.dumps({"findings": [{"lane": "claude", "check_id": 1, "severity": "high",
                "measured": m, "threshold": "5", "evidence_path": "CLAUDE.md", "suggested_fix": "trim"}]}))
        with patch("builtins.print"):
            for m in (51234, 61999):
                sw.run(adapters={"payload-audit": lambda m=m: sw.adapter_payload_audit(lambda: audit(m))})
        inc = self.ledger()
        self.assertEqual(len(inc), 1)
        only = next(iter(inc.values()))
        self.assertEqual(only["count"], 2)
        self.assertIn("61999", only["root_fix"])

    def test_dry_run_records_nothing_and_reports_unknown(self):
        out = []
        adapters = {"a": lambda: ("findings", [dict(subject="s", producer="p", path="p", authority="a",
                                                  os_error="e", severity="low", root_fix="")], "1"),
                    "b": lambda: ("unknown", [], "stale")}
        with patch("builtins.print", side_effect=lambda *a, **k: out.append(a[0])):
            sw.run(dry_run=True, as_json=True, adapters=adapters)
        summary = json.loads(out[0])
        self.assertEqual((summary["recorded"], summary["unknown"]), (0, ["b"]))
        self.assertFalse((rsi._RUNTIME / "rsi-incidents.json").exists())


class ResolveTests(unittest.TestCase):
    """Sweep resolves open incidents only on positive re-observation, never on unknown."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name, value in {"_RUNTIME": self.root, "_BACKLOG": self.root / "b.md", "_WORKAROUNDS": self.root / "w.md"}.items():
            p = patch.object(rsi, name, value); p.start(); self.addCleanup(p.stop)
        p = patch.object(rsi, "_event"); p.start(); self.addCleanup(p.stop)

    def ledger(self):
        return json.loads((rsi._RUNTIME / "rsi-incidents.json").read_text())["incidents"]

    def sweep(self, adapter, name="src", dry_run=False):
        out = []
        with patch("builtins.print", side_effect=lambda *a, **k: out.append(a[0])):
            sw.run(dry_run=dry_run, as_json=True, adapters={name: adapter})
        return json.loads(out[0])

    def status(self, producer):
        return {i["path"]: i["status"] for i in self.ledger().values() if i["producer"] == producer}

    def test_failed_units_record_then_resolve_and_partial_overlap(self):
        two = "● a.service loaded failed failed A\n● b.service loaded failed failed B\n"
        self.sweep(lambda: sw.adapter_failed_units(lambda: _proc(two)))
        self.assertEqual(self.status("systemd:failed-unit"), {"a.service": "open", "b.service": "open"})
        s = self.sweep(lambda: sw.adapter_failed_units(lambda: _proc("● b.service loaded failed failed B\n")))
        self.assertEqual([r["source"] for r in s["resolved"]], ["src"])
        self.assertEqual(self.status("systemd:failed-unit"), {"a.service": "resolved", "b.service": "open"})
        self.sweep(lambda: sw.adapter_failed_units(lambda: _proc("")))
        self.assertEqual(set(self.status("systemd:failed-unit").values()), {"resolved"})
        self.assertIn("[DONE", rsi._BACKLOG.read_text())

    def test_resolve_error_isolated_reported_and_nonzero_exit(self):
        two = "● a.service loaded failed failed A\n● b.service loaded failed failed B\n"
        self.sweep(lambda: sw.adapter_failed_units(lambda: _proc(two)))
        out = []
        real = rsi.resolve
        def flaky(iid, *a, **k):
            if self.ledger()[iid]["path"] == "a.service":
                raise OSError(30, "Read-only file system")
            return real(iid, *a, **k)
        with patch.object(rsi, "resolve", side_effect=flaky), \
             patch("builtins.print", side_effect=lambda *a, **k: out.append(a[0])):
            rc = sw.run(as_json=True, adapters={
                "src": lambda: sw.adapter_failed_units(lambda: _proc("")),
                "other": lambda: ("ok", [], "fine")})
        s = json.loads(out[0])
        self.assertEqual(rc, 1)
        self.assertEqual(len(s["resolve_errors"]), 1)
        self.assertEqual(s["resolve_errors"][0]["source"], "src")
        self.assertIn("Read-only", s["resolve_errors"][0]["error"])
        self.assertEqual(len(s["resolved"]), 1)
        self.assertIn("other", s["sources"])
        self.assertEqual(self.status("systemd:failed-unit"), {"a.service": "open", "b.service": "resolved"})

    def test_unknown_never_resolves(self):
        self.sweep(lambda: sw.adapter_failed_units(lambda: _proc("● a.service loaded failed failed A\n")))
        s = self.sweep(lambda: sw.adapter_failed_units(lambda: _proc("", 1)))
        self.assertEqual(s["resolved"], [])
        self.assertEqual(self.status("systemd:failed-unit"), {"a.service": "open"})

    def test_dry_run_reports_but_writes_nothing(self):
        self.sweep(lambda: sw.adapter_failed_units(lambda: _proc("● a.service loaded failed failed A\n")))
        before = (rsi._RUNTIME / "rsi-incidents.json").read_text()
        s = self.sweep(lambda: sw.adapter_failed_units(lambda: _proc("")), dry_run=True)
        self.assertEqual(len(s["resolved"]), 1)
        self.assertEqual((rsi._RUNTIME / "rsi-incidents.json").read_text(), before)
        self.assertEqual(self.status("systemd:failed-unit"), {"a.service": "open"})

    def test_qa_progress_resolve_on_pass_skip_only(self):
        p = self.root / "p.jsonl"
        def write(*recs): p.write_text("\n".join(json.dumps(r) for r in recs))
        ad = lambda: sw.adapter_qa_phase0(p, max_age_s=3600, health_monitor_json=self.root / "none.json")
        write({"check_id": "0.2.1", "state": "fail", "description": "aidb"}, {"check_id": "0.3.1", "state": "fail", "description": "x"})
        self.sweep(ad)
        write({"check_id": "0.2.1", "state": "pass"}, {"check_id": "0.3.1", "state": "fail", "description": "x"})
        s = self.sweep(ad)
        self.assertEqual(self.status("aq-qa:phase0"), {"aq-qa check 0.2.1": "resolved", "aq-qa check 0.3.1": "open"})
        self.assertIn("phase-0 check 0.2.1 passing in aq-qa progress run", s["resolved"][0]["evidence"])
        # check absent from the run, or still running: no evidence
        write({"check_id": "0.9.9", "state": "pass"})
        self.sweep(ad)
        self.assertEqual(self.status("aq-qa:phase0")["aq-qa check 0.3.1"], "open")
        write({"check_id": "0.3.1", "state": "running"})
        self.assertEqual(self.sweep(ad)["resolved"], [])

    def test_qa_health_monitor_resolve(self):
        m = self.root / "m.json"
        ad = lambda: sw.adapter_qa_phase0(self.root / "missing.jsonl", max_age_s=3600, health_monitor_json=m)
        def write(**ph): m.write_text(json.dumps({"phase_results": [dict(phase=0, **ph)]}))
        write(returncode=1, total=5, failures=[{"id": "0.2.1", "label": "aidb"}, {"id": "0.4.1", "label": "y"}])
        self.sweep(ad)
        write(returncode=1, total=5, failures=[{"id": "0.4.1", "label": "y"}])
        self.sweep(ad)
        self.assertEqual(self.status("aq-qa:phase0"), {"aq-qa check 0.2.1": "resolved", "aq-qa check 0.4.1": "open"})
        write(returncode=0, total=5, failures=[])
        s = self.sweep(ad)
        self.assertIn("health-monitor JSON run", s["resolved"][0]["evidence"])
        self.assertEqual(set(self.status("aq-qa:phase0").values()), {"resolved"})

    def test_qa_health_monitor_nonzero_without_total_or_detail_is_unknown(self):
        m = self.root / "m.json"
        ad = lambda: sw.adapter_qa_phase0(self.root / "missing.jsonl", max_age_s=3600, health_monitor_json=m)
        m.write_text(json.dumps({"phase_results": [{"phase": 0, "returncode": 1, "total": 5, "failures": [{"id": "0.2.1"}]}]}))
        self.sweep(ad)
        m.write_text(json.dumps({"phase_results": [{"phase": 0, "returncode": 1, "total": 0, "failures": []}]}))
        self.assertEqual(self.sweep(ad)["resolved"], [])
        self.assertEqual(self.status("aq-qa:phase0"), {"aq-qa check 0.2.1": "open"})

    def test_service_error_rate_resolve_requires_read_unit(self):
        bad = "\n".join(json.dumps({"level": "error", "event": "boom"}) for _ in range(6))
        run = lambda out, rc=0: (lambda u: _proc(out, rc))
        mk = lambda r, units: (lambda: sw.adapter_service_error_rate(r, units=units, window_s=60, min_count=5))
        self.sweep(mk(run(bad), ["u1"]))
        self.assertEqual(self.sweep(mk(run("", 1), ["u1"]))["resolved"], [])
        self.assertEqual(self.sweep(mk(run(""), ["u2"]))["resolved"], [])  # u1 not read this time
        s = self.sweep(mk(run("quiet"), ["u1"]))
        self.assertEqual(len(s["resolved"]), 1)
        self.assertEqual(set(self.status("journal:u1").values()), {"resolved"})

    def test_delegation_resolve_only_when_registry_read_and_class_absent(self):
        reg = self.root / "reg.jsonl"
        now = time.time()
        iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
        def write(*recs): reg.write_text("\n".join(json.dumps(dict(r, created=iso(now - 60))) for r in recs))
        ad = lambda: sw.adapter_delegation_outcomes(reg, window_s=3600, now=now)
        write({"id": "1", "agent": "codex", "status": "failed"}, {"id": "2", "agent": "local", "status": "timeout"})
        self.sweep(ad)
        write({"id": "3", "agent": "local", "status": "timeout"})
        self.sweep(ad)
        self.assertEqual(self.status("delegation:codex"), {".agents/delegation/registry.jsonl": "resolved"})
        self.assertEqual(self.status("delegation:local"), {".agents/delegation/registry.jsonl": "open"})
        reg.unlink()  # unreadable registry -> unknown -> nothing resolves
        self.assertEqual(self.sweep(ad)["resolved"], [])
        self.assertEqual(self.status("delegation:local"), {".agents/delegation/registry.jsonl": "open"})

    def test_delegation_missing_log_blocks_marker_class_resolution(self):
        reg = self.root / "reg.jsonl"
        now = time.time()
        created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 60))
        log = self.root / "out.log"
        rec = lambda **kw: json.dumps(dict(id="1", agent="codex", created=created, **kw))
        ad = lambda: sw.adapter_delegation_outcomes(reg, window_s=3600, now=now)
        log.write_text("work\nBlocked: need approval\n")
        reg.write_text(rec(status="done", output_file=str(log)))
        self.sweep(ad)
        self.assertEqual(self.status("delegation:codex"), {".agents/delegation/registry.jsonl": "open"})
        # (a) log archived: lane has an unreadable log -> blocked must stay open
        log.unlink()
        s = self.sweep(ad)
        self.assertEqual(s["resolved"], [])
        self.assertIn("1 unreadable log", s["sources"]["src"]["detail"])
        self.assertEqual(set(self.status("delegation:codex").values()), {"open"})
        # (b) log readable and marker-free -> resolves
        log.write_text("work\nall good\n")
        self.assertEqual(len(self.sweep(ad)["resolved"]), 1)
        self.assertEqual(set(self.status("delegation:codex").values()), {"resolved"})

    def test_delegation_missing_log_does_not_block_status_class(self):
        reg = self.root / "reg.jsonl"
        now = time.time()
        created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 60))
        ad = lambda: sw.adapter_delegation_outcomes(reg, window_s=3600, now=now)
        reg.write_text(json.dumps(dict(id="1", agent="codex", created=created, status="failed")))
        self.sweep(ad)
        reg.write_text(json.dumps(dict(id="2", agent="codex", created=created, status="done",
                                       output_file=str(self.root / "gone.log"))))
        self.assertEqual(len(self.sweep(ad)["resolved"]), 1)

class DelegationServiceTests(unittest.TestCase):
    def _reg(self, d, rows):
        reg = Path(d) / "registry.jsonl"
        reg.write_text("\n".join(json.dumps(r) for r in rows))
        return reg

    def _row(self, d, i, agent, status, log=None, age_s=3600):
        from datetime import datetime, timezone
        out = Path(d) / f"{i}.log"
        if log is not None:
            out.write_text(log)
        created = datetime.fromtimestamp(time.time() - age_s, timezone.utc).isoformat().replace("+00:00", "Z")
        return dict(id=i, agent=agent, status=status, created=created, output_file=str(out))

    def test_delegation_classes_dedupe_window_and_markers(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [self._row(d, f"la{n}", "local-agent", "failed", "boom") for n in range(5)]
            rows += [self._row(d, "old", "codex", "failed", age_s=30 * 86400),
                     self._row(d, "c1", "codex", "cancelled"),
                     self._row(d, "ok", "claude", "done", "all fine"),
                     self._row(d, "b1", "claude", "done", "x\nBlocked: need approval\n"),
                     self._row(d, "q1", "codex", "failed", "ERROR: you hit your usage limit"),
                     self._row(d, "s1", "codex", "done", "failed to load skill /a/SKILL.md: bad yaml"),
                     self._row(d, "t1", "antigravity", "timeout")]
            state, f, _ = sw.adapter_delegation_outcomes(self._reg(d, rows))
            self.assertEqual(state, "findings")
            by = {x["subject"]: x for x in f}
            self.assertEqual(sorted(by), ["delegation:antigravity:timeout", "delegation:claude:blocked",
                                          "delegation:codex:quota", "delegation:codex:skill-load-error:/a/SKILL.md",
                                          "delegation:local-agent:failed"])
            self.assertEqual(by["delegation:local-agent:failed"]["severity"], "medium")
            self.assertIn("5 run(s)", by["delegation:local-agent:failed"]["root_fix"])
            self.assertIn("outputs/la4.log", by["delegation:local-agent:failed"]["root_fix"])
            self.assertEqual(by["delegation:codex:quota"]["severity"], "medium")
            self.assertEqual(by["delegation:antigravity:timeout"]["severity"], "low")
            self.assertEqual(by["delegation:claude:blocked"]["severity"], "low")
            self.assertNotIn("delegation:codex:failed", by)  # old run outside window

    def test_delegation_missing_registry_unknown(self):
        self.assertEqual(sw.adapter_delegation_outcomes("/nonexistent/registry.jsonl")[0], "unknown")

    def test_service_error_rate(self):
        def ev(i): return json.dumps({"level": "error", "event": "learning_loop_error", "ts": f"2026-10-08T10:0{i}:00Z", "id": f"abc{i}def9"})
        out = "\n".join([ev(n) for n in range(6)] + ['{"level":"info","event":"x"}',
                          json.dumps({"level": "error", "event": "rare_error"}), "Permission denied: /x/1", "ok"])
        state, f, _ = sw.adapter_service_error_rate(lambda u: _proc(out), units=["u1"], window_s=60, min_count=5)
        self.assertEqual(state, "findings")
        self.assertEqual(len(f), 1)
        self.assertIn("learning_loop_error", f[0]["os_error"])
        self.assertIn("6 occurrence", f[0]["root_fix"])
        self.assertEqual(sw.adapter_service_error_rate(lambda u: _proc("quiet"), units=["u1"])[0], "ok")
        def boom(u): raise OSError("no journalctl")
        self.assertEqual(sw.adapter_service_error_rate(boom, units=["u1"])[0], "unknown")
        self.assertEqual(sw.adapter_service_error_rate(lambda u: _proc("", 1), units=["u1"])[0], "unknown")


def _cap_report(d, name, gen, classes, by_class=None, version=2):
    caps = [{"key": k, "class": c} for k, c in classes.items()]
    totals = by_class if by_class is not None else {}
    (Path(d) / name).write_text(json.dumps({"schema": "capability-audit/1", "audit_version": version, "generated_at": gen,
                                            "totals": {"by_class": totals}, "capabilities": caps}))


class CapabilityAuditTests(unittest.TestCase):
    def _dir(self, prev, cur, cur_totals=None):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        _cap_report(t.name, "20261008.json", "2026-10-08T06:00:00Z", prev)
        _cap_report(t.name, "20261009.json", "2026-10-09T06:00:00Z", cur, cur_totals)
        _cap_report(t.name, "latest.json", "2026-10-09T06:00:00Z", cur, cur_totals)
        return t.name

    def test_regression_detected_with_severity(self):
        d = self._dir({"a": "ACTIVE", "b": "ACTIVE", "c": "UNUSED-AVAILABLE", "d": "UNUSED-AVAILABLE", "e": "ACTIVE"},
                      {"a": "UNUSED-AVAILABLE", "b": "STALE-CLAIM", "c": "BROKEN", "d": "UNUSED-AVAILABLE", "e": "ACTIVE"})
        state, f, _ = sw.adapter_capability_audit(d)
        self.assertEqual(state, "findings")
        by = {x["path"]: x for x in f}
        self.assertEqual(sorted(by), ["a", "b", "c"])
        self.assertEqual(by["a"]["severity"], "low")
        self.assertEqual(by["b"]["severity"], "medium")
        self.assertEqual(by["c"]["severity"], "medium")
        self.assertIn("regressed from ACTIVE", by["a"]["os_error"])

    def test_no_timer_baseline_means_thresholds_only(self):
        # a committed one-off report in the parent dir must never be the baseline
        with tempfile.TemporaryDirectory() as t:
            sub = Path(t) / "capability-audit"
            sub.mkdir()
            _cap_report(t, "capability-audit-20261008.json", "2026-10-08T06:00:00Z", {"a": "ACTIVE"})
            _cap_report(sub, "latest.json", "2026-10-09T06:00:00Z", {"a": "BROKEN"}, {"BROKEN": 1})
            state, f, detail = sw.adapter_capability_audit(sub)
            self.assertEqual([x["path"] for x in f], ["threshold:BROKEN"])
            self.assertIn("previous=none", detail)

    def test_version_mismatch_skips_regressions(self):
        d = self._dir({"a": "ACTIVE"}, {"a": "BROKEN"})
        _cap_report(d, "20261008.json", "2026-10-08T06:00:00Z", {"a": "ACTIVE"}, version=1)
        state, f, detail = sw.adapter_capability_audit(d)
        self.assertEqual([x for x in f if not x["path"].startswith("threshold:")], [])
        self.assertIn("version-mismatch", detail)

    def test_improvement_is_not_a_finding(self):
        d = self._dir({"a": "BROKEN", "b": "UNDISCOVERABLE"}, {"a": "ACTIVE", "b": "UNUSED-AVAILABLE"})
        self.assertEqual(sw.adapter_capability_audit(d)[:2], ("ok", []))

    def test_threshold_crossed(self):
        d = self._dir({"a": "ACTIVE"}, {"a": "ACTIVE"}, {"UNDISCOVERABLE": 11, "STALE-CLAIM": 1, "BROKEN": 0})
        state, f, _ = sw.adapter_capability_audit(d)
        self.assertEqual(state, "findings")
        self.assertEqual(sorted(x["path"] for x in f), ["threshold:STALE-CLAIM", "threshold:UNDISCOVERABLE"])
        d = self._dir({"a": "ACTIVE"}, {"a": "ACTIVE"}, {"UNDISCOVERABLE": 10})
        self.assertEqual(sw.adapter_capability_audit(d)[0], "ok")

    def test_missing_or_stale_report_unknown(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(sw.adapter_capability_audit(t)[:2], ("unknown", []))
        d = self._dir({"a": "ACTIVE"}, {"a": "ACTIVE"})
        state, f, detail = sw.adapter_capability_audit(d, now=time.time() + 3 * 86400)
        self.assertEqual((state, f), ("unknown", []))
        self.assertIn("stale", detail)

    def test_resolves_when_restored(self):
        d = self._dir({"a": "ACTIVE"}, {"a": "STALE-CLAIM"}, {"STALE-CLAIM": 1})
        _, f, _ = sw.adapter_capability_audit(d)
        incs = {x["path"]: {"producer": x["producer"], "path": x["path"], "error": x["os_error"]} for x in f}
        self.assertEqual(set(incs), {"a", "threshold:STALE-CLAIM"})
        self.assertIsNone(f.cleared(incs["a"]))
        self.assertIsNone(f.cleared(incs["threshold:STALE-CLAIM"]))
        # next day: restored, totals back under limit
        _cap_report(d, "20261010.json", "2026-10-10T06:00:00Z", {"a": "ACTIVE"}, {"STALE-CLAIM": 0})
        _cap_report(d, "latest.json", "2026-10-10T06:00:00Z", {"a": "ACTIVE"}, {"STALE-CLAIM": 0})
        state, f2, _ = sw.adapter_capability_audit(d)
        self.assertEqual((state, list(f2)), ("ok", []))
        self.assertIn("restored to ACTIVE", f2.cleared(incs["a"]))
        self.assertIn("count 0", f2.cleared(incs["threshold:STALE-CLAIM"]))
        self.assertIsNone(f2.cleared({"producer": "other", "path": "a", "error": ""}))


class AntigravityDrainTests(unittest.TestCase):
    def _health(self, d, payload, raw=None):
        p = Path(d) / "drain.json"
        p.write_text(raw if raw is not None else json.dumps(payload))
        return p

    UNDRAINED = {"ok": False, "undrained_count": 2, "undrained": [
        {"task_id": "antigravity-1", "phase": "claimed", "last_nudge_age_s": 7200, "task": "x"},
        {"task_id": "antigravity-2", "phase": "nudged", "last_nudge_age_s": 3600, "task": "y"}]}

    def test_ok(self):
        with tempfile.TemporaryDirectory() as t:
            state, f, _ = sw.adapter_antigravity_drain(self._health(t, {"ok": True, "undrained": []}))
            self.assertEqual((state, list(f)), ("ok", []))

    def test_undrained_two_findings(self):
        with tempfile.TemporaryDirectory() as t:
            state, f, detail = sw.adapter_antigravity_drain(self._health(t, self.UNDRAINED))
            self.assertEqual(state, "findings")
            self.assertEqual([x["subject"] for x in f], ["antigravity-drain:antigravity-1", "antigravity-drain:antigravity-2"])
            self.assertTrue(all(x["producer"] == "antigravity-drain" and x["severity"] == "low" for x in f))
            self.assertIn("antigravity-1", f[0]["root_fix"])
            self.assertIn("claimed", f[0]["root_fix"])
            self.assertIn("2.0h", f[0]["root_fix"])
            self.assertIn("Rule 18", f[0]["root_fix"])
            self.assertIn("2 undrained", detail)

    def test_stale_missing_malformed_unknown(self):
        with tempfile.TemporaryDirectory() as t:
            p = self._health(t, self.UNDRAINED)
            state, f, detail = sw.adapter_antigravity_drain(p, now=time.time() + 7200)
            self.assertEqual((state, list(f)), ("unknown", []))
            self.assertIn("stale", detail)
            self.assertEqual(sw.adapter_antigravity_drain(Path(t) / "nope.json")[:2], ("unknown", []))
            self.assertEqual(sw.adapter_antigravity_drain(self._health(t, None, raw="{not json"))[:2], ("unknown", []))
            self.assertEqual(sw.adapter_antigravity_drain(self._health(t, None, raw="[1]"))[:2], ("unknown", []))

    def test_cleared_resolves_only_unlisted(self):
        with tempfile.TemporaryDirectory() as t:
            _, f, _ = sw.adapter_antigravity_drain(self._health(t, self.UNDRAINED))
            inc = lambda tid: {"producer": "antigravity-drain", "path": tid, "error": ""}
            self.assertIsNone(f.cleared(inc("antigravity-1")))
            partial = dict(self.UNDRAINED, undrained=self.UNDRAINED["undrained"][1:])
            _, f2, _ = sw.adapter_antigravity_drain(self._health(t, partial))
            self.assertIn("no longer undrained", f2.cleared(inc("antigravity-1")))
            self.assertIsNone(f2.cleared(inc("antigravity-2")))
            self.assertIsNone(f2.cleared({"producer": "other", "path": "antigravity-1", "error": ""}))
            _, f3, _ = sw.adapter_antigravity_drain(self._health(t, {"ok": True, "undrained": []}))
            self.assertIn("no longer undrained", f3.cleared(inc("antigravity-2")))


if __name__ == "__main__":
    unittest.main()
