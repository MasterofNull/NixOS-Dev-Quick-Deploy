"""
Bounded web research helpers for the hybrid coordinator.

This module intentionally exposes a narrow fetch -> extract surface:
- explicit URL list only
- robots-aware when available
- per-host pacing
- no broad crawling or recursive discovery
- SSRF hardening with pinned-IP connect, per-hop re-check, and tighten-only switches (AUTH-S6)
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from shared.ssrf_protection import assert_safe_outbound_url, resolve_pinned


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
    crawl_budget_max_requests: int
    crawl_budget_max_seconds: float


def load_web_research_policy() -> WebResearchPolicy:
    enabled = os.getenv("AI_WEB_RESEARCH_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
    max_urls = max(1, min(int(os.getenv("AI_WEB_RESEARCH_MAX_URLS", "5")), 20))
    max_selectors = max(1, min(int(os.getenv("AI_WEB_RESEARCH_MAX_SELECTORS", "8")), 20))
    timeout_seconds = max(1.0, min(float(os.getenv("AI_WEB_RESEARCH_TIMEOUT_SECONDS", "12.0")), 60.0))
    per_host_delay_seconds = max(0.0, min(float(os.getenv("AI_WEB_RESEARCH_PER_HOST_DELAY_SECONDS", "0.5")), 5.0))
    max_response_bytes = max(1024, min(int(os.getenv("AI_WEB_RESEARCH_MAX_RESPONSE_BYTES", "262144")), 1_048_576))
    max_text_chars = max(100, min(int(os.getenv("AI_WEB_RESEARCH_MAX_TEXT_CHARS", "4000")), 20000))
    max_links = max(0, min(int(os.getenv("AI_WEB_RESEARCH_MAX_LINKS", "20")), 50))
    max_redirects = max(0, min(int(os.getenv("AI_WEB_RESEARCH_MAX_REDIRECTS", "3")), 5))
    user_agent = os.getenv("AI_WEB_RESEARCH_USER_AGENT", "NixOS-Dev-Quick-Deploy-Research/1.0 (+local-ai-agent)").strip()
    crawl_budget_max_requests = max(1, min(int(os.getenv("AI_WEB_RESEARCH_CRAWL_MAX_REQUESTS", "20")), 100))
    crawl_budget_max_seconds = max(1.0, min(float(os.getenv("AI_WEB_RESEARCH_CRAWL_MAX_SECONDS", "30.0")), 300.0))

    return WebResearchPolicy(
        enabled=enabled,
        max_urls=max_urls,
        max_selectors=max_selectors,
        timeout_seconds=timeout_seconds,
        per_host_delay_seconds=per_host_delay_seconds,
        max_response_bytes=max_response_bytes,
        max_text_chars=max_text_chars,
        max_links=max_links,
        max_redirects=max_redirects,
        user_agent=user_agent,
        crawl_budget_max_requests=crawl_budget_max_requests,
        crawl_budget_max_seconds=crawl_budget_max_seconds,
    )


def _normalize_urls(urls: List[Any], limit: int) -> List[str]:
    seen = set()
    normalized: List[str] = []
    for item in urls:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned:
            continue
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"}:
            continue
        if not parsed.netloc:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
        if len(normalized) >= limit:
            break
    return normalized


def _normalize_selectors(selectors: List[Any], limit: int) -> List[str]:
    seen = set()
    normalized: List[str] = []
    for item in selectors:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
        if len(normalized) >= limit:
            break
    return normalized


def _clip_text(text: str, max_chars: int) -> tuple[str, bool]:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed, False
    return collapsed[:max_chars].rstrip() + "...", True


def _extract_links(soup: BeautifulSoup, base_url: str, limit: int) -> List[str]:
    links: List[str] = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if full_url in seen:
            continue
        seen.add(full_url)
        links.append(full_url)
        if len(links) >= limit:
            break
    return links


async def _read_response_text(response: httpx.Response, max_bytes: int) -> tuple[str, bool, int]:
    chunks: List[bytes] = []
    read_bytes = 0
    truncated = False
    async for chunk in response.aiter_bytes():
        read_bytes += len(chunk)
        if read_bytes > max_bytes:
            allowed = max_bytes - (read_bytes - len(chunk))
            if allowed > 0:
                chunks.append(chunk[:allowed])
            truncated = True
            break
        chunks.append(chunk)

    encoding = response.encoding or "utf-8"
    return b"".join(chunks).decode(encoding, errors="replace"), truncated, read_bytes


def _build_pinned_connect(url: str, pinned_ip: str) -> tuple[str, Dict[str, str], Dict[str, Any]]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower()
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if ":" in pinned_ip and not pinned_ip.startswith("["):
        ip_netloc = f"[{pinned_ip}]"
    else:
        ip_netloc = pinned_ip

    if (parsed.scheme == "https" and port != 443) or (parsed.scheme == "http" and port != 80):
        ip_netloc = f"{ip_netloc}:{port}"

    connect_url = urlunparse((
        parsed.scheme,
        ip_netloc,
        parsed.path or "/",
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))

    host_header = host if port in {80, 443} else f"{host}:{port}"
    headers = {"Host": host_header}
    extensions: Dict[str, Any] = {"sni_hostname": host} if parsed.scheme == "https" else {}
    return connect_url, headers, extensions


async def _fetch_with_redirects(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_redirects: int,
    max_response_bytes: int,
    enforce_ssrf: bool = True,
    use_pinned_connect: bool = True,
) -> Dict[str, Any]:
    current_url = url
    redirect_history: List[str] = []
    for _ in range(max_redirects + 1):
        parsed = urlparse(current_url)
        host = (parsed.hostname or "").strip().lower()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        if enforce_ssrf:
            assert_safe_outbound_url(current_url, purpose="web_research_fetch")

        req_url = current_url
        req_headers: Dict[str, str] = {}
        req_extensions: Dict[str, Any] = {}

        if enforce_ssrf and use_pinned_connect:
            pinned_ips = await resolve_pinned(host, port)
            req_url, req_headers, req_extensions = _build_pinned_connect(current_url, pinned_ips[0])

        async with client.stream(
            "GET",
            req_url,
            headers=req_headers,
            extensions=req_extensions,
            follow_redirects=False,
        ) as response:
            status_code = int(response.status_code)
            if status_code in {301, 302, 303, 307, 308}:
                location = str(response.headers.get("location") or "").strip()
                if not location:
                    raise RuntimeError(f"redirect missing location header for {current_url}")
                redirect_url = urljoin(current_url, location)
                if enforce_ssrf:
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
    enforce_ssrf: bool = True,
    use_pinned_connect: bool = True,
) -> Dict[str, Any]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower()
    scheme = parsed.scheme
    if not host or scheme not in {"http", "https"}:
        return {"allowed": False, "reason": "invalid_url_for_robots"}

    cache_key = f"{scheme}://{host}"
    if cache_key in cache:
        cached_entry = cache[cache_key]
        parser = cached_entry.get("parser")
        if parser is not None:
            allowed = bool(parser.can_fetch(user_agent, url))
            return {
                "allowed": allowed,
                "status_code": cached_entry.get("status_code", 200),
                "reason": "allowed_by_robots" if allowed else "blocked_by_robots",
            }
        return cached_entry.get("meta", {"allowed": True, "status_code": 0, "reason": "robots_cache_missing"})

    robots_url = f"{scheme}://{host}/robots.txt"
    try:
        if enforce_ssrf:
            assert_safe_outbound_url(robots_url, purpose="web_research_robots")
        payload = await _fetch_with_redirects(
            client,
            robots_url,
            max_redirects=max_redirects,
            max_response_bytes=128_000,
            enforce_ssrf=enforce_ssrf,
            use_pinned_connect=use_pinned_connect,
        )
        if int(payload["status_code"]) < 400:
            parser = RobotFileParser()
            parser.parse(str(payload.get("text") or "").splitlines())
            allowed = bool(parser.can_fetch(user_agent, url))
            meta = {
                "allowed": allowed,
                "status_code": int(payload["status_code"]),
                "reason": "allowed_by_robots" if allowed else "blocked_by_robots",
            }
            cache[cache_key] = {"parser": parser, "status_code": int(payload["status_code"]), "meta": meta}
            return meta
        else:
            meta = {
                "allowed": True,
                "status_code": int(payload["status_code"]),
                "reason": "robots_absent_allowed",
            }
            cache[cache_key] = {"parser": None, "status_code": int(payload["status_code"]), "meta": meta}
            return meta
    except PermissionError as exc:
        meta = {"allowed": False, "reason": f"ssrf_blocked_robots:{exc}"}
        cache[cache_key] = {"parser": None, "status_code": 0, "meta": meta}
        return meta
    except Exception as exc:
        meta = {
            "allowed": True,
            "status_code": 0,
            "reason": f"robots_fetch_failed_allowed:{exc.__class__.__name__}",
        }
        cache[cache_key] = {"parser": None, "status_code": 0, "meta": meta}
        return meta


def _extract_text(soup: BeautifulSoup, selectors: List[str], max_text_chars: int) -> Dict[str, Any]:
    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()

    selector_hits: Dict[str, int] = {}
    selected_nodes = []
    if selectors:
        for selector in selectors:
            matches = soup.select(selector)
            selector_hits[selector] = len(matches)
            selected_nodes.extend(matches)

    if not selected_nodes:
        main_node = soup.find("main") or soup.find("article") or soup.body or soup
        selected_nodes = [main_node]

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
    enforce_ssrf: Optional[bool] = None,
) -> Dict[str, Any]:
    policy = load_web_research_policy()
    if not policy.enabled:
        raise RuntimeError("web research is disabled")

    # In test mode or when explicitly set, honour explicit enforce_ssrf
    # By default, enforce_ssrf is always True in production.
    if enforce_ssrf is None:
        if transport is not None and os.getenv("AQ_TEST_MODE") == "1":
            effective_enforce_ssrf = False
        else:
            effective_enforce_ssrf = True
    else:
        effective_enforce_ssrf = bool(enforce_ssrf)

    # When transport is provided (e.g. MockTransport in tests), skip pinned IP connect
    use_pinned = transport is None

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
    async with httpx.AsyncClient(
        timeout=policy.timeout_seconds,
        headers=headers,
        transport=transport,
        trust_env=False,
    ) as client:
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
                enforce_ssrf=effective_enforce_ssrf,
                use_pinned_connect=use_pinned,
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
                    enforce_ssrf=effective_enforce_ssrf,
                    use_pinned_connect=use_pinned,
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
