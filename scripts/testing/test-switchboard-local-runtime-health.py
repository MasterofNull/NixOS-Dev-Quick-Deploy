#!/usr/bin/env python3
"""Hermetic regression checks for switchboard local runtime health surfacing."""

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SWITCHBOARD_SOURCE = REPO_ROOT / "ai-stack/switchboard/switchboard.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_switchboard():
    spec = importlib.util.spec_from_file_location("switchboard_a4_test", SWITCHBOARD_SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _BreakerStates:
    def __init__(self, llama: dict) -> None:
        self._llama = llama

    def get_all_states(self) -> dict:
        return {"llama": self._llama}


def test_fail_closed_local_lane_health() -> None:
    switchboard = _load_switchboard()
    original_breakers = switchboard.LOCAL_CIRCUIT_BREAKERS
    try:
        switchboard.LOCAL_CIRCUIT_BREAKERS = _BreakerStates(
            {"state": "closed", "failure_count": 1, "success_count": 0}
        )
        health, reason, evidence = switchboard._local_lane_health(
            {
                "slot_available": 1,
                "last_completion": {
                    "status_code": 503,
                    "age_s": 0.0,
                    "path": "chat/completions",
                    "profile": "continue-local",
                },
            }
        )
        assert_true(
            (health, reason) == ("degraded", "fresh_local_completion_failed"),
            "a fresh 503 must override available slot capacity",
        )
        assert_true(
            evidence["breaker"]["failure_count"] == 1
            and evidence["last_completion"]["status_code"] == 503,
            "a degraded result must retain bounded breaker and completion evidence",
        )

        switchboard.LOCAL_CIRCUIT_BREAKERS = _BreakerStates(
            {"state": "open", "failure_count": 5, "success_count": 0}
        )
        assert_true(
            switchboard._local_lane_health({"slot_available": 1})[:2]
            == ("unavailable", "local_breaker_open"),
            "an open llama breaker must be unavailable even with a free slot",
        )

        switchboard.LOCAL_CIRCUIT_BREAKERS = _BreakerStates(
            {"state": "closed", "failure_count": 0, "success_count": 1}
        )
        assert_true(
            switchboard._local_lane_health({
                "slot_available": 1,
                "last_completion": {"status_code": 200, "age_s": 0.0},
            })[:2]
            == ("available", "local_slot_available"),
            "a fresh successful completion, closed breaker, and capacity may be available",
        )
        assert_true(
            switchboard._local_lane_health({"slot_available": 1})[:2]
            == ("unknown", "local_completion_unproven"),
            "slot capacity alone must not prove usable inference",
        )
        assert_true(
            switchboard._local_lane_health(None)[:2]
            == ("unknown", "local_runtime_unknown"),
            "missing runtime evidence must remain unknown rather than available",
        )
        assert_true(
            switchboard._local_lane_health({
                "slot_available": 1,
                "last_completion": {"status_code": "invalid", "age_s": -1},
            })[:2] == ("degraded", "invalid_local_completion_evidence"),
            "malformed completion evidence must degrade rather than crash /health",
        )
        for invalid in (
            {"status_code": -1, "age_s": 0},
            {"status_code": 200, "age_s": float("nan")},
            {"status_code": 200, "age_s": -1},
        ):
            assert_true(
                switchboard._local_lane_health({
                    "slot_available": 1, "last_completion": invalid,
                })[:2] == ("degraded", "invalid_local_completion_evidence"),
                f"invalid completion evidence was accepted: {invalid}",
            )
        assert_true(
            switchboard._local_lane_health({
                "slot_available": 1,
                "last_completion": {
                    "status_code": 200,
                    "age_s": switchboard.LOCAL_BUSY_WARN_S + 1,
                },
            })[:2] == ("unknown", "local_completion_stale"),
            "stale completion evidence must not prove availability",
        )
        switchboard.LOCAL_CIRCUIT_BREAKERS = _BreakerStates(
            {"state": "closed", "failure_count": "invalid", "success_count": 0}
        )
        assert_true(
            switchboard._local_lane_health({"slot_available": 1})[:2]
            == ("degraded", "invalid_local_breaker_evidence"),
            "malformed breaker evidence must degrade rather than crash /health",
        )
    finally:
        switchboard.LOCAL_CIRCUIT_BREAKERS = original_breakers


def main() -> None:
    text = SWITCHBOARD_SOURCE.read_text(encoding="utf-8")

    assert_true(
        "local_runtime = await _local_runtime_health_snapshot()" in text,
        "expected switchboard /health to include a local runtime snapshot",
    )
    assert_true(
        "local_lane_runtime_status = _local_lane_status(local_runtime)" in text
        and "local_lane_status = local_lane_health" in text,
        "expected /health compatibility status to use the fail-closed health verdict",
    )
    assert_true(
        '"local_runtime": local_runtime' in text,
        "expected switchboard health payload to expose local_runtime",
    )
    assert_true(
        '"local_lane_status": local_lane_status' in text,
        "expected switchboard health payload to expose the canonical local lane status",
    )
    assert_true(
        "async def _local_runtime_health_snapshot() -> dict:" in text,
        "expected switchboard to define a local runtime health snapshot helper",
    )
    assert_true(
        '_parse_prometheus_gauge(metrics_text, "llamacpp:requests_processing")' in text,
        "expected local runtime health to parse llama requests_processing metric",
    )
    assert_true(
        '"slot_capacity": local_slot_capacity' in text
        and '"slot_available": local_slot_available' in text
        and '"slot_busy": local_slot_busy' in text,
        "expected local runtime health to expose slot capacity/availability/busy fields",
    )
    assert_true(
        'snapshot["source"] = "switchboard_semaphore+llama_metrics"' in text,
        "expected local runtime health to mark combined semaphore+metric saturation source",
    )
    assert_true(
        'snapshot["llama_metrics_error"] = f"{type(exc).__name__}: {exc}"' in text,
        "expected local runtime health to surface non-HTTP metrics probe failures explicitly",
    )
    assert_true(
        'snapshot["active_request"] = active_request' in text,
        "expected local runtime health to expose active local request metadata when available",
    )
    assert_true(
        "def _begin_local_active_request(path: str, profile: str, payload: dict | None, is_stream: bool) -> str:" in text,
        "expected switchboard to define a helper that tracks in-flight local request metadata",
    )
    assert_true(
        '"latest_user_excerpt"' in text and '"estimated_input_tokens"' in text,
        "expected active local request metadata to include request attribution and size signals",
    )
    assert_true(
        '"long_running"' in text and "LOCAL_BUSY_WARN_S" in text,
        "expected active local request metadata to flag long-running slot occupancy",
    )
    assert_true(
        "def _record_local_completion(path: str, profile: str, status_code: int, body: bytes | None) -> None:" in text,
        "expected switchboard to define a helper that stores the last local completion snapshot",
    )
    assert_true(
        "def _local_last_completion_snapshot() -> dict | None:" in text,
        "expected switchboard to define a helper that exposes the last local completion snapshot",
    )
    assert_true(
        'snapshot["last_completion"] = last_completion' in text,
        "expected local runtime health to expose the last local completion snapshot",
    )
    assert_true(
        '_record_local_completion(path, profile, upstream.status_code, upstream.content)' in text,
        "expected successful local chat completions to refresh the last completion snapshot",
    )
    assert_true(
        '"prompt_tokens_details"' in text and '"timings"' in text,
        "expected local completion snapshot to preserve cached token and timing fields",
    )
    assert_true(
        "STARTUP_PREFIX_WARM_ENABLED" in text,
        "expected switchboard to expose a startup prefix warmup toggle",
    )
    assert_true(
        "async def _warm_local_profile_prefix(profile: str) -> None:" in text,
        "expected switchboard to define a startup prefix warmup helper",
    )
    assert_true(
        "def _startup_prefix_warm_messages(profile: str) -> list[dict]:" in text,
        "expected switchboard to define a representative startup warmup message helper",
    )
    assert_true(
        'asyncio.create_task(_warm_local_profile_prefix("continue-local"))' in text,
        "expected switchboard startup to schedule continue-local prefix warmup",
    )
    assert_true(
        "cache_prompt=True" in text
        and '"Diagnose why the local editor path is slow and return 3 compact next steps."' in text
        and "_apply_compact_guidance_contract(messages, profile)" in text
        and "_startup_prefix_warm_messages(profile)," in text,
        "expected startup prefix warmup to seed llama.cpp cache with a representative compact local editor prompt",
    )
    assert_true(
        "def _local_lane_status(local_runtime: dict | None) -> str:" in text,
        "expected switchboard to define a canonical local lane status helper",
    )
    assert_true(
        "def _local_lane_health(local_runtime: dict | None)" in text
        and '"fresh_local_completion_failed"' in text
        and '"local_breaker_failures_without_success"' in text
        and '"local_breaker_open"' in text,
        "expected fail-closed local lane health reasons from fresh completion and breaker evidence",
    )
    assert_true(
        '"local_lane_health": local_lane_health' in text
        and '"local_lane_reason": local_lane_reason' in text
        and '"local_lane_evidence": local_lane_evidence' in text
        and '"local_lane_runtime_status": local_lane_runtime_status' in text,
        "expected switchboard /health to expose local lane health reason and evidence",
    )
    assert_true(
        '"busy-long-running"' in text,
        "expected canonical local lane status helper to distinguish long-running busy state",
    )
    assert_true(
        "_clear_local_active_request(local_active_request_id)" in text,
        "expected switchboard to clear tracked local request metadata after completion",
    )

    test_fail_closed_local_lane_health()

    print("PASS: switchboard health exposes local runtime slot occupancy")


if __name__ == "__main__":
    main()
