#!/usr/bin/env python3
"""Actionable attention notifications: format, identity/update, rate limit, snooze, actions."""
from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))


def fresh(tmp):
    os.environ["ATTENTION_QUEUE_DIR"] = tmp
    os.environ["ATTENTION_MIRROR_PATH"] = str(Path(tmp) / "mirror.json")
    os.environ.pop("ATTENTION_NOTIFY", None)
    sys.modules.pop("attention_queue", None)
    return importlib.import_module("attention_queue")


def P(aq, title="QA phase 0: 1 check failing (0.2.1 aidb port)", sev="high", **kw):
    return aq.push("mon", sev, "human_gate", title, "line one\nline two", "do x",
                   dedup_key=kw.pop("dedup_key", "qa-phase-0"), command="aq-qa 0 --machine",
                   why="stack degraded", next_step="rerun", **kw)


def test_format():
    with tempfile.TemporaryDirectory() as t:
        aq = fresh(t)
        s, b = aq.format_notification({
            "id": "attn-1", "title": "T <b>", "detail": "token=abc123secret more\nx", "why": "w",
            "next_step": "n", "command": "aq-qa 0 --machine", "autonomy_boundary": "human_gate"})
        assert "&lt;b&gt;" in s and "abc123secret" not in b
        assert "Why: w" in b and "Next: n" in b and "Run: aq-qa 0 --machine" in b and "ID: attn-1" in b
        long = aq.format_notification({"id": "a", "title": "t", "detail": "d" * 900, "why": "w" * 900})[1]
        assert len(long) <= 480
        assert "aq-approve show attn-9" in aq.format_notification({"id": "attn-9", "title": "t"})[1]


def test_identity_update_ratelimit_snooze():
    with tempfile.TemporaryDirectory() as t:
        aq = fresh(t)
        ident = lambda: aq._alert_identity(aq.get_pending()[0])  # noqa: E731
        with mock.patch.object(aq, "_spawn_notifier") as spawn:
            a = P(aq)
            assert a and spawn.call_count == 1
            assert P(aq) is None and spawn.call_count == 1, "unchanged -> deduped, no notify"
            b = P(aq, title="QA phase 0: 2 checks failing (a, b)")
            assert b == a, "update returns the existing id"
            alerts = aq.get_pending()
            assert len(alerts) == 1 and alerts[0]["title"].startswith("QA phase 0: 2"), alerts
            assert spawn.call_count == 1, "rate limited"
            P(aq, title="QA phase 0: 8 checks failing (a, b, c)", sev="critical")
            assert spawn.call_count == 2, "escalation notifies"
            aq._state_update(ident(), lambda e: e.update(notified_at=time.time() - 4000))
            P(aq, title="QA phase 0: 9 checks failing (a, b, c)", sev="critical")
            assert spawn.call_count == 3, "window elapsed -> replace notification"
            aq._state_update(ident(), lambda e: e.update(notified_at=0))
            assert aq.snooze(a, 3600)
            P(aq, title="QA phase 0: 10 checks failing (a, b, c)", sev="critical")
            assert spawn.call_count == 3, "snoozed -> silent"
            assert aq.get_pending(include_snoozed=False) == [] and len(aq.get_pending()) == 1
            assert aq.pending_count() == 0
        with mock.patch.object(aq, "_spawn_notifier") as spawn:
            aq._state_update(ident(), lambda e: e.update(snoozed_until=0, notified_at=time.time()))
            assert aq.resolve(a, "dismissed", "owner")
            c = P(aq, title="QA phase 0: 1 check failing (z)")
            assert c and c != a and spawn.call_count == 0, "same identity inside window -> no new popup"
        with mock.patch.object(aq, "_spawn_notifier"):
            x = aq.push("s", "low", "human_gate", "same", "d", "p")
            assert x and aq.push("s", "low", "human_gate", "same", "d2", "p") is None


