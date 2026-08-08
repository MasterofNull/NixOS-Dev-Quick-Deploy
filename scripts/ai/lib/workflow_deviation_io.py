#!/usr/bin/env python3
"""Durable append-only writer for validated workflow-deviation receipts."""

from __future__ import annotations

import fcntl
import json
import os
import stat
from pathlib import Path
from typing import Any, Mapping

from workflow_deviation import validate


class DeviationWriteError(RuntimeError):
    """A validated deviation could not be durably appended."""


def append_receipt(path: Path, record: Mapping[str, Any]) -> None:
    """Validate and durably append one compact JSONL receipt without following symlinks."""
    validate(record)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC | os.O_NONBLOCK
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o640)
        metadata = os.fstat(fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o022
        ):
            os.close(fd)
            raise DeviationWriteError("deviation-target-unsafe")
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(json.dumps(dict(record), sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except (OSError, ValueError) as exc:
        raise DeviationWriteError(f"deviation-append-failed:{exc.__class__.__name__}") from exc
