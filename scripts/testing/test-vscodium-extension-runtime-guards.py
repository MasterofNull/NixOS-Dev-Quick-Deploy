#!/usr/bin/env python3
"""Static regression checks for VSCodium runtime-extension guardrails."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_NIX = REPO_ROOT / "nix" / "home" / "base.nix"
SERVICE_ENDPOINTS = REPO_ROOT / "config" / "service-endpoints.sh"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    base_text = BASE_NIX.read_text(encoding="utf-8")
    endpoint_text = SERVICE_ENDPOINTS.read_text(encoding="utf-8")

    assert_true(
        '"qwenlm.qwen-code-vscode-ide-companion"' in base_text,
        "Qwen companion should be managed through the mutable runtime extension path",
    )
    assert_true(
        "++ [qwenCodeCompanion]" not in base_text and "qwenCodeCompanion =" not in base_text,
        "stale immutable Qwen extension pin should be removed",
    )
    assert_true(
        'alias_name = f"{ident.lower()}-{version}"' in base_text,
        "activation should create versioned compatibility aliases for registry-managed extensions",
    )
    assert_true(
        "Pruning heavy Qwen global state" in base_text
        and "def prune_qwen(data):" in base_text
        and '("qwenlm.qwen-code-vscode-ide-companion", prune_qwen)' in base_text,
        "repair path should prune oversized Qwen startup state",
    )
    assert_true(
        "Archiving oversized Continue sessions" in base_text
        and "state_5.sqlite.pre-vscodium-repair" in base_text,
        "repair path should archive oversized Continue sessions and back up broken Codex state DBs",
    )
    # Gemini CodeAssist and its companion were retired in 3c14a843816e.
    assert_true(
        "geminicodeassist" not in base_text.lower() and "prune_gemini" not in base_text,
        "retired Gemini CodeAssist extension state handling should stay removed",
    )
    assert_true(
        "openai.chatgpt-" in base_text
        and "anthropic.claude-code-" in base_text,
        "repair path should clear stale obsolete markers for Codex and Claude AI extensions",
    )
    assert_true(
        'HYBRID_HOST="${HYBRID_HOST:-127.0.0.1}"' in endpoint_text,
        "service endpoint defaults should prefer numeric loopback for the harness",
    )

    print("PASS: VSCodium runtime extension guardrails are configured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
