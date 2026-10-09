"""Postgres <-> Qdrant vector sync primitives for AIDB (pure, import-light).

Why this exists: the knowledge collection used md5(relative_path)[:8] (32-bit) point ids,
so distinct docs collided and identical paths in different projects collapsed into one
point; queue-full vectorizations were dropped with no retry; nothing compared Postgres to
Qdrant. This module holds the stable id, the durable retry spool and the reconcile math so
server.py and scripts/ai/aq-vector-reconcile share one implementation.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Fixed forever: changing it re-ids every point. Derived once from a constant string.
POINT_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "nixos-ai-stack/aidb/vector-point-id/v1")

# The embed server runs --ctx-size 4096 --parallel 4, i.e. 1024 tokens per slot (~2800
# chars of code/prose). Rows are ingested as ~2000-char chunks, so 2400 keeps whole chunks
# while staying under the slot limit; embed_with_shrink() handles denser-than-average text.
DEFAULT_EMBED_CHARS = int(os.getenv("AIDB_VECTORIZE_EMBED_CHARS", "2400"))
SPOOL_CONTENT_CAP = 20000
MAX_SPOOL_ATTEMPTS = int(os.getenv("AIDB_VECTORIZE_SPOOL_MAX_ATTEMPTS", "10"))


def point_id(project: str, relative_path: str) -> str:
    """Stable, collision-free Qdrant point id (UUID string) for one (project, path)."""
    return str(uuid.uuid5(POINT_ID_NAMESPACE, f"{project}|{relative_path}"))


def embed_input(title: str, content: str, cap: int = DEFAULT_EMBED_CHARS) -> str:
    return (title + "\n\n" + content)[:cap]


async def embed_with_shrink(embed_texts, text: str, min_chars: int = 400, max_tries: int = 3):
    """Embed `text`; on failure (e.g. context-exceeded 400) halve the text and retry."""
    last: Optional[Exception] = None
    for _ in range(max_tries):
        try:
            return (await embed_texts([text]))[0]
        except Exception as exc:  # noqa: BLE001
            last = exc
            if len(text) <= min_chars:
                break
            text = text[: max(min_chars, len(text) // 2)]
    assert last is not None
    raise last


class PendingSpool:
    """Durable JSONL journal of vectorizations that must be retried.

    Lines: {"op":"add", ...item} or {"op":"done","id":<point_id>}. Latest add per id wins.
    Items carry full title/content so draining needs no Postgres access.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._items: Dict[str, Dict[str, Any]] = {}
        self._lines = 0
        self._load()

    def _load(self) -> None:
        self._items.clear()
        self._lines = 0
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue  # torn last line after a crash
                    self._lines += 1
                    if rec.get("op") == "done":
                        self._items.pop(rec.get("id", ""), None)
                    elif rec.get("op") == "add" and rec.get("id"):
                        self._items[rec["id"]] = rec
        except FileNotFoundError:
            pass

    def _append(self, rec: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self._lines += 1

    def _compact_locked(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            for rec in self._items.values():
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)
        self._lines = len(self._items)

    def add(self, *, title: str, content: str, project: str, relative_path: str,
            source_trust_level: str, collection: str = "knowledge", checksum: str = "",
            attempts: int = 0) -> str:
        pid = point_id(project, relative_path)
        rec = {
            "op": "add", "id": pid, "collection": collection, "title": title,
            "content": content[:SPOOL_CONTENT_CAP], "project": project,
            "relative_path": relative_path, "source_trust_level": source_trust_level,
            "checksum": checksum, "attempts": attempts, "queued_at": time.time(),
        }
        with self._lock:
            self._items[pid] = rec
            self._append(rec)
        return pid

    def mark_done(self, pid: str) -> None:
        with self._lock:
            if self._items.pop(pid, None) is None:
                return
            self._append({"op": "done", "id": pid})
            if self._lines > 2 * len(self._items) + 200:
                self._compact_locked()

    def bump_attempt(self, pid: str) -> int:
        """Record a failed retry; returns new attempt count."""
        with self._lock:
            rec = self._items.get(pid)
            if rec is None:
                return 0
            rec = dict(rec, attempts=int(rec.get("attempts", 0)) + 1)
            self._items[pid] = rec
            self._append(rec)
            return rec["attempts"]

    def take(self, n: int) -> List[Dict[str, Any]]:
        """Oldest-first snapshot of up to n retryable items (does not remove)."""
        with self._lock:
            live = [r for r in self._items.values() if int(r.get("attempts", 0)) < MAX_SPOOL_ATTEMPTS]
        live.sort(key=lambda r: r.get("queued_at", 0))
        return live[: max(0, n)]

    def __len__(self) -> int:
        return len(self._items)

    def exhausted(self) -> int:
        return sum(1 for r in self._items.values() if int(r.get("attempts", 0)) >= MAX_SPOOL_ATTEMPTS)


def reconcile(
    pg_rows: Iterable[Dict[str, Any]],
    qdrant_points: Iterable[Tuple[Any, Optional[str]]],
) -> Dict[str, Any]:
    """Compare approved Postgres docs with Qdrant points by the stable id.

    pg_rows: dicts with project, relative_path, checksum (optional), modified_at (optional).
    qdrant_points: (point_id, payload_checksum_or_None). Only a payload checksum can prove
    staleness; points without one are treated as current (never guessed stale).
    Returns per-project counts plus the missing/stale row lists and orphan ids.
      missing: Postgres doc with no point under its stable id
      stale:   point exists but its stored checksum differs from Postgres
      orphan:  point whose id matches no Postgres doc (includes legacy 32-bit int ids)
      legacy:  subset of orphans with a non-UUID (integer) id
    """
    expected: Dict[str, Dict[str, Any]] = {}
    for row in pg_rows:
        expected[point_id(row["project"], row["relative_path"])] = row
    present: Dict[str, Optional[str]] = {}
    orphan_ids: List[Any] = []
    for pid, chk in qdrant_points:
        key = str(pid)
        if key in expected:
            present[key] = chk
        else:
            orphan_ids.append(pid)

    per_project: Dict[str, Dict[str, int]] = {}

    def bucket(project: str) -> Dict[str, int]:
        return per_project.setdefault(project, {"postgres": 0, "missing": 0, "stale": 0})

    missing: List[Dict[str, Any]] = []
    stale: List[Dict[str, Any]] = []
    for pid, row in expected.items():
        b = bucket(row["project"])
        b["postgres"] += 1
        if pid not in present:
            b["missing"] += 1
            missing.append(row)
        else:
            chk = present[pid]
            if chk and row.get("checksum") and chk != row["checksum"]:
                b["stale"] += 1
                stale.append(row)
    legacy = [p for p in orphan_ids if not isinstance(p, str)]
    return {
        "per_project": per_project,
        "totals": {
            "postgres": len(expected),
            "qdrant": len(present) + len(orphan_ids),
            "missing": len(missing),
            "stale": len(stale),
            "orphan": len(orphan_ids),
            "legacy_orphan": len(legacy),
        },
        "missing": missing,
        "stale": stale,
        "orphan_ids": orphan_ids,
        "legacy_ids": legacy,
    }
