#!/usr/bin/env python3
"""Offline verified-trajectory collector (F3 S5). Never called from aq-land; run by hand after landings.

Reads <delegation dir>/outcome-receipts.jsonl, keeps independently reviewed + CI-passing landings, adds
git-derived path stats (paths and line counts only, no diff bodies) and writes <delegation dir>/trajectories.jsonl (0600).
Any redaction/scan finding, or an unreadable diff range, goes to trajectories.quarantine.jsonl instead.
Kill switch: AQ_TRAJECTORY_COLLECT=0. Counts printed are raw counts.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ai" / "lib"))
from delegation_dir import resolve_delegation_dir, resolve_main_root  # noqa: E402
from outcome_receipt import LOG, _redact, is_eligible, scan  # noqa: E402

OUT = "trajectories.jsonl"
QUAR = "trajectories.quarantine.jsonl"
RETRY = ["range_unreachable"]


def _jsonl(p: Path) -> list[dict]:
    out = []
    try:
        for ln in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict):
                out.append(r)
    except OSError:
        pass
    return out


def _check_mode(p: Path) -> None:
    """Refuse (never chmod) a pre-existing file readable or writable by group/other."""
    try:
        mode = p.stat().st_mode & 0o777
    except FileNotFoundError:
        return
    if mode & 0o077:
        raise PermissionError(f"{p} has mode {mode:04o}; refusing to write (needs 0600, not changed here)")


def _append(p: Path, line: str) -> None:
    fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        if os.fstat(fd).st_mode & 0o077:
            raise PermissionError(f"{p} has group/other permission bits; refusing to write")
        os.write(fd, (line + "\n").encode())
    finally:
        os.close(fd)


def _run(cmd: list[str], cwd: Path, timeout: int = 60) -> str | None:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _pr_meta(repo: Path, pr: int) -> dict | None:
    out = _run(["gh", "pr", "view", str(pr), "--json", "mergeCommit,baseRefOid,headRefOid"], repo, 30)
    try:
        m = json.loads(out or "")
    except ValueError:
        return None
    merge = (m.get("mergeCommit") or {}).get("oid") if isinstance(m, dict) else None
    if not (merge and m.get("baseRefOid") and m.get("headRefOid")):
        return None
    return {"merge_sha": merge, "base": m["baseRefOid"], "head": m["headRefOid"]}


def _numstat(repo: Path, pr: int, base: str, head: str) -> list[dict] | None:
    rng = f"{base}...{head}"
    out = _run(["git", "diff", "--numstat", "--no-renames", rng], repo)
    if out is None:  # commit missing locally: fetch the PR ref once, then retry
        _run(["git", "fetch", "--quiet", "origin", f"refs/pull/{pr}/head"], repo)
        out = _run(["git", "diff", "--numstat", "--no-renames", rng], repo)
    if out is None:
        return None
    files = []
    for ln in out.splitlines():
        a, d, path = (ln.split("\t", 2) + ["", "", ""])[:3]
        files.append({"path": path, "added": int(a) if a.isdigit() else 0, "deleted": int(d) if d.isdigit() else 0})
    return files


def collect(delegation_dir: Path, receipts_dir: Path, repo: Path, only: set[int] | None = None) -> dict:
    main_p, quar_p = delegation_dir / OUT, delegation_dir / QUAR
    delegation_dir.mkdir(parents=True, exist_ok=True)
    _check_mode(main_p)
    _check_mode(quar_p)
    done = {r.get("pr") for r in _jsonl(main_p)}
    quar = _jsonl(quar_p)
    settled = {r.get("pr") for r in quar if r.get("reasons") != RETRY}
    retried = {r.get("pr") for r in quar if r.get("reasons") == RETRY}
    c = {"collected": 0, "quarantined": 0, "not_eligible": 0, "pending": 0, "already_done": 0}
    for rec in _jsonl(receipts_dir / LOG):
        pr = rec.get("pr")
        if not isinstance(pr, int):
            continue
        if only is not None and pr not in only:
            continue
        if not is_eligible(rec):
            c["not_eligible"] += 1
            continue
        if pr in done or pr in settled:
            c["already_done"] += 1
            continue
        meta = _pr_meta(repo, pr)
        if meta is None:
            c["pending"] += 1  # gh missing/offline or PR not merged: retry next run
            continue
        files = _numstat(repo, pr, meta["base"], meta["head"])
        stamp = rec.get("recorded_at")
        if files is None:
            if pr not in retried:
                _append(quar_p, json.dumps({"pr": pr, "recorded_at": stamp, "reasons": RETRY}))
                c["quarantined"] += 1
            else:
                c["pending"] += 1
            continue
        row = dict(rec, rejected_rounds=rec.get("request_changes_rounds", 0), files=files, merge_sha=meta["merge_sha"])
        redacted, found = _redact(json.dumps(row, sort_keys=True))
        found = found + scan(redacted)
        if found:
            reasons = sorted(set(found))
            q = {"pr": pr, "recorded_at": stamp, "reasons": reasons}
            if "redactor_unavailable" not in reasons:
                q["redacted"] = redacted
            _append(quar_p, json.dumps(q))
            c["quarantined"] += 1
            continue
        _append(main_p, redacted)
        c["collected"] += 1
    return c


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--receipts-dir", default="", help="dir holding outcome-receipts.jsonl (default: the output dir)")
    ap.add_argument("--repo", default="", help="git repo for diff ranges (default: main checkout)")
    ap.add_argument("--pr", type=int, action="append", help="only this PR (repeatable)")
    a = ap.parse_args(argv)
    if os.environ.get("AQ_TRAJECTORY_COLLECT") == "0":
        print("trajectory collection disabled (AQ_TRAJECTORY_COLLECT=0)")
        return 0
    out = resolve_delegation_dir(HERE)
    repo = Path(a.repo) if a.repo else resolve_main_root(HERE)
    try:
        c = collect(out, Path(a.receipts_dir) if a.receipts_dir else out, repo, set(a.pr) if a.pr else None)
    except PermissionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(json.dumps(c, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
