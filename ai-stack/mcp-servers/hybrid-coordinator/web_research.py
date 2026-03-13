"""
Bounded web research helpers for the hybrid coordinator.

This module intentionally exposes a narrow fetch -> extract surface:
- explicit URL list only
- robots-aware when available
- per-host pacing
- no broad crawling or recursive discovery
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from shared.ssrf_protection import assert_safe_outbound_url


@dataclass(frozen=True)
class WebResearchPolicy:
    enabled: bool
    max_urls: int
    max_selectors: int
    timeout_seconds: float
    per_host_delay_seconds: float
    max_response_bytes: int
    max_text_chars: int
    max_links: int
    max_redirects: int
    user_agent: str


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


def load_web_research_policy() -> WebResearchPolicy:
    return WebResearchPolicy(
        enabled=_env_bool("AI_WEB_RESEARCH_ENABLED", "true"),
        max_urls=_env_int("AI_WEB_RESEARCH_MAX_URLS", 3, minimum=1),
        max_selectors=_env_int("AI_WEB_RESEARCH_MAX_SELECTORS", 4, minimum=0),
        timeout_seconds=_env_float("AI_WEB_RESEARCH_TIMEOUT_SECONDS", 12.0, minimum=1.0),
        per_host_delay_seconds=_env_float("AI_WEB_RESEARCH_PER_HOST_DELAY_SECONDS", 1.5, minimum=0.0),
        max_response_bytes=_env_int("AI_WEB_RESEARCH_MAX_RESPONSE_BYTES", 400_000, minimum=8_192),
        max_text_chars=_env_int("AI_WEB_RESEARCH_MAX_TEXT_CHARS", 6_000, minimum=256),
        max_links=_env_int("AI_WEB_RESEARCH_MAX_LINKS", 12, minimum=0),
        max_redirects=_env_int("AI_WEB_RESEARCH_MAX_REDIRECTS", 2, minimum=0),
        user_agent=os.getenv(
            "AI_WEB_RESEARCH_USER_AGENT",
            "nixos-dev-quick-deploy-web-research/1.0 (+respectful bounded fetch)",
        ).strip()
        or "nixos-dev-quick-deploy-web-research/1.0 (+respectful bounded fetch)",
    )


def _clip_text(text: str, limit: int) -> tuple[str, bool]:
    normalized = " ".join(str(text or "").split())
    if limit <= 0 or len(normalized) <= limit:
        return normalized, False
    if limit <= 3:
        return normalized[:limit], True
    return normalized[: limit - 3].rstrip() + "...", True


def _normalize_urls(urls: List[Any], max_urls: int) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw in urls:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
        if len(normalized) >= max_urls:
            break
    return normalized


def _normalize_selectors(selectors: List[Any], max_selectors: int) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw in selectors:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
        if len(normalized) >= max_selectors:
            break
    return normalized


async def _read_response_text(response: httpx.Response, max_bytes: int) -> tuple[str, bool, int]:
    chunks: List[bytes] = []
    read_bytes = 0
    truncated = False
    async for chunk in response.aiter_bytes():
        if not chunk:
            continue
        remaining = max_bytes - read_bytes
        if remaining <= 0:
            truncated = True
            break
        if len(chunk) > remaining:
            chunks.append(chunk[:remaining])
            read_bytes += remaining
            truncated = True
            break
        chunks.append(chunk)
        read_bytes += len(chunk)
    encoding = response.encoding or "utf-8"
    return b"".join(chunks).decode(encoding, errors="replace"), truncated, read_bytes


async def _fetch_with_redirects(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_redirects: int,
    max_response_bytes: int,
) -> Dict[str, Any]:
    current_url = url
    redirect_history: List[str] = []
    for _ in range(max_redirects + 1):
        assert_safe_outbound_url(current_url, purpose="web_research_fetch")
        async with client.stream("GET", current_url, follow_redirects=False) as response:
            status_code = int(response.status_code)
            if status_code in {301, 302, 303, 307, 308}:
                location = str(response.headers.get("location") or "").strip()
                if not location:
                    raise RuntimeError(f"redirect missing location header for {current_url}")
                redirect_url = urljoin(current_url, location)
                assert_safe_outbound_url(redirect_url, purpose="web_research_redirect")
                redirect_history.append(redirect_url)
                current_url = redirect_url
                continue
            text, truncated, read_bytes = await _read_response_text(response, max_response_bytes)
            return {
                "url": current_url,
                "status_code": status_code,
                "headers": dict(response.headers),
                "text": text,
                "truncated_bytes": truncated,
                "read_bytes": read_bytes,
                "redirect_history": redirect_history,
            }
    raise RuntimeError(f"redirect limit exceeded for {url}")


async def _robots_allowed(
    client: httpx.AsyncClient,
    url: str,
    *,
    user_agent: str,
    max_redirects: int,
    cache: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower()
    scheme = (parsed.scheme or "").strip().lower()
    cache_key = f"{scheme}://{host}"
    if cache_key not in cache:
        robots_url = f"{scheme}://{host}/robots.txt"
        cache_entry: Dict[str, Any] = {
            "robots_url": robots_url,
            "robots_checked": True,
            "robots_present": False,
            "reason": "robots_missing",
            "parser": None,
        }
        try:
            payload = await _fetch_with_redirects(
                client,
                robots_url,
                max_redirects=max_redirects,
                max_response_bytes=128_000,
            )
            if int(payload["status_code"]) < 400:
                parser = RobotFileParser()
                parser.set_url(payload["url"])
                parser.parse((payload.get("text") or "").splitlines())
                cache_entry.update(
                    {
                        "robots_present": True,
                        "reason": "parsed",
                        "parser": parser,
                    }
                )
        except Exception as exc:
            cache_entry.update({"robots_checked": False, "reason": f"robots_error:{exc.__class__.__name__}"})
        cache[cache_key] = cache_entry

    cached = cache[cache_key]
    parser = cached.get("parser")
    allowed = True if parser is None else bool(parser.can_fetch(user_agent, url))
    return {
        "robots_url": cached.get("robots_url"),
        "robots_checked": bool(cached.get("robots_checked", False)),
        "robots_present": bool(cached.get("robots_present", False)),
        "allowed": allowed,
        "reason": "allowed" if allowed else "blocked_by_robots",
    }


def _extract_links(soup: BeautifulSoup, base_url: str, max_links: int) -> List[str]:
    if max_links <= 0:
        return []
    links: List[str] = []
    seen = set()
    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)
        if len(links) >= max_links:
            break
    return links


def _extract_text(soup: BeautifulSoup, selectors: List[str], max_text_chars: int) -> Dict[str, Any]:
    for node in soup.select("script, style, noscript, template"):
        node.decompose()

    selected_nodes = []
    selector_hits: Dict[str, int] = {}
    if selectors:
        for selector in selectors:
            try:
                matches = soup.select(selector)
            except Exception:
                matches = []
            selector_hits[selector] = len(matches)
            selected_nodes.extend(matches)

    if not selected_nodes:
        selected_nodes = soup.select("main, article, [role='main'], .content, #content")
    if not selected_nodes:
        selected_nodes = [soup.body or soup]

    combined = "\n".join(node.get_text(" ", strip=True) for node in selected_nodes if node)
    text_excerpt, truncated = _clip_text(combined, max_text_chars)
    title = ""
    if soup.title and soup.title.string:
        title = " ".join(soup.title.string.split())

    return {
        "title": title,
        "text_excerpt": text_excerpt,
        "text_truncated": truncated,
        "selector_hits": selector_hits,
    }


async def fetch_web_research(
    *,
    urls: List[Any],
    selectors: Optional[List[Any]] = None,
    max_text_chars: Optional[int] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    sleep_fn: Optional[Callable[[float], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    policy = load_web_research_policy()
    if not policy.enabled:
        raise RuntimeError("web research is disabled")

    normalized_urls = _normalize_urls(urls, policy.max_urls)
    normalized_selectors = _normalize_selectors(selectors or [], policy.max_selectors)
    effective_max_text_chars = min(max_text_chars or policy.max_text_chars, policy.max_text_chars)
    effective_sleep = sleep_fn or asyncio.sleep

    metrics = {
        "submitted_urls": len(list(urls)),
        "accepted_urls": len(normalized_urls),
        "page_requests": 0,
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
                payload = await _fetch_with_redirects(
                    client,
                    url,
                    max_redirects=policy.max_redirects,
                    max_response_bytes=policy.max_response_bytes,
                )
                last_request_by_host[host] = time.monotonic()
                metrics["page_requests"] += 1
            except PermissionError as exc:
                skipped.append({"url": url, "reason": f"ssrf_blocked:{exc}"})
                last_request_by_host[host] = time.monotonic()
                continue
            except Exception as exc:
                skipped.append({"url": url, "reason": f"fetch_failed:{exc.__class__.__name__}"})
                last_request_by_host[host] = time.monotonic()
                continue

            content_type = str((payload.get("headers") or {}).get("content-type") or "").lower()
            if "html" not in content_type and "xml" not in content_type:
                skipped.append({"url": url, "reason": f"unsupported_content_type:{content_type or 'unknown'}"})
                continue

            soup = BeautifulSoup(payload.get("text") or "", "html.parser")
            extracted = _extract_text(soup, normalized_selectors, effective_max_text_chars)
            results.append(
                {
                    "requested_url": url,
                    "final_url": payload.get("url", url),
                    "status_code": int(payload.get("status_code", 0) or 0),
                    "host": host,
                    "title": extracted["title"],
                    "text_excerpt": extracted["text_excerpt"],
                    "text_truncated": bool(extracted["text_truncated"]),
                    "selector_hits": extracted["selector_hits"],
                    "links": _extract_links(soup, str(payload.get("url") or url), policy.max_links),
                    "content_type": content_type,
                    "read_bytes": int(payload.get("read_bytes", 0) or 0),
                    "response_truncated": bool(payload.get("truncated_bytes", False)),
                    "redirect_history": payload.get("redirect_history", []),
                    "robots": robots_meta,
                }
            )

    return {
        "status": "ok",
        "policy": {
            "max_urls": policy.max_urls,
            "max_selectors": policy.max_selectors,
            "timeout_seconds": policy.timeout_seconds,
            "per_host_delay_seconds": policy.per_host_delay_seconds,
            "max_response_bytes": policy.max_response_bytes,
            "max_text_chars": policy.max_text_chars,
            "max_links": policy.max_links,
            "max_redirects": policy.max_redirects,
            "user_agent": policy.user_agent,
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
