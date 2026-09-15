#!/usr/bin/env python3
"""Garbage-collect stale ephemeral `agent-ctx-*` Qdrant scratch collections.

db-4 F2. Per-agent session scratch collections (`agent-ctx-*`) accumulate
with no owner cleanup — this sweep deletes ones strictly older than
RETENTION_DAYS. Everything else (typed memory tiers `agent-memory-*` and
all operational collections — interaction-history, knowledge,
learning-feedback, error-solutions, best-practices, skills-patterns,
wiki-sections, codebase-context, *-patterns, osint-intelligence,
qa-patterns) is NEVER touched: only names matching the exact
`agent-ctx-` prefix are ever considered, and that prefix is re-asserted
immediately before every delete (defense in depth against a future bug
in the candidate-selection logic above it).

Age is determined, in order:
  1. Newest payload timestamp found via a bounded scroll
     (`timestamp` / `created_at` / `ts` keys — mirrors
     dashboard/backend/api/routes/aistack.py's Qdrant scroll pattern).
  2. A trailing unix-epoch suffix parsed from the collection name
     (e.g. `agent-ctx-aq-1787924736`).
  3. Otherwise: UNKNOWN — never deleted (fail-safe on ambiguous age).

Any Qdrant error for a given collection is logged and that collection is
skipped; the sweep never aborts on a single collection's failure.

Usage:
    python3 scripts/ai/qdrant-scratch-gc.py [--dry-run] [--retention-days N]

Env vars:
    QDRANT_URL      — default built from QDRANT_PORT (falls back to 6333)
    QDRANT_PORT     — default 6333
    RETENTION_DAYS  — default 14 (overridden by --retention-days)
    DRY_RUN         — "1"/"true" forces dry-run even without --dry-run
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

# Ports sourced from service environment; fall back to options.nix defaults only.
# Never hardcode — source of truth is nix/modules/core/options.nix (ports.qdrantHttp).
_QDRANT_PORT = os.environ.get("QDRANT_PORT", "6333")
QDRANT_URL = os.environ.get("QDRANT_URL", f"http://127.0.0.1:{_QDRANT_PORT}").rstrip("/")

SCRATCH_PREFIX = "agent-ctx-"
DEFAULT_RETENTION_DAYS = float(os.environ.get("RETENTION_DAYS", "14"))
SCROLL_LIMIT = 100
TIMESTAMP_PAYLOAD_KEYS = ("timestamp", "created_at", "ts")
_NAME_EPOCH_RE = re.compile(r"-(\d{9,13})$")

logging.basicConfig(
    level=logging.INFO,
    format="[qdrant-scratch-gc] %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("qdrant-scratch-gc")
logging.getLogger("httpx").setLevel(logging.WARNING)  # suppress per-request noise; decisions are what matter


@dataclass
class Decision:
    name: str
    action: str  # "kept" | "deleted" | "would-delete" | "skipped-unknown" | "skipped-protected" | "error"
    age_days: Optional[float] = None
    age_source: Optional[str] = None  # "payload" | "name-suffix" | None
    reason: str = ""


def _parse_timestamp(value: Any) -> Optional[float]:
    """Best-effort epoch-seconds parse of a payload timestamp field. Never raises."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v / 1000.0 if v > 1e12 else v
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            pass
        try:
            import datetime

            iso = s.replace("Z", "+00:00")
            return datetime.datetime.fromisoformat(iso).timestamp()
        except ValueError:
            return None
    return None


def _epoch_from_name(name: str) -> Optional[float]:
    """Trailing unix-epoch suffix fallback, e.g. agent-ctx-aq-1787924736."""
    m = _NAME_EPOCH_RE.search(name)
    if not m:
        return None
    digits = m.group(1)
    value = float(digits)
    return value / 1000.0 if len(digits) >= 13 else value


def _newest_payload_timestamp(client: httpx.Client, name: str) -> Optional[float]:
    """Bounded scroll of `name`, returns the newest recognized payload timestamp.

    Mirrors the scroll pattern used for Qdrant recency elsewhere in the
    harness (dashboard/backend/api/routes/aistack.py). Any failure here is
    swallowed by the caller — never crashes the sweep.
    """
    resp = client.post(
        f"{QDRANT_URL}/collections/{name}/points/scroll",
        json={"limit": SCROLL_LIMIT, "with_payload": True, "with_vector": False},
        timeout=15.0,
    )
    resp.raise_for_status()
    points = resp.json().get("result", {}).get("points", [])
    newest: Optional[float] = None
    for pt in points:
        payload = pt.get("payload") or {}
        for key in TIMESTAMP_PAYLOAD_KEYS:
            if key in payload:
                parsed = _parse_timestamp(payload[key])
                if parsed is not None and (newest is None or parsed > newest):
                    newest = parsed
                break
    return newest


