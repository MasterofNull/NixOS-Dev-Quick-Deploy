#!/usr/bin/env python3
"""Regression checks for delegate-to-antigravity background child stdio handling."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ai" / "delegate-to-antigravity"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = SCRIPT.read_text()

    assert_true(
        "def _redirect_background_stdio(log_path: Path)" in text,
        "expected a shared background stdio redirection helper",
    )
    assert_true(
        "os.dup2(stdin_fd, sys.stdin.fileno())" in text,
        "expected background child stdin to detach from caller",
    )
    assert_true(
        "os.dup2(log_fd, sys.stdout.fileno())" in text,
        "expected background child stdout to be redirected to the task log",
    )
    assert_true(
        "os.dup2(log_fd, sys.stderr.fileno())" in text,
        "expected background child stderr to be redirected to the task log",
    )
    assert_true(
        text.count("_redirect_background_stdio(log_path)") >= 2,
        "expected both background dispatch paths to redirect stdio",
    )
    assert_true(
        "json.dumps(result)" not in text,
        "empty switchboard response path must not reference undefined result",
    )

    print("PASS delegate-to-antigravity background stdio regression")


if __name__ == "__main__":
    main()
