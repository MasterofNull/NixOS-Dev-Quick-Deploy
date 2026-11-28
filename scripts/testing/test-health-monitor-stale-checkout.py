#!/usr/bin/env python3
"""Stale-checkout annotation for ai-stack-health-monitor, on a hermetic fake repo behind origin/main."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MONITOR = ROOT / "scripts" / "health" / "ai-stack-health-monitor.py"


def git(repo: Path, *a: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                   check=True, capture_output=True)


def main() -> int:
    spec = importlib.util.spec_from_file_location("monitor_stale_under_test", MONITOR)
    assert spec and spec.loader
    mon: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mon)

    tmp = Path(tempfile.mkdtemp(prefix="stale-checkout-"))
    up, repo = tmp / "up", tmp / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(up)], check=True)
    (up / "scripts").mkdir()
    (up / "scripts" / "qa.py").write_text("bug\n")
    git(up, "add", "-A")
    git(up, "commit", "-qm", "base")
    subprocess.run(["git", "clone", "-q", str(up), str(repo)], check=True)

    st = mon.checkout_staleness(repo)
    assert st["behind"] == 0 and mon.stale_note(st) == "", st

    (up / "scripts" / "qa.py").write_text("fixed\n")
    (up / "other.txt").write_text("x\n")
    git(up, "add", "-A")
    git(up, "commit", "-qm", "fix(qa): repair scripts/qa.py")
    (up / "other.txt").write_text("y\n")
    git(up, "commit", "-qam", "chore: unrelated")
    git(repo, "fetch", "-q", "origin")

    failing = [{"id": "0.6.1", "name": "qa", "message": "broken in scripts/qa.py"}]
    st = mon.checkout_staleness(repo, failing)
    assert st["behind"] == 2, st
    assert len(st["fixing"]) == 1 and "repair scripts/qa.py" in st["fixing"][0], st
    note = mon.stale_note(st)
    assert "STALE CHECKOUT" in note and "2 commit(s) behind" in note and "repair scripts/qa.py" in note, note

    st = mon.checkout_staleness(repo, [{"id": "x", "message": "no path"}])
    assert st["fixing"] == [] and len(st["recent"]) == 2, st

    # A `..` path in failing output must not poison the log query for the valid one (git exits 128 outside repo).
    st = mon.checkout_staleness(repo, [{"id": "x", "message": "see ../elsewhere/file and scripts/qa.py"}])
    assert len(st["fixing"]) == 1 and "repair scripts/qa.py" in st["fixing"][0], st

    # The systemd unit's PATH has no git: _git must fall back to _SYSTEM_BIN.
    git_dir = str(Path(shutil.which("git") or "git").parent)
    saved_path, saved_bin = os.environ["PATH"], mon._SYSTEM_BIN
    try:
        os.environ["PATH"], mon._SYSTEM_BIN = str(tmp), git_dir
        assert mon.checkout_staleness(repo)["behind"] == 2, "git must resolve via _SYSTEM_BIN"
    finally:
        os.environ["PATH"], mon._SYSTEM_BIN = saved_path, saved_bin

    # main(): stale checkout caps critical -> high, prefixes the title, appends the note, records phase checkout.
    pushed, statuses = [], []
    mon._REPO_ROOT = repo
    mon.push = lambda **spec: pushed.append(spec)
    mon.write_status = statuses.append
    mon.run_payload_audit = lambda: {"state": "ok", "findings": []}
    mon._PHASES = ["0"]
    fails = [{"id": f"0.9.{n}", "status": "FAIL", "description": f"real {n}", "message": "broken in scripts/qa.py"}
             for n in (1, 2, 3)]
    mon.run_aq_qa = lambda phase: {"tests": fails}
    with contextlib.redirect_stderr(io.StringIO()):
        mon.main()
    alert = {a["dedup_key"]: a for a in pushed}["qa-phase-0"]
    assert alert["severity"] == "high", alert["severity"]
    assert alert["title"].startswith("[stale checkout 2 behind]"), alert["title"]
    assert "STALE CHECKOUT" in alert["detail"] and "repair scripts/qa.py" in alert["detail"], alert["detail"]
    assert statuses[-1]["phase_results"][-1]["checkout"]["behind"] == 2, statuses[-1]
    git(repo, "merge", "-q", "--ff-only", "origin/main")
    pushed.clear()
    with contextlib.redirect_stderr(io.StringIO()):
        mon.main()
    alert = {a["dedup_key"]: a for a in pushed}["qa-phase-0"]
    assert alert["severity"] == "critical" and "stale checkout" not in alert["title"], alert

    assert mon.checkout_staleness(tmp / "missing")["behind"] is None
    no_origin = tmp / "plain"
    subprocess.run(["git", "init", "-q", str(no_origin)], check=True)
    assert mon.checkout_staleness(no_origin)["behind"] is None
    print("PASS: health monitor annotates a checkout behind origin/main and stays silent when current/unknown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
