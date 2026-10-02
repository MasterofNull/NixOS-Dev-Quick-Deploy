"""Single fail-closed load / atomic save / lock for the PRSI action queue.

Every PRSI queue writer (orchestrator, aq-throttler, ...) goes through this
module so a malformed file is never silently treated as empty and concurrent
read-modify-write cycles serialize (2026-10-02 aq-throttler wipe incident).
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

DEFAULT_QUEUE_PATH = "/var/lib/nixos-ai-stack/optimizer/prsi/action-queue.json"

_held = threading.local()


def queue_path() -> Path:
    return Path(os.getenv("PRSI_ACTION_QUEUE_PATH", DEFAULT_QUEUE_PATH))


def load(path: Optional[Path] = None) -> Dict[str, Any]:
    path = Path(path) if path is not None else queue_path()
    payload: Any = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise RuntimeError(f"PRSI queue {path} is not valid JSON; refusing to overwrite") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("actions", []), list):
            raise RuntimeError(f"PRSI queue {path} is not a {{'actions': [...]}} object; refusing to overwrite")
    return {
        "updated_at": payload.get("updated_at"),
        "actions": payload.get("actions", []),
        "meta": payload.get("meta") if isinstance(payload.get("meta"), dict) else {},
    }


def save(queue: Dict[str, Any], path: Optional[Path] = None) -> None:
    path = Path(path) if path is not None else queue_path()
    queue["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = path.stat().st_mode & 0o7777
    except OSError:
        mode = 0o644
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(queue, indent=2, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def locked(path: Optional[Path] = None) -> Iterator[None]:
    """Exclusive inter-process lock on <queue>.lock; re-entrant within a thread."""
    path = Path(path) if path is not None else queue_path()
    held = getattr(_held, "paths", None)
    if held is None:
        held = _held.paths = {}
    key = str(path)
    if held.get(key, 0) > 0:
        held[key] += 1
        try:
            yield
        finally:
            held[key] -= 1
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + ".lock", "a+") as lockfh:
        fcntl.flock(lockfh.fileno(), fcntl.LOCK_EX)
        held[key] = 1
        try:
            yield
        finally:
            held[key] = 0
            fcntl.flock(lockfh.fileno(), fcntl.LOCK_UN)
