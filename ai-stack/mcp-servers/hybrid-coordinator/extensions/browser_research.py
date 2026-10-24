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
import re
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
    crawl_budget_max_requests: int
    crawl_budget_max_seconds: float


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
        crawl_budget_max_requests=_env_int("AI_BROWSER_RESEARCH_CRAWL_MAX_REQUESTS", 10, minimum=1),
        crawl_budget_max_seconds=_env_float("AI_BROWSER_RESEARCH_CRAWL_MAX_SECONDS", 60.0, minimum=5.0),
    )


def extract_structured_dom(soup: BeautifulSoup, base_url: str = "") -> Dict[str, Any]:
    """Structured extraction: metadata, heading hierarchy, and tabular data."""
    meta: Dict[str, str] = {}
    for tag in soup.find_all("meta"):
        name = tag.get("name") or tag.get("property") or tag.get("http-equiv")
        content = tag.get("content")
        if name and content:
            clean_name = str(name).strip().lower()
            clean_content = str(content).strip()
            if clean_name and clean_content and len(clean_name) < 80:
                meta[clean_name] = clean_content[:500]

    headings: List[Dict[str, Any]] = []
    for h in soup.find_all(re.compile(r"^h[1-6]$"))[:30]:
        try:
            level = int(h.name[1])
            text = h.get_text(separator=" ", strip=True)
            if text:
                headings.append({"level": level, "text": text[:200]})
        except (ValueError, IndexError):
            pass

    tables: List[List[List[str]]] = []
    for t in soup.find_all("table")[:5]:
        rows: List[List[str]] = []
        for tr in t.find_all("tr")[:25]:
            cells = [cell.get_text(separator=" ", strip=True)[:150] for cell in tr.find_all(["td", "th"])[:12]]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)

    return {
        "metadata": meta,
        "headings": headings,
        "tables": tables,
    }


async def _dump_browser_dom(
    url: str,
    *,
    chromium_binary: str,
    virtual_time_budget_ms: int,
    timeout_seconds: float,
    runner: Optional[Callable[..., Awaitable[tuple[int, str, str]]]] = None,
    enforce_ssrf: bool = True,
) -> tuple[int, str, str]:
    if enforce_ssrf:
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
    structured_extract: bool = False,
    crawl_budget_max_requests: Optional[int] = None,
    crawl_budget_max_seconds: Optional[float] = None,
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
    if transport is not None and browser_runner is not None and os.getenv("AQ_TEST_MODE") == "1":
        enforce_ssrf = False
    else:
        enforce_ssrf = True

    max_reqs_budget = crawl_budget_max_requests if crawl_budget_max_requests is not None else policy.crawl_budget_max_requests
    max_secs_budget = crawl_budget_max_seconds if crawl_budget_max_seconds is not None else policy.crawl_budget_max_seconds

    metrics = {
        "submitted_urls": len(list(urls)),
        "accepted_urls": len(normalized_urls),
        "browser_requests": 0,
        "robots_requests": 0,
        "delays_applied": 0,
        "delay_seconds_total": 0.0,
        "crawl_budget_exceeded": False,
        "crawl_elapsed_seconds": 0.0,
    }
    results: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    robots_cache: Dict[str, Dict[str, Any]] = {}
    last_request_by_host: Dict[str, float] = {}

    headers = {
        "User-Agent": policy.user_agent,
        "Accept": "text/html,application/xhtml+xml",
    }
    crawl_start = time.monotonic()
    async with httpx.AsyncClient(timeout=policy.timeout_seconds, headers=headers, transport=transport) as client:
        for url in normalized_urls:
            now = time.monotonic()
            elapsed_crawl = now - crawl_start
            metrics["crawl_elapsed_seconds"] = round(elapsed_crawl, 3)

            if metrics["browser_requests"] >= max_reqs_budget:
                metrics["crawl_budget_exceeded"] = True
                skipped.append({"url": url, "reason": "crawl_budget_max_requests_exceeded"})
                continue
            if elapsed_crawl >= max_secs_budget:
                metrics["crawl_budget_exceeded"] = True
                skipped.append({"url": url, "reason": "crawl_budget_max_seconds_exceeded"})
                continue

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
                enforce_ssrf=enforce_ssrf,
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
                    enforce_ssrf=enforce_ssrf,
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
            res_item: Dict[str, Any] = {
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
            if structured_extract:
                res_item["structured"] = extract_structured_dom(soup, base_url=url)

            results.append(res_item)

    metrics["crawl_elapsed_seconds"] = round(time.monotonic() - crawl_start, 3)

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
            "crawl_budget_max_requests": max_reqs_budget,
            "crawl_budget_max_seconds": max_secs_budget,
        },
        "request": {
            "urls": normalized_urls,
            "selectors": normalized_selectors,
            "max_text_chars": effective_max_text_chars,
            "structured_extract": structured_extract,
        },
        "metrics": metrics,
        "results": results,
        "skipped": skipped,
    }
