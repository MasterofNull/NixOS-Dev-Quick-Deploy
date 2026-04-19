#!/usr/bin/env python3
"""Static regression for harness workflow CLI and local orchestrator controls."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARNESS_RPC = ROOT / "scripts" / "ai" / "harness-rpc.js"
MCP_CLIENT = ROOT / "ai-stack" / "local-orchestrator" / "mcp_client.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    harness_text = HARNESS_RPC.read_text(encoding="utf-8")
    client_text = MCP_CLIENT.read_text(encoding="utf-8")

    assert_true(
        "function buildOrchestrationPolicy(args)" in harness_text,
        "harness-rpc.js should build workflow orchestration policy overrides",
    )
    assert_true(
        'blueprint_id: args.blueprint || args["blueprint-id"] || ""' in harness_text,
        "harness-rpc.js run-start should forward blueprint ids",
    )
    assert_true(
        'isolation_profile: args["isolation-profile"] || ""' in harness_text
        and 'workspace_root: args["workspace-root"] || ""' in harness_text
        and 'network_policy: args["network-policy"] || ""' in harness_text,
        "harness-rpc.js should forward isolation controls",
    )
    assert_true(
        "orchestration_policy: orchestrationPolicy" in harness_text,
        "harness-rpc.js should forward workflow orchestration policy overrides",
    )
    assert_true(
        "blueprint_id: Optional[str] = None" in client_text,
        "local orchestrator client should accept blueprint_id",
    )
    assert_true(
        "orchestration_policy: Optional[Dict[str, Any]] = None" in client_text,
        "local orchestrator client should accept orchestration_policy",
    )
    assert_true(
        '"blueprint_id": blueprint_id or ""' in client_text
        and '"orchestration_policy": orchestration_policy' in client_text,
        "local orchestrator client should forward blueprint and policy controls",
    )
    assert_true(
        '"isolation_profile": isolation_profile or ""' in client_text
        and '"workspace_root": workspace_root or ""' in client_text
        and '"network_policy": network_policy or ""' in client_text,
        "local orchestrator client should forward isolation controls",
    )

    print("PASS: harness workflow controls expose blueprint, isolation, and team-policy overrides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
