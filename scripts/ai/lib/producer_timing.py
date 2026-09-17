"""Content-free, best-effort receipts for local inference producer timing."""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


SCHEMA = "aq.local-producer-timing/v1"


def utc_now() -> str:
    """Return a UTC event timestamp; durations remain caller-owned monotonic values."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def output_path_from_progress(progress_file: str | Path | None) -> Optional[Path]:
    """Recover the established output path from its existing progress sidecar name."""
    if not progress_file:
        return None
    value = str(progress_file)
    suffix = ".progress.json"
    return Path(value[: -len(suffix)]) if value.endswith(suffix) else None


def _duration(start: Optional[float], end: Optional[float]) -> Optional[float]:
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, (int, float))
        or not isinstance(end, (int, float))
    ):
        return None
    value = end - start
    return value if math.isfinite(value) and value >= 0 else None


def _serialize(receipt: dict) -> str:
    return json.dumps(receipt, separators=(",", ":"))


def write_receipt(
    output_file: Path,
    *,
    producer: str,
    task_id: Optional[str],
    output_task_id: Optional[str],
    call_number: Optional[int],
    invocation_sequence: Optional[int],
    streaming: bool,
    timing_mode: str,
    terminal_state: str,
    failure_category: Optional[str] = None,
    local_admission_started: Optional[float] = None,
    local_admission_completed: Optional[float] = None,
    request_started: Optional[float] = None,
    request_started_utc: Optional[str] = None,
    first_visible_content: Optional[float] = None,
    first_visible_content_utc: Optional[str] = None,
    first_visible_content_observation: str = "unavailable",
    request_completed: Optional[float] = None,
    request_completed_utc: Optional[str] = None,
) -> None:
    """Persist one bounded latest-call receipt without ever affecting inference."""
    try:
        receipt = {
            "schema": SCHEMA,
            "producer": producer,
            "task_id": task_id,
            "output_task_id": output_task_id,
            "call_number": call_number,
            "invocation_sequence": invocation_sequence,
            "streaming": streaming,
            "timing_mode": timing_mode,
            "terminal_state": terminal_state,
            "failure_category": failure_category,
            "local_admission_wait_seconds": _duration(
                local_admission_started, local_admission_completed
            ),
            "server_queue_wait_seconds": None,
            "request_started_utc": request_started_utc,
            "first_visible_content_utc": first_visible_content_utc,
            "request_completed_utc": request_completed_utc,
            "request_elapsed_seconds": _duration(request_started, request_completed),
            "time_to_first_visible_content_seconds": _duration(
                request_started, first_visible_content
            ),
            "first_visible_content_observation": first_visible_content_observation,
        }
        path = Path(str(output_file) + ".timing.json")
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(_serialize(receipt), encoding="utf-8")
        os.replace(temporary, path)
    except Exception:
        pass
