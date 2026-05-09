#!/usr/bin/env python3
"""
Task 2.5 validation: context compression ratio and critical-field retention.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HYBRID_DIR = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path.insert(0, str(HYBRID_DIR))

from context_compression import ContextCompressor  # noqa: E402


def build_contexts() -> list[dict]:
    critical_fields = [
        "SERVICE=ai-hybrid-coordinator",
        "PORT=8003",
        "API_KEY_FILE=/run/secrets/hybrid_coordinator_api_key",
    ]
    base = (
        "Configure the service declaratively. "
        "This fix improves reliability and reduces timeout risk. "
        "Run validation checks and confirm healthy status. "
    )
    contexts = []
    for i in range(12):
        marker = " ".join(critical_fields) if i == 0 else f"NOTE=aux-{i}"
        text = f"{marker}. " + (base * 40)
        contexts.append({"id": f"ctx-{i}", "text": text, "score": 1.0 - (i * 0.03)})
    return contexts


def main() -> int:
    compressor = ContextCompressor()
    contexts = build_contexts()
    raw_tokens = sum(compressor.estimate_tokens(ctx["text"]) for ctx in contexts)
    compressed_text, included_ids, compressed_tokens = compressor.compress_to_budget(
        contexts=contexts,
        max_tokens=600,
        strategy="hybrid",
    )
    ratio = raw_tokens / max(compressed_tokens, 1)

    missing = [
        "SERVICE=ai-hybrid-coordinator",
        "PORT=8003",
        "API_KEY_FILE=/run/secrets/hybrid_coordinator_api_key",
    ]
    missing = [field for field in missing if field not in compressed_text]

    print(
        f"compression_validation raw_tokens={raw_tokens} "
        f"compressed_tokens={compressed_tokens} ratio={ratio:.2f} "
        f"contexts_used={len(included_ids)}"
    )

    if ratio < 3.0:
        print("FAIL: compression ratio below 3:1 target", file=sys.stderr)
        return 1
    if missing:
        print(f"FAIL: missing critical fields after compression: {missing}", file=sys.stderr)
        return 1

    print("PASS: compression ratio >= 3:1 and critical fields preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
