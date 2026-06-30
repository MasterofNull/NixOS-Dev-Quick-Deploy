#!/usr/bin/env python3
"""Regression checks for Understand-Anything batch quality validation wiring."""
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
WRAPPER = REPO / "scripts" / "ai" / "aq-understand-anything"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    src = WRAPPER.read_text(encoding="utf-8")
    require("validate-batches" in src, "wrapper should expose validate-batches")
    require('"ok": not (missing or invalid or empty or fallback) and graph_present' in src,
            "validator should require clean batches and graph output")
    require('metadata.get("analysisMode") == "fallback"' in src,
            "validator should reject fallback-provenance batches")
    require("knowledge-graph.json" in src, "validator should require final graph")
    require("expected_batches" in src, "validator should report expected batch count")
    print("ok understand-anything batch validation wiring")


if __name__ == "__main__":
    main()
