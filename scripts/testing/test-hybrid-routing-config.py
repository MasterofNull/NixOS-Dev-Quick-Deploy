#!/usr/bin/env python3
"""Static regression checks for hybrid local-routing defaults."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MCP_MODULE = ROOT / "nix" / "modules" / "services" / "mcp-servers.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = MCP_MODULE.read_text(encoding="utf-8")
    assert_true(
        '"LOCAL_CONFIDENCE_THRESHOLD=0.35"' in text,
        "hybrid coordinator should set a lower local confidence threshold declaratively",
    )
    assert_true(
        '"SWITCHBOARD_URL=http://127.0.0.1:${toString ports.switchboard}"' in text,
        "hybrid coordinator should continue to use declarative switchboard wiring",
    )
    print("PASS: hybrid routing declarative defaults present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