def _determine_age_days(client: httpx.Client, name: str, now_ts: float) -> tuple[Optional[float], Optional[str]]:
    """Returns (age_days, source). age_days is None ⇒ UNKNOWN, never delete."""
    try:
        newest = _newest_payload_timestamp(client, name)
    except Exception as exc:  # noqa: BLE001 — a scroll failure must never abort the sweep
        log.warning("scroll failed collection=%s error=%s — falling back to name suffix", name, exc)
        newest = None

    if newest is not None:
        return (now_ts - newest) / 86400.0, "payload"

    epoch = _epoch_from_name(name)
    if epoch is not None:
        return (now_ts - epoch) / 86400.0, "name-suffix"

    return None, None


def _list_collections(client: httpx.Client) -> list[str]:
    resp = client.get(f"{QDRANT_URL}/collections", timeout=15.0)
    resp.raise_for_status()
    return [c["name"] for c in resp.json().get("result", {}).get("collections", [])]


def _delete_collection(client: httpx.Client, name: str) -> None:
    resp = client.delete(f"{QDRANT_URL}/collections/{name}", timeout=15.0)
    resp.raise_for_status()


def sweep(retention_days: float, dry_run: bool) -> list[Decision]:
    decisions: list[Decision] = []
    now_ts = time.time()

    with httpx.Client() as client:
        try:
            all_collections = _list_collections(client)
        except Exception as exc:  # noqa: BLE001 — can't proceed without a listing; report and stop
            log.error("failed to list Qdrant collections: %s", exc)
            return decisions

        # HARD SAFETY: only names starting with the exact scratch prefix are
        # ever candidates. Everything else — typed memory tiers, operational
        # collections — is never inspected or touched.
        candidates = [n for n in all_collections if n.startswith(SCRATCH_PREFIX)]
        log.info(
            "found %d collection(s) total, %d candidate(s) matching prefix %r",
            len(all_collections), len(candidates), SCRATCH_PREFIX,
        )

        for name in candidates:
            # Defense in depth: re-assert the prefix immediately before any
            # decision that could lead to deletion, independent of how the
            # candidate list above was built.
            if not name.startswith(SCRATCH_PREFIX):
                log.error("PROTECTED-PREFIX GUARD tripped for %s — skipping, no delete", name)
                decisions.append(Decision(name, "skipped-protected", reason="prefix guard tripped"))
                continue

            age_days, source = _determine_age_days(client, name, now_ts)

            if age_days is None:
                log.info("skipped-unknown collection=%s reason=no-payload-timestamp-and-no-epoch-suffix", name)
                decisions.append(Decision(name, "skipped-unknown", reason="age undeterminable — fail-safe"))
                continue

            if age_days <= retention_days:
                log.info(
                    "kept collection=%s age_days=%.1f source=%s reason=within-retention(%s)",
                    name, age_days, source, retention_days,
                )
                decisions.append(Decision(name, "kept", age_days, source, "within retention"))
                continue

            if dry_run:
                log.info(
                    "would-delete collection=%s age_days=%.1f source=%s reason=older-than-retention(%s)",
                    name, age_days, source, retention_days,
                )
                decisions.append(Decision(name, "would-delete", age_days, source, "older than retention (dry-run)"))
                continue

            try:
                _delete_collection(client, name)
            except Exception as exc:  # noqa: BLE001 — a delete failure must never abort the sweep
                log.error("delete failed collection=%s error=%s", name, exc)
                decisions.append(Decision(name, "error", age_days, source, f"delete failed: {exc}"))
                continue

            log.info(
                "deleted collection=%s age_days=%.1f source=%s reason=older-than-retention(%s)",
                name, age_days, source, retention_days,
            )
            decisions.append(Decision(name, "deleted", age_days, source, "older than retention"))

    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--retention-days", type=float, default=DEFAULT_RETENTION_DAYS,
        help=f"Delete agent-ctx-* collections strictly older than this many days (default {DEFAULT_RETENTION_DAYS}).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Log decisions without deleting anything.",
    )
    args = parser.parse_args()

    dry_run = args.dry_run or os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes")

    log.info(
        "starting sweep qdrant_url=%s retention_days=%s dry_run=%s",
        QDRANT_URL, args.retention_days, dry_run,
    )
    decisions = sweep(args.retention_days, dry_run)

    counts: dict[str, int] = {}
    for d in decisions:
        counts[d.action] = counts.get(d.action, 0) + 1
    log.info("sweep complete: %s", counts or "no candidates found")

    return 1 if counts.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
