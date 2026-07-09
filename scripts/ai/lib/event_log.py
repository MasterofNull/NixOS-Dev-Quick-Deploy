#!/usr/bin/env python3
"""event_log — append-only A2A event log (WS2). Clobber-proof by construction.

Primary store is a JSONL file opened O_APPEND: POSIX guarantees each append is
atomic, so concurrent producers never overwrite each other (the exact failure
that clobbered RESUME.json). Redis Streams is an OPTIONAL mirror for fan-out
when REDIS_URL is set — never required (local-first: the file is truth).

API:
    emit(agent, type, payload=..., subject=..., event_id=...) -> Envelope
    append(envelope) -> Envelope
    read_all(*, verify=True) -> list[Envelope]      # idempotent (dedup by id)
    read_since(ts) -> list[Envelope]

Idempotency: duplicate event_id collapses at read time (first occurrence wins).
Signing: emit() signs when a key is available (envelope._signing_key); read_all
drops events whose present sig fails to verify.

Kill switch: none needed — this is additive; direct file writers still work
during migration. Path override: A2A_EVENT_LOG env.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from contracts.events import Envelope  # noqa: E402


def log_path() -> Path:
    p = os.environ.get("A2A_EVENT_LOG", "").strip()
    if p:
        return Path(p)
    return _REPO_ROOT / ".agents" / "events" / "a2a-events.jsonl"


def append(env: Envelope) -> Envelope:
    """Atomically append one envelope (signed if a key is available)."""
    signed = env.signed()
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # LEADING newline (not trailing): if a crashed writer left a torn line with
    # no newline, our leading "\n" starts us on a fresh line so we never glue
    # onto — and thereby corrupt/lose — a following event. Readers skip the
    # blank first line. Records stay one-per-line and independently parseable.
    line = "\n" + signed.model_dump_json()
    # O_APPEND makes the write atomic wrt other appenders (no lock, no clobber).
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
    _mirror_to_redis(signed)
    return signed


def emit(
    agent: str,
    type: str,
    *,
    payload: Optional[dict[str, Any]] = None,
    subject: Optional[str] = None,
    event_id: Optional[str] = None,
) -> Envelope:
    """Build and append an envelope in one call."""
    kwargs: dict[str, Any] = {"agent": agent, "type": type, "payload": payload or {}}
    if subject is not None:
        kwargs["subject"] = subject
    if event_id is not None:
        kwargs["event_id"] = event_id
    return append(Envelope(**kwargs))


def read_all(*, verify: bool = True) -> list[Envelope]:
    """Return all events in append order, deduped by event_id (first wins).

    Corrupt lines are skipped (a partial line from a crash mid-append must not
    break every reader). Events with a present-but-invalid signature are dropped
    when verify=True.
    """
    path = log_path()
    out: list[Envelope] = []
    seen: set[str] = set()
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            env = Envelope.model_validate_json(line)
        except Exception:
            continue  # skip torn/corrupt line
        if env.event_id in seen:
            continue  # idempotent collapse
        if verify and not env.verify():
            continue  # bad signature
        seen.add(env.event_id)
        out.append(env)
    return out


def read_since(ts: float, *, verify: bool = True) -> list[Envelope]:
    return [e for e in read_all(verify=verify) if e.ts >= ts]


def _mirror_to_redis(env: Envelope) -> None:
    """Best-effort Redis Streams mirror. Silent no-op when unavailable."""
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return
    try:
        import redis  # type: ignore

        r = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        r.xadd(
            os.environ.get("A2A_EVENT_STREAM", "aq:a2a:events"),
            {"envelope": env.model_dump_json()},
            maxlen=int(os.environ.get("A2A_EVENT_STREAM_MAXLEN", "10000")),
            approximate=True,
        )
    except Exception:
        pass  # mirror is an optimization, never a dependency


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(prog="event_log.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit")
    e.add_argument("--agent", required=True)
    e.add_argument("--type", required=True)
    e.add_argument("--subject", default=None)
    e.add_argument("--payload", default="{}", help="JSON object")
    sub.add_parser("tail").add_argument("-n", type=int, default=10)
    sub.add_parser("verify")
    args = ap.parse_args()

    if args.cmd == "emit":
        env = emit(args.agent, args.type, payload=json.loads(args.payload), subject=args.subject)
        print(env.event_id)
    elif args.cmd == "tail":
        for ev in read_all()[-args.n:]:
            print(f"{ev.ts:.0f} {ev.agent} {ev.type} {ev.subject or ''}")
    elif args.cmd == "verify":
        evs = read_all(verify=False)
        bad = [e.event_id for e in evs if not e.verify()]
        print(f"events={len(evs)} bad_sig={len(bad)}")
        sys.exit(1 if bad else 0)
