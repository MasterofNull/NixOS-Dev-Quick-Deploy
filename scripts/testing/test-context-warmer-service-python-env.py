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

    print("PASS: ai-context-warmer service injects a Python runtime with world-model deps")


if __name__ == "__main__":
    main()
