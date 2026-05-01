"""
Checkpoint Service — Phase 16.3

Periodically writes a snapshot of the identity summary to disk so the
coordinator can serve GET /identity/self without replaying the full journal on
every request.

Env vars:
  IDENTITY_CHECKPOINT_INTERVAL_SECONDS  — write interval (default 300)
  IDENTITY_CHECKPOINT_PATH              — output dir (default /var/lib/ai-stack/identity)
  IDENTITY_JOURNAL_PATH                 — passed through to NarrativeEngine
  IDENTITY_SERVICE_MODE                 — "thread" (default) | "oneshot"

Usage — embedded thread inside hybrid coordinator:
    from checkpoint_service import CheckpointService
    svc = CheckpointService()
    svc.start_thread()          # non-blocking; writes every N seconds

Usage — standalone oneshot (systemd timer / --dry-run):
    IDENTITY_SERVICE_MODE=oneshot python3 checkpoint_service.py [--dry-run]
"""

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("identity-kernel")


def _checkpoint_path() -> Path:
    base = os.environ.get(
        "IDENTITY_CHECKPOINT_PATH",
        "/var/lib/ai-stack/identity",
    )
    return Path(base) / "checkpoint.json"


def _interval() -> int:
    try:
        return int(os.environ.get("IDENTITY_CHECKPOINT_INTERVAL_SECONDS", "300"))
    except (TypeError, ValueError):
        return 300


class CheckpointService:
    """
    Manages periodic identity checkpoint writes.

    Designed to be cheap — it just replays the JSONL journal and dumps a JSON
    summary.  All I/O is synchronous and happens in a background thread so the
    query path is never blocked.
    """

    def __init__(self, journal_path: Optional[str] = None) -> None:
        # Import here so the module is self-contained when run standalone.
        from narrative_engine import NarrativeEngine  # type: ignore

        self._engine = NarrativeEngine(journal_path=journal_path)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Checkpoint write
    # ------------------------------------------------------------------

    def write_checkpoint(self, dry_run: bool = False) -> None:
        """
        Generate summary from journal and write to checkpoint file.
        If *dry_run* is True, log intent but skip the actual write.
        """
        summary = self._engine.generate_summary()
        out_path = _checkpoint_path()

        if dry_run:
            logger.info(
                "checkpoint_service [dry_run]: would write to %s — summary keys: %s",
                out_path,
                list(summary.keys()),
            )
            return

        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = out_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
            tmp.replace(out_path)
            logger.debug("checkpoint_service: wrote %s", out_path)
        except OSError as exc:
            logger.warning("checkpoint_service: write failed: %s", exc)

    # ------------------------------------------------------------------
    # Embedded thread
    # ------------------------------------------------------------------

    def start_thread(self) -> None:
        """Start a background daemon thread that writes checkpoints periodically."""
        if self._thread and self._thread.is_alive():
            return

        # Write initial checkpoint immediately on startup (replay from journal).
        self.write_checkpoint()

        def _loop() -> None:
            interval = _interval()
            while not self._stop_event.wait(timeout=interval):
                self.write_checkpoint()

        self._thread = threading.Thread(target=_loop, daemon=True, name="identity-checkpoint")
        self._thread.start()
        logger.info(
            "checkpoint_service: background thread started (interval=%ds)", _interval()
        )

    def stop(self) -> None:
        """Signal the background thread to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Standalone entrypoint (IDENTITY_SERVICE_MODE=oneshot or --dry-run)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
    dry_run = "--dry-run" in sys.argv
    mode = os.environ.get("IDENTITY_SERVICE_MODE", "oneshot")

    svc = CheckpointService()

    if mode == "oneshot" or dry_run:
        svc.write_checkpoint(dry_run=dry_run)
        logger.info("checkpoint_service: oneshot complete")
        sys.exit(0)

    # Continuous mode (not typical for standalone; prefer thread embedding)
    logger.info("checkpoint_service: running continuous mode (interval=%ds)", _interval())
    svc.start_thread()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        svc.stop()
