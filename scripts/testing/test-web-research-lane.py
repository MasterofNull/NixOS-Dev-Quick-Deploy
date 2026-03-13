#!/usr/bin/env python3
"""Targeted checks for the bounded web research lane."""

import asyncio
import os
import sys
import types
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_WEB_RESEARCH_ENABLED", "true")
os.environ.setdefault("AI_WEB_RESEARCH_MAX_URLS", "3")
os.environ.setdefault("AI_WEB_RESEARCH_MAX_SELECTORS", "4")
os.environ.setdefault("AI_WEB_RESEARCH_TIMEOUT_SECONDS", "5")
os.environ.setdefault("AI_WEB_RESEARCH_PER_HOST_DELAY_SECONDS", "0.2")
os.environ.setdefault("AI_WEB_RESEARCH_MAX_RESPONSE_BYTES", "16384")
os.environ.setdefault("AI_WEB_RESEARCH_MAX_TEXT_CHARS", "400")
os.environ.setdefault("AI_WEB_RESEARCH_MAX_LINKS", "5")
os.environ.setdefault("AI_WEB_RESEARCH_MAX_REDIRECTS", "1")
if "structlog" not in sys.modules:
    sys.modules["structlog"] = types.SimpleNamespace(
        get_logger=lambda: types.SimpleNamespace(debug=lambda *a, **k: None, warning=lambda *a, **k: None)
    )
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from web_research import fetch_web_research  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> int:
    request_log = []
    sleep_calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_log.append(str(request.url))
        if str(request.url) == "https://example.com/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /blocked\n",
                headers={"content-type": "text/plain"},
            )
        if str(request.url) == "https://example.com/page":
            return httpx.Response(
                200,
                text="""
                <html><head><title>Example Plants</title></head>
                <body>
                  <main>
                    <h1>Native Plants</h1>
                    <p>Goldenrod and milkweed are common examples.</p>
                    <a href="/plants/goldenrod">Goldenrod</a>
                  </main>
                </body></html>
                """,
                headers={"content-type": "text/html; charset=utf-8"},
            )
        if str(request.url) == "https://example.com/blocked":
            return httpx.Response(200, text="<html><body>should not fetch</body></html>", headers={"content-type": "text/html"})
        return httpx.Response(404, text="not found", headers={"content-type": "text/plain"})

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    result = await fetch_web_research(
        urls=["https://example.com/page", "https://example.com/blocked"],
        selectors=["main"],
        transport=httpx.MockTransport(handler),
        sleep_fn=fake_sleep,
    )

    metrics = result.get("metrics", {})
    assert_true(metrics.get("accepted_urls") == 2, "accepted_urls should preserve both bounded inputs")
    assert_true(metrics.get("robots_requests") == 1, "robots.txt should be cached per host")
    assert_true(metrics.get("page_requests") == 1, "blocked robots target should not be fetched")
    assert_true(metrics.get("delays_applied") == 1, "same-host pacing delay should be applied once")
    assert_true(bool(sleep_calls), "sleep_fn should be used for per-host pacing")

    results = result.get("results", [])
    assert_true(len(results) == 1, "expected exactly one fetched page result")
    page = results[0]
    assert_true(page.get("title") == "Example Plants", "title extraction failed")
    assert_true("Goldenrod" in page.get("text_excerpt", ""), "text extraction failed")
    assert_true(page.get("selector_hits", {}).get("main") == 1, "selector hit accounting failed")
    assert_true(page.get("links") == ["https://example.com/plants/goldenrod"], "link extraction failed")

    skipped = result.get("skipped", [])
    assert_true(len(skipped) == 1 and skipped[0].get("reason") == "blocked_by_robots", "robots block not surfaced")
    assert_true("https://example.com/blocked" not in request_log, "blocked URL should not have been fetched")

    print("PASS: bounded web research lane enforces robots-aware pacing and extraction limits")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
