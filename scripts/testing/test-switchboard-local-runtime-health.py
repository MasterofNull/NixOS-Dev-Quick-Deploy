#!/usr/bin/env python3
"""Static regression checks for switchboard local runtime health surfacing."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SWITCHBOARD_NIX = REPO_ROOT / "nix/modules/services/switchboard.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = SWITCHBOARD_NIX.read_text(encoding="utf-8")

    assert_true(
        "local_runtime = await _local_runtime_health_snapshot()" in text,
        "expected switchboard /health to include a local runtime snapshot",
    )
    assert_true(
        "local_lane_status = _local_lane_status(local_runtime)" in text,
        "expected switchboard /health to derive a canonical local lane status",
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
        '"cache_prompt": True' in text
        and '"Diagnose why the local editor path is slow and return 3 compact next steps."' in text
        and "_apply_compact_guidance_contract(messages, profile)" in text
        and '"messages": _startup_prefix_warm_messages(profile)' in text,
        "expected startup prefix warmup to seed llama.cpp cache with a representative compact local editor prompt",
    )
    assert_true(
        "def _local_lane_status(local_runtime: dict | None) -> str:" in text,
        "expected switchboard to define a canonical local lane status helper",
    )
    assert_true(
        '"busy-long-running"' in text,
        "expected canonical local lane status helper to distinguish long-running busy state",
    )
    assert_true(
        "_clear_local_active_request(local_active_request_id)" in text,
        "expected switchboard to clear tracked local request metadata after completion",
    )

    print("PASS: switchboard health exposes local runtime slot occupancy")


if __name__ == "__main__":
    main()
