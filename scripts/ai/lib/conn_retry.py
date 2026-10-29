"""One-shot retry for local-model requests killed by an llama-cpp restart (suspend/resume).

Stdlib only. Retries once, and only for connection reset / closed / refused errors.
"""
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

MARKERS = (
    "remote end closed connection",
    "connection reset",
    "connection refused",
    "connection aborted",
    "remotedisconnected",
)


def connection_error_reason(output_file: Path) -> Optional[str]:
    """Return the matched marker if the runner's failure text is a connection drop."""
    try:
        text = Path(output_file).read_text(errors="replace")
    except OSError:
        return None
    tail = text[-600:].lower()
    if "error" not in tail:
        return None
    for marker in MARKERS:
        if marker in tail:
            return marker
    return None


def wait_for_health(base_url: str, max_wait_s: float, interval_s: float = 2.0) -> bool:
    deadline = time.monotonic() + max_wait_s
    while True:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval_s)


def run_with_connection_retry(
    run_fn: Callable[[], bool],
    output_file: Path,
    llama_url: str,
    record: Callable[[dict], None],
    wait_s: float = 120.0,
    interval_s: float = 2.0,
    before_retry: Optional[Callable[[], None]] = None,
) -> bool:
    """Run once; on a connection-drop failure wait for /health and run exactly once more."""
    ok = run_fn()
    if ok:
        return True
    reason = connection_error_reason(output_file)
    if reason is None:
        return False
    if not wait_for_health(llama_url, wait_s, interval_s):
        record({"retried": False, "retry_reason": reason, "retry_skipped": "llama health timeout"})
        return False
    if before_retry is not None:
        before_retry()
    ok = run_fn()
    record({"retried": True, "retry_reason": reason})
    return ok


def _main(argv) -> int:
    """CLI used by delegate-to-local: conn_retry.py --task-id ID --output F --llama-url U
    --delegation-dir D [--wait-s N] -- <dispatch command...>"""
    import argparse
    import json
    import subprocess

    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--llama-url", required=True)
    ap.add_argument("--delegation-dir", required=True)
    ap.add_argument("--wait-s", type=float, default=120.0)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    out = Path(a.output)
    retry_id = f"{a.task_id}-r1"
    attempts = []

    def retry_cmd() -> list:
        # Same output file, distinct task id: the registry keeps the first attempt's row.
        c = list(cmd)
        if "--task-id" in c:
            c[c.index("--task-id") + 1] = retry_id
        return c

    def run() -> bool:
        attempts.append(1)
        return subprocess.run(cmd if len(attempts) == 1 else retry_cmd()).returncode == 0

    def registry():
        from task_registry import TaskRegistry  # type: ignore
        return TaskRegistry(Path(a.delegation_dir))

    def safe(fn, *args) -> None:
        try:
            fn(*args)
        except Exception:
            pass

    def mark_first_attempt() -> None:
        # Never delete rows: the original row becomes non-running and points at the retry.
        safe(registry().update_fields_atomic, a.task_id,
             {"status": "failed_retried", "retried_as": retry_id})

    def record(fields: dict) -> None:
        sidecar = dict(fields, retry_task_id=retry_id) if fields.get("retried") else fields
        try:
            Path(str(out) + ".retry.json").write_text(json.dumps(sidecar))
        except OSError:
            pass
        if not fields.get("retried"):
            safe(registry().update_fields_atomic, a.task_id, fields)

    ok = run_with_connection_retry(run, out, a.llama_url, record, a.wait_s, before_retry=mark_first_attempt)
    if len(attempts) > 1:
        reg = registry()
        row = None
        try:
            row = reg.get(retry_id)
        except Exception:
            pass
        final = (row or {}).get("status")
        if final in (None, "running", "failed_retried"):
            final = "done" if ok else "failed"
        safe(reg.update_fields_atomic, retry_id, {"retry_of": a.task_id})
        # Original id resolves to the retry's outcome (waiters on the original id terminate).
        safe(reg.update_fields_atomic, a.task_id,
             {"status": final, "retried": True, "retry_reason": connection_reason_from_sidecar(out),
              "retried_as": retry_id, "first_attempt_status": "failed_retried"})
    return 0 if ok else 1


def connection_reason_from_sidecar(out: Path) -> str:
    import json
    try:
        return json.loads(Path(str(out) + ".retry.json").read_text()).get("retry_reason", "")
    except (OSError, ValueError):
        return ""


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
