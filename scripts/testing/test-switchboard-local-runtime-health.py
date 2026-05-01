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
        '"local_runtime": local_runtime' in text,
        "expected switchboard health payload to expose local_runtime",
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

    print("PASS: switchboard health exposes local runtime slot occupancy")


if __name__ == "__main__":
    main()
