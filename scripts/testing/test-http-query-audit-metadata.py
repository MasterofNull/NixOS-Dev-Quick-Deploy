#!/usr/bin/env python3
"""Static regression checks for HTTP query audit metadata propagation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = HTTP_SERVER.read_text(encoding="utf-8")

    assert_true(
        '"generate_response": generate_response' in text,
        "query audit metadata should propagate generate_response into tool-audit rows",
    )
    assert_true(
        '"backend": "unknown"' in text,
        "query audit metadata should seed a backend field before route_search runs",
    )
    assert_true(
        'audit_metadata["backend"] = "local" if prefer_local else "remote"' in text,
        "query error path should classify failed requests with a bounded backend label",
    )
    assert_true(
        'request["audit_metadata"]["prompt_cache_cached_tokens"] = cached_tokens' in text,
        "query audit metadata should propagate prompt-cache sample counts into tool-audit rows",
    )
    assert_true(
        'request["audit_metadata"]["task_complexity_tokens"] = task_complexity_tokens' in text,
        "query audit metadata should propagate task complexity token estimates into tool-audit rows",
    )
    assert_true(
        'request["audit_metadata"]["task_complexity_local_suitable"] = bool(' in text,
        "query audit metadata should propagate local suitability into tool-audit rows",
    )
    assert_true(
        'request["audit_metadata"]["task_complexity_remote_required"] = bool(' in text,
        "query audit metadata should propagate remote-required flags into tool-audit rows",
    )

    print("PASS: HTTP query audit metadata propagation is covered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
