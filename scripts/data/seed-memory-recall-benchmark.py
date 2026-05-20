#!/usr/bin/env python3
"""Seed deterministic Phase 54.1 memory-recall benchmark facts.

This is a data repair/convergence tool, not a benchmark shortcut. The benchmark
probes assume the harness has baseline operational facts in agent memory. After a
Qdrant reset or new deployment, this script repopulates those facts through the
public /memory/store contract so recall quality can measure retrieval behavior
rather than empty-corpus state.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEEDS = ROOT / "config" / "memory-recall-benchmark-seeds.json"


def _post_json(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, sort_keys=True).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coordinator-url", default=os.getenv("HYBRID_COORDINATOR_URL", "http://127.0.0.1:8003"))
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.seeds.read_text(encoding="utf-8"))
    source = str(data.get("source") or "memory-recall-benchmark-seeds")
    scope = str(data.get("scope") or "phase54-memory-recall")
    valid_from = int(time.time()) - 60
    endpoint = args.coordinator_url.rstrip("/") + "/memory/store"

    results = []
    for seed in data.get("seeds") or []:
        payload = {
            "memory_type": seed["memory_type"],
            "summary": seed["summary"],
            "content": seed["content"],
            "source": source,
            "metadata": {
                "source": source,
                "scope": scope,
                # Use integer epochs for compatibility with deployed coordinators
                # that predate ISO temporal coercion.
                "valid_from": valid_from,
                "valid_until": 0,
            },
        }
        try:
            body = _post_json(endpoint, payload, args.timeout)
            status = body.get("status", "unknown")
            ok = status in {"stored", "skipped", "success"}
            results.append({
                "summary": seed["summary"],
                "memory_type": seed["memory_type"],
                "ok": ok,
                "status": status,
                "reason": body.get("reason"),
                "memory_id": body.get("memory_id"),
            })
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            results.append({
                "summary": seed.get("summary", ""),
                "memory_type": seed.get("memory_type", ""),
                "ok": False,
                "status": "error",
                "reason": str(exc),
            })

    payload = {
        "seed_file": str(args.seeds),
        "coordinator_url": args.coordinator_url,
        "total": len(results),
        "ok": sum(1 for item in results if item["ok"]),
        "failed": sum(1 for item in results if not item["ok"]),
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"seeded memory recall facts: {payload['ok']}/{payload['total']} ok")
        if payload["failed"]:
            for item in results:
                if not item["ok"]:
                    print(f"FAIL {item['memory_type']} {item['summary']}: {item['reason']}", file=sys.stderr)
    return 0 if payload["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
