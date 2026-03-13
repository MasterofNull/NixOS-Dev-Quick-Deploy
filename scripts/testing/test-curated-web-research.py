#!/usr/bin/env python3
"""Checks for manifest-backed curated research workflows."""

import asyncio
import json
import os
import sys
import tempfile
import types
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_WEB_RESEARCH_ENABLED", "true")
os.environ.setdefault("AI_WEB_RESEARCH_MAX_URLS", "3")
os.environ.setdefault("AI_WEB_RESEARCH_MAX_SELECTORS", "4")
os.environ.setdefault("AI_WEB_RESEARCH_TIMEOUT_SECONDS", "5")
os.environ.setdefault("AI_WEB_RESEARCH_PER_HOST_DELAY_SECONDS", "0.1")
os.environ.setdefault("AI_WEB_RESEARCH_MAX_RESPONSE_BYTES", "16384")
os.environ.setdefault("AI_WEB_RESEARCH_MAX_TEXT_CHARS", "500")
os.environ.setdefault("AI_WEB_RESEARCH_MAX_LINKS", "5")
os.environ.setdefault("AI_WEB_RESEARCH_MAX_REDIRECTS", "1")
if "structlog" not in sys.modules:
    sys.modules["structlog"] = types.SimpleNamespace(
        get_logger=lambda: types.SimpleNamespace(debug=lambda *a, **k: None, warning=lambda *a, **k: None)
    )
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from research_workflows import list_curated_research_workflows, run_curated_research_workflow  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_dir:
        manifest_path = Path(tmp_dir) / "curated-web-research-sources.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "workflows": [
                        {
                            "slug": "generic-example",
                            "description": "Example bounded workflow",
                            "max_urls": 2,
                            "default_max_text_chars": 300,
                            "inputs": [{"name": "topic", "required": True}],
                            "sources": [
                                {
                                    "name": "example-home",
                                    "url": "https://example.com/home",
                                    "selectors": ["main"],
                                    "purpose": "Static source",
                                },
                                {
                                    "name": "example-search",
                                    "url_template": "https://example.com/topics/{topic}",
                                    "selectors": ["main", "article"],
                                    "purpose": "Templated source",
                                }
                            ]
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        os.environ["AI_CURATED_RESEARCH_WORKFLOWS_FILE"] = str(manifest_path)

        workflows = list_curated_research_workflows()
        assert_true(len(workflows) == 1 and workflows[0]["slug"] == "generic-example", "workflow listing failed")

        request_log = []

        def handler(request: httpx.Request) -> httpx.Response:
            request_log.append(str(request.url))
            if str(request.url) == "https://example.com/robots.txt":
                return httpx.Response(200, text="User-agent: *\nAllow: /\n", headers={"content-type": "text/plain"})
            if str(request.url) == "https://example.com/home":
                return httpx.Response(
                    200,
                    text="<html><head><title>Home</title></head><body><main>alpha data</main></body></html>",
                    headers={"content-type": "text/html; charset=utf-8"},
                )
            if str(request.url) == "https://example.com/topics/native-plants":
                return httpx.Response(
                    200,
                    text="<html><head><title>Topic</title></head><body><article>beta data</article></body></html>",
                    headers={"content-type": "text/html; charset=utf-8"},
                )
            if str(request.url) == "https://example.com/topics/challenge":
                return httpx.Response(
                    200,
                    text="<html><head><title>Just a moment...</title></head><body><main>Enable JavaScript and cookies to continue</main></body></html>",
                    headers={"content-type": "text/html; charset=utf-8"},
                )
            return httpx.Response(404, text="not found", headers={"content-type": "text/plain"})

        result = await run_curated_research_workflow(
            workflow_slug="generic-example",
            inputs={"topic": "native-plants"},
            transport=httpx.MockTransport(handler),
            sleep_fn=lambda _seconds: asyncio.sleep(0),
        )

        assert_true(result["workflow"]["slug"] == "generic-example", "workflow slug mismatch")
        assert_true(len(result["selected_sources"]) == 2, "source limit mismatch")
        assert_true(result["result_count"] == 2, "expected two fetched results")
        assert_true(result["fetch"]["metrics"]["robots_requests"] == 1, "expected one robots request")
        assert_true(
            any(item["requested_url"] == "https://example.com/topics/native-plants" for item in result["fetch"]["results"]),
            "templated source url not expanded",
        )
        assert_true(
            any(entry["source_name"] == "example-home" and entry["result"]["title"] == "Home" for entry in result["results"]),
            "organized result missing home source",
        )
        assert_true("https://example.com/robots.txt" in request_log, "robots check missing")

        challenge_result = await run_curated_research_workflow(
            workflow_slug="generic-example",
            inputs={"topic": "challenge"},
            transport=httpx.MockTransport(handler),
            sleep_fn=lambda _seconds: asyncio.sleep(0),
        )
        challenge_entry = next(
            item for item in challenge_result["results"] if item["source_name"] == "example-search"
        )
        assert_true(challenge_entry["status"] == "needs_fallback", "bot gate should require fallback")
        assert_true(challenge_entry["issue_class"] == "bot_gate_detected", "bot gate classification mismatch")

        try:
            await run_curated_research_workflow(
                workflow_slug="generic-example",
                inputs={},
                transport=httpx.MockTransport(handler),
                sleep_fn=lambda _seconds: asyncio.sleep(0),
            )
        except ValueError as exc:
            assert_true("missing required workflow inputs" in str(exc), "missing-input validation mismatch")
        else:
            raise AssertionError("missing required inputs should fail")

    print("PASS: curated web research workflows stay manifest-driven, bounded, and fallback-aware")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
