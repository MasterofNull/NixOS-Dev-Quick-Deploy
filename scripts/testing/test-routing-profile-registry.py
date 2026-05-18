#!/usr/bin/env python3
"""Reject intent-map profiles that are not canonical routing profiles."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from core.routing_contract import PROFILE_REGISTRY  # noqa: E402


def main() -> None:
    payload = json.loads((ROOT / "config" / "intent-routing-map.json").read_text())
    intents = payload.get("intents") or {}
    unknown: list[str] = []
    for intent, entry in intents.items():
        for key in ("profile", "fallback_profile"):
            profile = str((entry or {}).get(key) or "").strip()
            if profile and profile not in PROFILE_REGISTRY:
                unknown.append(f"{intent}.{key}={profile}")
    if unknown:
        raise SystemExit("unknown routing profiles: " + ", ".join(sorted(unknown)))
    print(f"PASS: {len(intents)} intent mappings use canonical routing profiles")


if __name__ == "__main__":
    main()
