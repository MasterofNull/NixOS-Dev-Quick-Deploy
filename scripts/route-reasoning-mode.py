#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json


def classify(query: str) -> dict:
    q = query.lower()
    mode = "hybrid"
    retrieval = "semantic+lexical"
    if any(k in q for k in ("exact", "flag", "option", "syntax", "literal")):
        mode = "lexical-first"
        retrieval = "lexical"
    elif any(k in q for k in ("root cause", "incident", "boot", "shutdown", "systemd", "hang")):
        mode = "tree-hybrid"
        retrieval = "tree+semantic"
    elif any(k in q for k in ("memory", "previous", "history", "past fix")):
        mode = "memory-first"
        retrieval = "memory+semantic"
    elif any(k in q for k in ("overview", "explain", "concept")):
        mode = "semantic-first"
        retrieval = "semantic"

    token_budget = 1400
    if mode in {"tree-hybrid", "hybrid"}:
        token_budget = 2200
    if mode == "lexical-first":
        token_budget = 900

    return {
        "query": query,
        "reasoning_mode": mode,
        "retrieval_mode": retrieval,
        "token_budget": token_budget,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Classify reasoning/retrieval mode for a query")
    ap.add_argument("--query", required=True)
    args = ap.parse_args()
    print(json.dumps(classify(args.query), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
