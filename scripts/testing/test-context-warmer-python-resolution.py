#!/usr/bin/env python3
"""Static regression checks for aq-context-warm Python resolution."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts/ai/aq-context-warm"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert_true(
        'PYTHON_BIN="${PYTHON_BIN:-}"' in text,
        "expected aq-context-warm to honor PYTHON_BIN override",
    )
    assert_true(
        'command -v python3 >/dev/null 2>&1' in text,
        "expected aq-context-warm to try PATH python3 first",
    )
    assert_true(
        'elif [[ -x /run/current-system/sw/bin/python3 ]]; then' in text,
        "expected aq-context-warm to fall back to the system profile python3 under systemd",
    )
    assert_true(
        'exec "${PYTHON_BIN}" - "$@"' in text,
        "expected aq-context-warm to exec the resolved Python interpreter",
    )
    assert_true(
        "export REPO_ROOT" in text and 'repo_root = os.environ["REPO_ROOT"]' in text,
        "expected aq-context-warm to pass repo root through the environment for stdin execution",
    )

    print("PASS: aq-context-warm resolves python3 robustly for systemd and shell use")


if __name__ == "__main__":
    main()
