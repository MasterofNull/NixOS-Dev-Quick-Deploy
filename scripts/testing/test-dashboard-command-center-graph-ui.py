#!/usr/bin/env python3
"""Static regression checks for command-center graph UI wiring."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_HTML = ROOT / "dashboard.html"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert_true(
        'id="commandCenterGraphConfig"' in text,
        "expected command-center graph panel in dashboard configuration section",
    )
    assert_true(
        'async function renderCommandCenterGraphSurfaces(snapshot)' in text,
        "expected dashboard graph surface renderer",
    )
    assert_true(
        'summarizeGraphSurfacePayload(surface, payload)' in text,
        "expected dashboard graph payload summarizer",
    )
    assert_true(
        'void renderCommandCenterGraphSurfaces(snapshot);' in text,
        "expected control-plane render path to load graph surfaces",
    )

    print("PASS: dashboard command-center graph UI wiring is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
