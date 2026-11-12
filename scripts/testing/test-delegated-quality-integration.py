#!/usr/bin/env python3
"""Static regression checks for delegated response quality integration."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server_impl.py"


# Explicit live owners of the asserted behavior; coordinator_source() fails if http_server_impl.py
# (first entry) does not reference an owner module, so dormant files cannot satisfy assertions.
COORDINATOR_OWNERS = (
    "http_server_impl.py",
    "extensions/ai_coordinator_handlers.py",
    "workflow/delegation_handlers.py",
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
        "from quality_assurance import QualityChecker, QualityThreshold, ResultCache, ResultRefiner, QualityTrendTracker" in text,
        "hybrid coordinator should import delegated quality assurance primitives",
    )
    assert_true(
        "_DELEGATED_QUALITY_CHECKER = QualityChecker(threshold=QualityThreshold.PERMISSIVE)" in text,
        "hybrid coordinator should initialize a delegated quality checker",
    )
    assert_true(
        "def _assess_delegated_response_quality(" in text,
        "hybrid coordinator should define delegated quality assessment helper",
    )
    assert_true(
        '_DELEGATED_RESULT_CACHE.set(task, selected_text, quality_check.score)' in text,
        "delegated quality flow should cache passing responses",
    )
    assert_true(
        '_DELEGATED_QUALITY_TRACKER.record_quality(agent_id, quality_check.score.overall)' in text,
        "delegated quality flow should track per-agent quality trends",
    )
    assert_true(
        '"delegated_quality_assurance": _delegated_quality_status_snapshot()' in text,
        "status endpoint should expose delegated quality assurance state",
    )
    assert_true(
        'delegated_quality = await _assess_delegated_response_quality(' in text,
        "delegate handler should assess successful delegated responses",
    )
    assert_true(
        'body = _inject_delegated_response_text(body, updated_text)' in text,
        "delegate handler should inject refined or cached response text back into payloads",
    )
    assert_true(
        'local_fallback_needed = (' in text,
        "delegate handler should decide when failed remote calls need bounded local fallback",
    )
    assert_true(
        "local_profile = _ai_coordinator_local_fallback_profile(" in text
        and 'tools_present=isinstance(payload.get("tools"), list) and len(payload.get("tools") or []) > 0' in text
        and 'if tools_present or normalized == "local-tool-calling":\n        return "local-tool-calling"'
        in (ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "extensions" / "ai_coordinator.py").read_text(encoding="utf-8"),
        "delegate handler should select an appropriate local fallback profile (call site in handler, tool-calling rule in ai_coordinator.py)",
    )
    assert_true(
        'stage="local_fallback"' in text,
        "delegate handler should classify bounded local fallback attempts explicitly",
    )
    assert_true(
        '"local_fallback_applied": local_fallback_applied' in text,
        "delegate audit metadata should record local fallback activation",
    )
    assert_true(
        '"quality_assurance": delegated_quality' in text,
        "delegate response should surface quality assurance metadata",
    )

    print("PASS: delegated response quality assurance is integrated into routing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
