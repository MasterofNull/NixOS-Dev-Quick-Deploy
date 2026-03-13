#!/usr/bin/env python3
"""Targeted checks for ai-coordinator default runtime lanes."""

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from ai_coordinator import default_runtime_id_for_profile, infer_profile, merge_runtime_defaults  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    merged = merge_runtime_defaults({"runtimes": {}})
    runtime_ids = set((merged.get("runtimes", {}) or {}).keys())
    assert_true("local-hybrid" in runtime_ids, "local-hybrid default missing")
    assert_true("openrouter-free" in runtime_ids, "openrouter-free default missing")
    assert_true("openrouter-coding" in runtime_ids, "openrouter-coding default missing")
    assert_true("openrouter-reasoning" in runtime_ids, "openrouter-reasoning default missing")

    assert_true(infer_profile("review architecture tradeoffs") == "remote-reasoning", "reasoning profile inference failed")
    assert_true(infer_profile("implement patch for service failure") == "remote-coding", "coding profile inference failed")
    assert_true(infer_profile("gather quick external context") == "remote-free", "free profile inference failed")
    assert_true(infer_profile("use the local lane", "continue-local") == "default", "continue-local should map to default lane")

    refreshed = merge_runtime_defaults(
        {
            "runtimes": {
                "local-hybrid": {
                    "runtime_id": "local-hybrid",
                    "name": "stale-name",
                    "source": "ai-coordinator-default",
                    "created_at": 123,
                }
            }
        }
    )
    local_runtime = refreshed["runtimes"]["local-hybrid"]
    assert_true(local_runtime["name"] == "Local Hybrid Coordinator", "default runtime record did not refresh")
    assert_true(local_runtime["created_at"] == 123, "refresh should preserve created_at")

    assert_true(default_runtime_id_for_profile("remote-free") == "openrouter-free", "free runtime mapping failed")
    assert_true(default_runtime_id_for_profile("remote-coding") == "openrouter-coding", "coding runtime mapping failed")
    assert_true(default_runtime_id_for_profile("remote-reasoning") == "openrouter-reasoning", "reasoning runtime mapping failed")
    assert_true(default_runtime_id_for_profile("continue-local") == "local-hybrid", "continue-local runtime mapping failed")

    print("PASS: ai-coordinator exposes default local/OpenRouter runtime lanes and profile inference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