def test_helper_is_detached():
    with tempfile.TemporaryDirectory() as t:
        aq = fresh(t)
        with mock.patch.object(aq.subprocess, "Popen") as popen:
            P(aq)
            kw = popen.call_args.kwargs
            assert kw["start_new_session"] is True and kw["stdout"] == subprocess.DEVNULL
            assert popen.call_args.args[0][-2] == "--notify"
            popen.return_value.wait.assert_not_called()
            popen.return_value.communicate.assert_not_called()


def test_notify_main_actions_and_fallback():
    with tempfile.TemporaryDirectory() as t:
        aq = fresh(t)
        with mock.patch.object(aq, "_spawn_notifier"):
            aid = P(aq, executor="nixos_rebuild_hint")
        proc = mock.Mock()
        proc.communicate.return_value = ("42\nsnooze\n", "")
        with mock.patch.object(aq, "_actions_supported", return_value=True), \
             mock.patch.object(aq.subprocess, "Popen", return_value=proc) as popen:
            aq._notify_main(aid)
            cmd = popen.call_args.args[0]
            assert cmd[0] == "notify-send" and "-p" in cmd and "-r" not in cmd
            assert "--action=review=Review & approve" in cmd and "--action=dismiss=Dismiss" in cmd
        st = aq._state_update(aq._alert_identity(aq.get_by_id(aid)))
        assert st["notify_id"] == 42 and st["snoozed_until"] > time.time(), st
        proc.communicate.return_value = ("42\n", "")
        with mock.patch.object(aq, "_actions_supported", return_value=True), \
             mock.patch.object(aq.subprocess, "Popen", return_value=proc) as popen:
            aq._notify_main(aid)
            cmd = popen.call_args.args[0]
            assert cmd[cmd.index("-r") + 1] == "42", "replaces previous notification"
        with mock.patch.object(aq, "_actions_supported", return_value=False), \
             mock.patch.object(aq.subprocess, "Popen", return_value=proc) as popen:
            aq._notify_main(aid)
            cmd = popen.call_args.args[0]
            assert not any(c.startswith("--action") for c in cmd) and "Run: aq-qa 0 --machine" in cmd[-1]


def test_handle_actions():
    with tempfile.TemporaryDirectory() as t:
        aq = fresh(t)
        with mock.patch.object(aq, "_spawn_notifier"):
            aid = P(aq)
        popen = mock.Mock()
        os.environ["DASHBOARD_URL"] = "http://dash.test:1"
        assert aq.handle_action("open", aid, popen=popen)
        assert popen.call_args.args[0] == ["xdg-open", f"http://dash.test:1/api/alerts/{aid}/view"]
        os.environ["ATTENTION_TERMINAL_CMD"] = "myterm -e bash -c {cmd}"
        popen.reset_mock()
        assert aq.handle_action("show", aid, popen=popen)
        argv = popen.call_args.args[0]
        assert argv[:4] == ["myterm", "-e", "bash", "-c"] and f"aq-approve show {aid}" in argv[4]
        popen.reset_mock()
        assert aq.handle_action("review", aid, popen=popen)
        assert f"aq-approve review {aid}" in popen.call_args.args[0][4], "review goes via the prompting subcommand"
        assert not aq.handle_action("bogus", aid, popen=popen)
        assert aq.handle_action("snooze", aid) and aq.is_snoozed(aq.get_by_id(aid))
        assert aq.handle_action("dismiss", aid) and aq.get_by_id(aid) is None
        last = (Path(t) / "ATTENTION_ARCHIVE.jsonl").read_text().splitlines()[-1]
        assert '"dismissed"' in last and '"resolved_by": "owner"' in last
        del os.environ["ATTENTION_TERMINAL_CMD"], os.environ["DASHBOARD_URL"]


def test_open_link_validation():
    with tempfile.TemporaryDirectory() as t:
        aq = fresh(t)
        os.environ["DASHBOARD_URL"] = "http://dash.test:1"
        d = aq.dashboard_link("attn-x")
        ok = "http://dash.test:1/somewhere"
        assert aq.safe_open_url(ok, "attn-x") == ok
        for bad in ("file:///etc/passwd", "javascript:alert(1)", "https://evil.example/x",
                    "http://dash.test:2/x", "https://dash.test:1/x", "-x", "--help http://dash.test:1/", "", "http://dash.test:1/a b"):
            assert aq.safe_open_url(bad, "attn-x") == d, bad
        del os.environ["DASHBOARD_URL"]


