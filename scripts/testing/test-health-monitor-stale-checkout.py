#!/usr/bin/env python3
"""Stale-checkout annotation for ai-stack-health-monitor, on a hermetic fake repo behind origin/main."""
from __future__ import annotations

import importlib.util
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MONITOR = ROOT / "scripts" / "health" / "ai-stack-health-monitor.py"


def git(repo: Path, *a: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                   check=True, capture_output=True)


def main() -> int:
    spec = importlib.util.spec_from_file_location("monitor_stale_under_test", MONITOR)
    assert spec and spec.loader
    mon = importlib.util.module_from_spec(spec)
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

    assert mon.checkout_staleness(tmp / "missing")["behind"] is None
    no_origin = tmp / "plain"
    subprocess.run(["git", "init", "-q", str(no_origin)], check=True)
    assert mon.checkout_staleness(no_origin)["behind"] is None
    print("PASS: health monitor annotates a checkout behind origin/main and stays silent when current/unknown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
