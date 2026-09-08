#!/usr/bin/env python3
"""Frontier-evidence backlog — durable, append-only, deduplicated candidate store.

FA-1 foundation for the Frontier Autopilot (.agents/plans/frontier-evidence-intake/
FRONTIER-AUTOPILOT.md). Each record is one verified frontier technique mapped to an
AQ-OS measurement, with a proposed bounded slice + acceptance goal and an HITL
status. The scan/digest/scheduler layers (FA-2..FA-5) build on this; FA-1 is pure
data + CLI, offline-testable, no scheduler.

Store format: JSON Lines (one record per line) so appends never rewrite history and
concurrent scans can't corrupt earlier records. Dedup is by content hash over
(technique, claim) so re-scans of the same finding do not spam the backlog.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

DEFAULT_STORE = ".agents/plans/frontier-evidence-intake/BACKLOG.jsonl"

VERDICTS = ("adopt", "monitor", "drop", "corrected")
STATUSES = ("new", "approved", "deferred", "dropped", "scheduled")
_REQUIRED = ("technique", "source", "claim", "verdict", "aqos_mapping",
             "proposed_slice", "acceptance_goal")


def content_hash(technique: str, claim: str) -> str:
    return hashlib.sha256(f"{technique}\x1f{claim}".encode("utf-8")).hexdigest()[:12]


def _iso(now: float | None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now if now is not None else time.time()))


def load(store: str | os.PathLike = DEFAULT_STORE) -> list[dict[str, Any]]:
    """Return all records. Fail-safe: missing store -> []; a corrupt line is skipped."""
    out: list[dict[str, Any]] = []
    try:
        text = Path(store).read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("id"):
            out.append(rec)
    return out


def _validate(record: dict[str, Any]) -> str | None:
    for k in _REQUIRED:
        if not record.get(k) or not isinstance(record[k], str):
            return f"missing/invalid field: {k}"
    if record["verdict"] not in VERDICTS:
        return f"verdict must be one of {VERDICTS}"
    return None


def _rewrite(store: str | os.PathLike, records: list[dict[str, Any]]) -> None:
    directory = os.path.dirname(str(store)) or "."
    os.makedirs(directory, exist_ok=True)
    payload = "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)
    fd, tmp = tempfile.mkstemp(prefix=".backlog.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, store)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def add(store: str | os.PathLike, record: dict[str, Any], *, now: float | None = None) -> dict[str, Any]:
    """Add a candidate unless an identical (technique, claim) already exists."""
    err = _validate(record)
    if err:
        return {"added": False, "error": err}
    chash = content_hash(record["technique"], record["claim"])
    existing = load(store)
    if any(r.get("content_hash") == chash for r in existing):
        return {"added": False, "duplicate": True, "content_hash": chash}
    rec = dict(record)
    rec["content_hash"] = chash
    rec["id"] = record.get("id") or f"fe-{chash}"
    rec["discovered_at"] = record.get("discovered_at") or _iso(now)
    rec["status"] = record.get("status") if record.get("status") in STATUSES else "new"
    directory = os.path.dirname(str(store)) or "."
    os.makedirs(directory, exist_ok=True)
    with open(store, "a", encoding="utf-8") as f:  # append-only fast path
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return {"added": True, "id": rec["id"], "content_hash": chash}


def set_status(store: str | os.PathLike, item_id: str, status: str) -> dict[str, Any]:
    if status not in STATUSES:
        return {"ok": False, "error": f"status must be one of {STATUSES}"}
    records = load(store)
    found = False
    for r in records:
        if r.get("id") == item_id:
            r["status"] = status
            found = True
    if not found:
        return {"ok": False, "error": f"no such id: {item_id}"}
    _rewrite(store, records)
    return {"ok": True, "id": item_id, "status": status}


def list_items(store: str | os.PathLike, *, status: str | None = None) -> list[dict[str, Any]]:
    items = load(store)
    if status is not None:
        items = [r for r in items if r.get("status") == status]
    return sorted(items, key=lambda r: (r.get("discovered_at", ""), r.get("id", "")))


def digest(store: str | os.PathLike) -> dict[str, Any]:
    items = load(store)
    by_status: dict[str, int] = {}
    by_verdict: dict[str, int] = {}
    for r in items:
        by_status[r.get("status", "?")] = by_status.get(r.get("status", "?"), 0) + 1
        by_verdict[r.get("verdict", "?")] = by_verdict.get(r.get("verdict", "?"), 0) + 1
    new_lines = [f"[{r['id']}] {r['technique']} — {r['verdict']}: {r['proposed_slice']}"
                 for r in list_items(store, status="new")]
    return {"total": len(items), "by_status": by_status, "by_verdict": by_verdict,
            "new_count": len(new_lines), "new_lines": new_lines}
