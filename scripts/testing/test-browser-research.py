#!/usr/bin/env python3
"""Checks for the bounded browser-assisted research lane."""

import asyncio
import os
import sys
import types
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_BROWSER_RESEARCH_ENABLED", "true")
os.environ.setdefault("AI_BROWSER_RESEARCH_MAX_URLS", "1")
os.environ.setdefault("AI_BROWSER_RESEARCH_MAX_SELECTORS", "4")
os.environ.setdefault("AI_BROWSER_RESEARCH_TIMEOUT_SECONDS", "5")
os.environ.setdefault("AI_BROWSER_RESEARCH_PER_HOST_DELAY_SECONDS", "0.1")
os.environ.setdefault("AI_BROWSER_RESEARCH_MAX_TEXT_CHARS", "400")
os.environ.setdefault("AI_BROWSER_RESEARCH_MAX_LINKS", "5")
os.environ.setdefault("AI_BROWSER_RESEARCH_MAX_REDIRECTS", "1")
os.environ.setdefault("AI_BROWSER_RESEARCH_CHROMIUM_BIN", "chromium")
os.environ.setdefault("AI_BROWSER_RESEARCH_VIRTUAL_TIME_BUDGET_MS", "4000")
if "structlog" not in sys.modules:
    sys.modules["structlog"] = types.SimpleNamespace(
        get_logger=lambda: types.SimpleNamespace(debug=lambda *a, **k: None, warning=lambda *a, **k: None)
    )
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from browser_research import fetch_browser_research  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> int:
    request_log = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_log.append(str(request.url))
        if str(request.url) == "https://example.com/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n", headers={"content-type": "text/plain"})
        return httpx.Response(404, text="not found", headers={"content-type": "text/plain"})

    async def browser_runner(**kwargs):
        url = kwargs["url"]
        if url == "https://example.com/page":
            return (
                0,
                "<html><head><title>Rendered Example</title></head><body><main>Rendered native plant data <a href='/plants/oak'>Oak</a></main></body></html>",
                "",
            )
        if url == "https://example.com/challenge":
            return (
                0,
                "<html><head><title>Just a moment...</title></head><body><main>Enable JavaScript and cookies to continue</main></body></html>",
                "",
            )
        return (1, "", "failed")

    result = await fetch_browser_research(
        urls=["https://example.com/page"],
        selectors=["main"],
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _seconds: asyncio.sleep(0),
        browser_runner=browser_runner,
    )

    metrics = result.get("metrics", {})
    assert_true(metrics.get("accepted_urls") == 1, "accepted_urls mismatch")
    assert_true(metrics.get("robots_requests") == 1, "robots request missing")
    assert_true(metrics.get("browser_requests") == 1, "browser request missing")
    page = result["results"][0]
    assert_true(page["title"] == "Rendered Example", "browser title mismatch")
    assert_true("Rendered native plant data" in page["text_excerpt"], "rendered excerpt missing")
    assert_true(page["links"] == ["https://example.com/plants/oak"], "rendered links mismatch")

    challenge = await fetch_browser_research(
        urls=["https://example.com/challenge"],
        selectors=["main"],
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _seconds: asyncio.sleep(0),
        browser_runner=browser_runner,
    )
    assert_true(challenge["results"][0]["title"] == "Just a moment...", "challenge title mismatch")
    assert_true("https://example.com/robots.txt" in request_log, "robots precheck missing")

    print("PASS: browser research lane stays bounded and robots-aware")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
