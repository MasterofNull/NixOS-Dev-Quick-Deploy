#!/usr/bin/env python3
"""Static regression checks for HTTP query audit metadata propagation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server_impl.py"


# Explicit live owners of the asserted behavior; coordinator_source() fails if http_server_impl.py
# (first entry) does not reference an owner module, so dormant files cannot satisfy assertions.
COORDINATOR_OWNERS = (
    "http_server_impl.py",
)


def coordinator_source() -> str:
    root = Path(__file__).resolve().parents[2] / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
    http_text = (root / COORDINATOR_OWNERS[0]).read_text(encoding="utf-8")
    for owner in COORDINATOR_OWNERS[1:]:
        if Path(owner).stem not in http_text:
            raise AssertionError(f"{owner} is not referenced by {COORDINATOR_OWNERS[0]}; owner is not wired")
    return "\n".join((root / owner).read_text(encoding="utf-8") for owner in COORDINATOR_OWNERS)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = coordinator_source()

    assert_true(
        "def _collect_query_audit(request, result" in text
        and "_collect_query_audit(request, result" in text.split("def _collect_query_audit(request, result", 1)[1],
        "query handler should call the result-derived audit collector",
    )
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
        'audit["prompt_cache_cached_tokens"] = cached_tokens' in text,
        "query audit metadata should propagate prompt-cache sample counts into tool-audit rows",
    )
    assert_true(
        'audit["task_complexity_tokens"] = tc_tokens' in text,
        "query audit metadata should propagate task complexity token estimates into tool-audit rows",
    )
    assert_true(
        'for flag in ("local_suitable", "remote_required"):' in text,
        "query audit metadata should propagate local suitability into tool-audit rows",
    )
    assert_true(
        'audit[f"task_complexity_{flag}"] = bool(task_complexity.get(flag))' in text,
        "query audit metadata should propagate remote-required flags into tool-audit rows",
    )
    assert_true(
        'audit["strategy_tag"] = str(result.get("route", "unknown"))' in text,
        "query audit metadata should propagate strategy_tag into tool-audit rows",
    )
    assert_true(
        '("local_inference_lane", "local_inference_lane"),' in text,
        "query audit metadata should propagate the selected local inference lane into tool-audit rows",
    )
    assert_true(
        '("local_inference_lane_reason", "local_inference_lane_reason"),' in text,
        "query audit metadata should propagate the local inference lane reason into tool-audit rows",
    )

    print("PASS: HTTP query audit metadata propagation is covered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
