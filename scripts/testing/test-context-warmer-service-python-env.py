#!/usr/bin/env python3
"""Static regression checks for ai-context-warmer Python runtime wiring."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_PATH = REPO_ROOT / "nix/modules/roles/ai-stack.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = ROLE_PATH.read_text(encoding="utf-8")

    assert_true(
        "worldModelPython = pkgs.python3.withPackages" in text,
        "expected ai-stack role to define a dedicated world-model Python runtime",
    )
    for dep in ("httpx", "psycopg", "redis"):
        assert_true(
            dep in text,
            f"expected worldModelPython to include dependency {dep}",
        )
    assert_true(
        '"PYTHON_BIN=${worldModelPython}/bin/python3"' in text,
        "expected ai-context-warmer service to inject PYTHON_BIN from worldModelPython",
    )
    assert_true(
        "ExecStart = \"${pkgs.bash}/bin/bash ${cfg.mcpServers.repoPath}/scripts/ai/aq-context-warm\"" in text,
        "expected ai-context-warmer to run aq-context-warm directly",
    )
    assert_true(
        "aq-ralph-task" not in text[text.index("systemd.services.ai-context-warmer"):text.index("systemd.timers.ai-context-warmer")],
        "ai-context-warmer must not enqueue local-agent Ralph tasks",
    )
    assert_true(
        '"DATA_DIR=${cfg.mcpServers.dataDir}/hybrid"' in text,
        "expected ai-context-warmer to write telemetry under the MCP data dir",
    )
    assert_true(
        '"COORDINATOR_URL=http://127.0.0.1:${toString cfg.mcpServers.hybridPort}"' in text,
        "expected ai-context-warmer to target the local hybrid coordinator",
    )
    assert_true(
        '"HYBRID_COORDINATOR_API_KEY_FILE=/run/secrets/hybrid_coordinator_api_key"' in text,
        "expected ai-context-warmer to use the hybrid coordinator API key file",
    )
    assert_true(
        "ReadWritePaths = [\n            cfg.mcpServers.dataDir\n          ];" in text,
        "expected ai-context-warmer to permit telemetry writes under mcpServers.dataDir",
    )

    print("PASS: ai-context-warmer service injects a Python runtime with world-model deps")


if __name__ == "__main__":
    main()
