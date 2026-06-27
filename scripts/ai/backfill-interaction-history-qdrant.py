#!/usr/bin/env python3
"""Backfill interaction_history rows → Qdrant interaction-history collection.

Fetches rows from AIDB /history (paginated), embeds via /vector/embed,
upserts into Qdrant interaction-history collection.

Usage:
    python3 scripts/ai/backfill-interaction-history-qdrant.py [--batch-size N] [--dry-run]

Env vars:
    AIDB_URL      — default http://127.0.0.1:8002
    AIDB_API_KEY  — falls back to /run/secrets/aidb_api_key
    QDRANT_URL    — default http://127.0.0.1:6333
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from typing import Any

import httpx

# Ports sourced from service environment; fall back to options.nix defaults only.
# Never hardcode — source of truth is nix/modules/core/options.nix.
_AIDB_PORT = os.environ.get("AIDB_PORT", "8002")
_QDRANT_PORT = os.environ.get("QDRANT_PORT", "6333")
AIDB_URL = os.environ.get("AIDB_URL", f"http://127.0.0.1:{_AIDB_PORT}")
QDRANT_URL = os.environ.get("QDRANT_URL", f"http://127.0.0.1:{_QDRANT_PORT}")
COLLECTION = "interaction-history"


def _api_key() -> str:
    key = os.environ.get("AIDB_API_KEY", "")
    if key:
        return key
    try:
        return open("/run/secrets/aidb_api_key").read().strip()
    except OSError:
        return ""


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _fetch_all_interactions(client: httpx.Client, api_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    batch = 200
    while True:
        resp = client.get(
            f"{AIDB_URL}/history",
            params={"limit": batch, "offset": offset},
            headers=_auth(api_key),
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        page = data if isinstance(data, list) else data.get("history", data.get("interactions", data.get("results", [])))
        if not page:
            break
        rows.extend(page)
        if len(page) < batch:
            break
        offset += batch
        time.sleep(0.05)
    return rows


def _embed(client: httpx.Client, texts: list[str], api_key: str) -> list[list[float]]:
    resp = client.post(
        f"{AIDB_URL}/vector/embed",
        json={"texts": texts},
        headers=_auth(api_key),
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def _scroll_existing_ids(client: httpx.Client) -> set[int]:
    existing: set[int] = set()
    scroll_offset = None
    while True:
        body: dict[str, Any] = {"limit": 1000, "with_payload": False, "with_vector": False}
        if scroll_offset is not None:
            body["offset"] = scroll_offset
        resp = client.post(
            f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
            json=body,
            timeout=30.0,
        )
        if resp.status_code != 200:
            print(f"WARN: cannot scroll Qdrant ({resp.status_code}) — will upsert all")
            break
        data = resp.json().get("result", {})
        for pt in data.get("points", []):
            existing.add(pt["id"])
        scroll_offset = data.get("next_page_offset")
        if not scroll_offset:
            break
    return existing


def _point_id(interaction_id: str) -> int:
    return int(hashlib.md5(f"interaction/{interaction_id}".encode()).hexdigest()[:8], 16)


def _upsert(client: httpx.Client, points: list[dict[str, Any]]) -> None:
    resp = client.put(
        f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true",
        json={"points": points},
        timeout=30.0,
    )
    resp.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=20,
                        help="Texts per embed call (default 20 — conservative to avoid GPU saturation)")
    parser.add_argument("--sleep", type=float, default=1.0,
                        help="Seconds between batches (default 1.0 — throttles embed service)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = _api_key()
    if not api_key:
        print("ERROR: no AIDB API key (set AIDB_API_KEY or ensure /run/secrets/aidb_api_key is readable)", file=sys.stderr)
        sys.exit(1)

    with httpx.Client() as client:
        print(f"Fetching interactions from {AIDB_URL}/history ...")
        rows = _fetch_all_interactions(client, api_key)
        print(f"PostgreSQL interaction_history (via API): {len(rows)} rows")

        print(f"Scrolling existing Qdrant points in {COLLECTION} ...")
        existing_ids = _scroll_existing_ids(client)
        print(f"Qdrant {COLLECTION}: {len(existing_ids)} existing points")

        to_process = [r for r in rows if _point_id(str(r.get("interaction_id", ""))) not in existing_ids]
        print(f"Rows to vectorize: {len(to_process)} (skipping {len(rows) - len(to_process)} already present)")

        if args.dry_run:
            print("DRY RUN — no writes")
            return

        total_ok = 0
        total_fail = 0
        for i in range(0, len(to_process), args.batch_size):
            batch = to_process[i : i + args.batch_size]
            texts = [
                (str(r.get("query") or ""))[:80] + "\n\n" + (str(r.get("response") or ""))
                for r in batch
            ]
            try:
                vectors = _embed(client, texts, api_key)
            except Exception as exc:
                print(f"WARN: embed batch {i // args.batch_size} failed: {exc}")
                total_fail += len(batch)
                continue

            points = []
            for row, vector in zip(batch, vectors):
                iid = str(row.get("interaction_id", ""))
                points.append({
                    "id": _point_id(iid),
                    "vector": vector,
                    "payload": {
                        "interaction_id": iid,
                        "query": (str(row.get("query") or ""))[:500],
                        "response": (str(row.get("response") or ""))[:1000],
                        "agent_type": row.get("agent_type") or "unknown",
                        "project": row.get("project") or "default",
                        "created_at": str(row.get("created_at", "")),
                        "source": "backfill",
                    },
                })

            try:
                _upsert(client, points)
                total_ok += len(points)
                print(f"  batch {i // args.batch_size + 1}: upserted {len(points)} (total {total_ok})")
            except Exception as exc:
                print(f"WARN: upsert batch {i // args.batch_size} failed: {exc}")
                total_fail += len(batch)

            time.sleep(args.sleep)

        print(f"\nDone. OK={total_ok} FAIL={total_fail}")


if __name__ == "__main__":
    main()
