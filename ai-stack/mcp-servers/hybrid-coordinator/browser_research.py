"""
Bounded browser-assisted research helpers for JS-heavy public pages.

This is a fallback layer, not the default scraper:
- explicit URL list only
- robots-aware precheck before launching the browser
- same extraction limits as the normal web research path
- no anti-bot evasion; challenge pages are surfaced as fallback-required
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from shared.ssrf_protection import assert_safe_outbound_url
from web_research import (
    _extract_links,
    _extract_text,
    _normalize_selectors,
    _normalize_urls,
    _robots_allowed,
)


@dataclass(frozen=True)
class BrowserResearchPolicy:
    enabled: bool
    max_urls: int
    max_selectors: int
    timeout_seconds: float
    per_host_delay_seconds: float
    max_text_chars: int
    max_links: int
    max_redirects: int
    user_agent: str
    chromium_binary: str
    virtual_time_budget_ms: int


def _env_bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, value)


def load_browser_research_policy() -> BrowserResearchPolicy:
    return BrowserResearchPolicy(
        enabled=_env_bool("AI_BROWSER_RESEARCH_ENABLED", "true"),
        max_urls=_env_int("AI_BROWSER_RESEARCH_MAX_URLS", 1, minimum=1),
        max_selectors=_env_int("AI_BROWSER_RESEARCH_MAX_SELECTORS", 4, minimum=0),
        timeout_seconds=_env_float("AI_BROWSER_RESEARCH_TIMEOUT_SECONDS", 18.0, minimum=2.0),
        per_host_delay_seconds=_env_float("AI_BROWSER_RESEARCH_PER_HOST_DELAY_SECONDS", 2.0, minimum=0.0),
        max_text_chars=_env_int("AI_BROWSER_RESEARCH_MAX_TEXT_CHARS", 6000, minimum=256),
        max_links=_env_int("AI_BROWSER_RESEARCH_MAX_LINKS", 12, minimum=0),
        max_redirects=_env_int("AI_BROWSER_RESEARCH_MAX_REDIRECTS", 2, minimum=0),
        user_agent=os.getenv(
            "AI_BROWSER_RESEARCH_USER_AGENT",
            "nixos-dev-quick-deploy-browser-research/1.0 (+respectful bounded browser fetch)",
        ).strip()
        or "nixos-dev-quick-deploy-browser-research/1.0 (+respectful bounded browser fetch)",
        chromium_binary=os.getenv("AI_BROWSER_RESEARCH_CHROMIUM_BIN", "chromium").strip() or "chromium",
        virtual_time_budget_ms=_env_int("AI_BROWSER_RESEARCH_VIRTUAL_TIME_BUDGET_MS", 8000, minimum=1000),
    )


async def _dump_browser_dom(
    url: str,
    *,
    chromium_binary: str,
    virtual_time_budget_ms: int,
    timeout_seconds: float,
    runner: Optional[Callable[..., Awaitable[tuple[int, str, str]]]] = None,
) -> tuple[int, str, str]:
    assert_safe_outbound_url(url, purpose="browser_research_fetch")
    if runner is not None:
        return await runner(
            url=url,
            chromium_binary=chromium_binary,
            virtual_time_budget_ms=virtual_time_budget_ms,
            timeout_seconds=timeout_seconds,
        )

    with tempfile.TemporaryDirectory(prefix="browser-research-") as profile_dir:
        proc = await asyncio.create_subprocess_exec(
            chromium_binary,
            "--headless",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile_dir}",
            f"--virtual-time-budget={virtual_time_budget_ms}",
            "--dump-dom",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise RuntimeError("browser_fetch_timeout")
        return int(proc.returncode or 0), stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


async def fetch_browser_research(
    *,
    urls: List[Any],
    selectors: Optional[List[Any]] = None,
    max_text_chars: Optional[int] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    sleep_fn: Optional[Callable[[float], Awaitable[None]]] = None,
    browser_runner: Optional[Callable[..., Awaitable[tuple[int, str, str]]]] = None,
) -> Dict[str, Any]:
    policy = load_browser_research_policy()
    if not policy.enabled:
        raise RuntimeError("browser research is disabled")

    normalized_urls = _normalize_urls(urls, policy.max_urls)
    normalized_selectors = _normalize_selectors(selectors or [], policy.max_selectors)
    effective_max_text_chars = min(max_text_chars or policy.max_text_chars, policy.max_text_chars)
    effective_sleep = sleep_fn or asyncio.sleep

    metrics = {
        "submitted_urls": len(list(urls)),
        "accepted_urls": len(normalized_urls),
        "browser_requests": 0,
        "robots_requests": 0,
        "delays_applied": 0,
        "delay_seconds_total": 0.0,
    }
    results: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    robots_cache: Dict[str, Dict[str, Any]] = {}
    last_request_by_host: Dict[str, float] = {}

    headers = {
        "User-Agent": policy.user_agent,
        "Accept": "text/html,application/xhtml+xml",
    }
    async with httpx.AsyncClient(timeout=policy.timeout_seconds, headers=headers, transport=transport) as client:
        for url in normalized_urls:
            parsed = urlparse(url)
            host = (parsed.hostname or "").strip().lower()
            if not host:
                skipped.append({"url": url, "reason": "missing_host"})
                continue

            previous = last_request_by_host.get(host)
            if previous is not None and policy.per_host_delay_seconds > 0:
                elapsed = time.monotonic() - previous
                remaining = policy.per_host_delay_seconds - elapsed
                if remaining > 0:
                    metrics["delays_applied"] += 1
                    metrics["delay_seconds_total"] += remaining
                    await effective_sleep(remaining)

            robots_meta = await _robots_allowed(
                client,
                url,
                user_agent=policy.user_agent,
                max_redirects=policy.max_redirects,
                cache=robots_cache,
            )
            metrics["robots_requests"] = len(robots_cache)
            if not robots_meta.get("allowed", True):
                skipped.append({"url": url, "reason": robots_meta.get("reason", "blocked_by_robots")})
                last_request_by_host[host] = time.monotonic()
                continue

            try:
                return_code, html, stderr_text = await _dump_browser_dom(
                    url,
                    chromium_binary=policy.chromium_binary,
                    virtual_time_budget_ms=policy.virtual_time_budget_ms,
                    timeout_seconds=policy.timeout_seconds,
                    runner=browser_runner,
                )
                last_request_by_host[host] = time.monotonic()
                metrics["browser_requests"] += 1
            except PermissionError as exc:
                skipped.append({"url": url, "reason": f"ssrf_blocked:{exc}"})
                last_request_by_host[host] = time.monotonic()
                continue
            except Exception as exc:
                skipped.append({"url": url, "reason": f"browser_failed:{exc}"})
                last_request_by_host[host] = time.monotonic()
                continue

            if return_code != 0:
                skipped.append({"url": url, "reason": f"browser_failed:returncode_{return_code}"})
                continue

            soup = BeautifulSoup(html or "", "html.parser")
            extracted = _extract_text(soup, normalized_selectors, effective_max_text_chars)
            results.append(
                {
                    "requested_url": url,
                    "final_url": url,
                    "status_code": 200,
                    "host": host,
                    "title": extracted["title"],
                    "text_excerpt": extracted["text_excerpt"],
                    "text_truncated": bool(extracted["text_truncated"]),
                    "selector_hits": extracted["selector_hits"],
                    "links": _extract_links(soup, url, policy.max_links),
                    "content_type": "text/html; rendered",
                    "read_bytes": len(html.encode("utf-8", errors="ignore")),
                    "response_truncated": False,
                    "redirect_history": [],
                    "robots": robots_meta,
                    "browser_stderr_excerpt": " ".join(stderr_text.split())[:240],
                }
            )

    return {
        "status": "ok",
        "policy": {
            "max_urls": policy.max_urls,
            "max_selectors": policy.max_selectors,
            "timeout_seconds": policy.timeout_seconds,
            "per_host_delay_seconds": policy.per_host_delay_seconds,
            "max_text_chars": policy.max_text_chars,
            "max_links": policy.max_links,
            "max_redirects": policy.max_redirects,
            "user_agent": policy.user_agent,
            "chromium_binary": policy.chromium_binary,
            "virtual_time_budget_ms": policy.virtual_time_budget_ms,
        },
        "request": {
            "urls": normalized_urls,
            "selectors": normalized_selectors,
            "max_text_chars": effective_max_text_chars,
        },
        "metrics": metrics,
        "results": results,
        "skipped": skipped,
    }
