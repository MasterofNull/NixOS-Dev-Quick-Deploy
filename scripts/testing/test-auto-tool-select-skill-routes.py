#!/usr/bin/env python3
"""Static regression for auto-tool-select skill route handlers."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HANDLERS = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "auto_tool_select_handlers.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = HANDLERS.read_text(encoding="utf-8")

    assert_true(
        'app.router.add_get("/skills/list", handle_skills_list)' in text,
        "auto-tool-select routes should expose /skills/list",
    )
    assert_true(
        'app.router.add_get(r"/skills/{slug}/content", handle_skill_content)' in text,
        "auto-tool-select routes should expose /skills/{slug}/content",
    )
    assert_true(
        "async def handle_skills_list(request: Any) -> Any:" in text,
        "auto-tool-select routes should define a list handler for registered skill routes",
    )
    assert_true(
        "async def handle_skill_content(request: Any) -> Any:" in text,
        "auto-tool-select routes should define a content handler for registered skill routes",
    )
    assert_true(
        "def _list_local_skills() -> List[Dict[str, Any]]:" in text
        and "async def _fetch_remote_skills(limit: int = 50) -> Dict[str, Any]:" in text,
        "skill listing should merge local filesystem skills with approved remote catalog entries",
    )

    print("PASS: auto-tool-select skill routes are backed by real handlers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