def test_view_host_and_redaction():
    with tempfile.TemporaryDirectory() as t:
        aq = fresh(t)
        for h in ("localhost", "localhost:8889", "127.0.0.1:8889", "[::1]:8889", "[::1]"):
            assert aq.host_allowed(h), h
        for h in ("", "evil.example", "evil.example:8889", "127.0.0.1.evil.example", "localhost.evil.com"):
            assert not aq.host_allowed(h), h
        os.environ["ATTENTION_VIEW_ALLOWED_HOSTS"] = "nixos.lan:8889"
        assert aq.host_allowed("nixos.lan:8889") and not aq.host_allowed("nixos.lan")
        del os.environ["ATTENTION_VIEW_ALLOWED_HOSTS"]
        import asyncio
        sys.path.insert(0, str(ROOT / "dashboard" / "backend"))
        try:
            from api.routes import aistack
        except Exception as exc:  # backend deps missing in this interpreter
            print(f"SKIP route-level checks ({type(exc).__name__}: {exc})")
            return
        with mock.patch.object(aq, "_spawn_notifier"):
            aid = aq.push("s", "high", "human_gate", "T", "password=hunter2xyz detail", "p")
        assert len(aid) >= 21 and aid.startswith("attn-")
        aistack._repo_root = lambda: ROOT
        def call(host, site=None):
            h = [(b"host", host.encode())] + ([(b"sec-fetch-site", site.encode())] if site else [])
            from starlette.requests import Request
            req = Request({"type": "http", "headers": h, "method": "GET", "path": "/", "query_string": b""})
            return asyncio.run(aistack.get_alert_view(aid, req))
        assert call("evil.example").status_code == 403
        assert call("localhost:8889", "cross-site").status_code == 403
        r = call("localhost:8889", "none")
        assert r.status_code == 200 and b"hunter2xyz" not in r.body and b"[redacted]" in r.body


def test_helper_cap():
    import fcntl
    with tempfile.TemporaryDirectory() as t:
        aq = fresh(t)
        held = [aq._acquire_helper_slot() for _ in range(aq._MAX_HELPERS)]
        assert all(held) and aq._acquire_helper_slot() is None, "5th helper gets no slot"
        with mock.patch.object(aq, "_spawn_notifier"):
            aid = P(aq)
        proc = mock.Mock()
        proc.communicate.return_value = ("7\n", "")
        with mock.patch.object(aq, "_actions_supported", return_value=True), \
             mock.patch.object(aq.subprocess, "Popen", return_value=proc) as popen:
            aq._notify_main(aid)
            cmd = popen.call_args.args[0]
            assert not any(c.startswith("--action") for c in cmd), "over cap -> body-only popup"
        for fh in held:
            fcntl.flock(fh, fcntl.LOCK_UN); fh.close()
        assert aq._acquire_helper_slot() is not None


def test_producers():
    with tempfile.TemporaryDirectory() as t:
        fresh(t)
        spec = importlib.util.spec_from_file_location("m", ROOT / "scripts/health/ai-stack-health-monitor.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        got = []
        m.push = lambda **k: got.append(k)
        m._PHASES = ["0"]
        m.write_status = lambda s: None
        m.run_aq_qa = lambda ph: {"tests": [
            {"id": "0.10.66", "status": "FAIL", "name": "aq-confine"},
            {"id": "0.2.1", "status": "FAIL", "name": "aidb port"}]}
        m.main()
        k = got[0]
        assert k["dedup_key"] == "qa-phase-0" and k["command"] == "aq-qa 0 --machine"
        assert "0.10.66" in k["title"] and "0.2.1" in k["title"] and len(k["title"]) <= 80, k["title"]
        m.run_aq_qa = lambda ph: {"tests": [{"id": "0.2.1", "status": "FAIL", "name": "aidb port"}]}
        got.clear()
        m.main()
        assert got[0]["dedup_key"] == "qa-phase-0" and "1 check failing" in got[0]["title"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("ALL PASS")
