#!/usr/bin/env python3
"""Static regression checks for AI-specific metrics instrumentation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
METRICS = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "metrics.py"
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    metrics_text = METRICS.read_text(encoding="utf-8")
    server_text = HTTP_SERVER.read_text(encoding="utf-8")

    for symbol in [
        "DELEGATED_PROMPT_TOKENS_BEFORE",
        "DELEGATED_PROMPT_TOKENS_AFTER",
        "DELEGATED_PROMPT_TOKEN_SAVINGS",
        "DELEGATED_QUALITY_SCORE",
        "DELEGATED_QUALITY_EVENTS",
        "PROGRESSIVE_CONTEXT_LOADS",
        "CAPABILITY_GAP_DETECTIONS",
        "REAL_TIME_LEARNING_EVENTS",
        "META_LEARNING_ADAPTATIONS",
    ]:
        assert_true(symbol in metrics_text, f"metrics.py should define {symbol}")
        assert_true(symbol in server_text, f"http_server.py should instrument {symbol}")

    assert_true(
        'DELEGATED_PROMPT_TOKEN_SAVINGS.labels(profile=effective_profile).inc(prompt_tokens_before - prompt_tokens_after)' in server_text,
        "server should record delegated prompt token savings",
    )
    assert_true(
        'DELEGATED_QUALITY_SCORE.labels(profile=effective_profile).observe(quality_value)' in server_text,
        "server should record delegated quality scores",
    )
    assert_true(
        'PROGRESSIVE_CONTEXT_LOADS.labels(' in server_text,
        "server should record progressive context loads",
    )
    assert_true(
        'CAPABILITY_GAP_DETECTIONS.labels(' in server_text,
        "server should record capability gap detections",
    )
    assert_true(
        'REAL_TIME_LEARNING_EVENTS.labels(profile=effective_profile, event_type="learning_example").inc()' in server_text,
        "server should record real-time learning events",
    )
    assert_true(
        'META_LEARNING_ADAPTATIONS.labels(' in server_text,
        "server should record meta-learning adaptations",
    )

    print("PASS: AI-specific delegated metrics are instrumented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
