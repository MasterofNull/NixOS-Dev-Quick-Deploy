#!/usr/bin/env python3
"""
Phase 171: Local inference throughput calibration check.

Verifies that LOCAL_TOK_PER_SEC in llm_config.py is within 50% of the
throughput reported by llama.cpp /metrics. Catches budget constant drift
before it causes 504 timeouts.

Exits 0 on PASS or SKIP (llama.cpp unreachable at test time).
Exits 1 on FAIL (drift > 50% — budget math is materially wrong).
"""
import sys
import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "ai-stack" / "mcp-servers"))

LLAMA_URL = os.environ.get("LLAMA_CPP_URL", "http://127.0.0.1:8080").rstrip("/")
DRIFT_THRESHOLD = 0.50  # 50% tolerance — fail if measured is <50% or >150% of constant


def _get_measured_tps() -> float | None:
    """Read llamacpp:predicted_tokens_seconds from Prometheus /metrics."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{LLAMA_URL}/metrics", timeout=5) as resp:
            text = resp.read().decode()
        for line in text.splitlines():
            if line.startswith("llamacpp:predicted_tokens_seconds"):
                parts = line.split()
                if len(parts) >= 2:
                    return float(parts[-1])
    except Exception:
        pass
    return None


def main() -> int:
    try:
        from shared.llm_config import LOCAL_TOK_PER_SEC
    except ImportError as e:
        print(f"FAIL: cannot import LOCAL_TOK_PER_SEC from shared.llm_config: {e}")
        return 1

    measured = _get_measured_tps()
    if measured is None:
        print(f"SKIP: llama.cpp at {LLAMA_URL} unreachable or /metrics unavailable — skipping throughput calibration")
        return 0

    if measured == 0.0:
        print("SKIP: llamacpp:predicted_tokens_seconds = 0 (no inference has run yet) — skipping throughput calibration")
        return 0

    drift = abs(measured - LOCAL_TOK_PER_SEC) / LOCAL_TOK_PER_SEC
    if drift > DRIFT_THRESHOLD:
        print(
            f"FAIL: throughput drift {drift:.0%} exceeds {DRIFT_THRESHOLD:.0%} threshold.\n"
            f"  Measured: {measured:.2f} tok/s\n"
            f"  Constant: LOCAL_TOK_PER_SEC = {LOCAL_TOK_PER_SEC:.2f} tok/s\n"
            f"  Action: update LOCAL_TOK_PER_SEC in ai-stack/mcp-servers/shared/llm_config.py"
        )
        return 1

    print(
        f"PASS: throughput calibrated — measured {measured:.2f} tok/s, "
        f"constant {LOCAL_TOK_PER_SEC:.2f} tok/s (drift {drift:.0%} ≤ {DRIFT_THRESHOLD:.0%})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
