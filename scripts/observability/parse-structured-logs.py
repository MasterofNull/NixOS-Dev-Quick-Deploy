#!/usr/bin/env python3
"""Parse JSONL service logs and emit severity/count summary."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse structured JSON logs and summarize levels/events.")
    ap.add_argument("log_file", help="Path to JSONL log file")
    ap.add_argument("--top", type=int, default=10, help="Top N events to print")
    args = ap.parse_args()

    path = Path(args.log_file)
    if not path.exists():
        print(f"ERROR: log file not found: {path}")
        return 2

    level_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    invalid = 0
    total = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        total += 1
        try:
            obj: Dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            invalid += 1
            continue
        level = str(obj.get("level", "unknown")).lower()
        level_counts[level] += 1
        event = str(obj.get("event") or obj.get("message") or obj.get("msg") or "unknown")
        event_counts[event] += 1

    print("Structured Log Summary")
    print(f"- file: {path}")
    print(f"- rows: {total}")
    print(f"- invalid_json: {invalid}")
    print("- levels:")
    for lvl, cnt in sorted(level_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"  - {lvl}: {cnt}")
    print("- top_events:")
    for evt, cnt in event_counts.most_common(max(1, args.top)):
        print(f"  - {evt}: {cnt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
