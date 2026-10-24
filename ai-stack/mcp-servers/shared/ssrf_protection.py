"""
Phase 13.2.2 & AUTH-S6 — SSRF (Server-Side Request Forgery) Protection

Provides URL validation and pinned-IP resolution to prevent outbound requests
to private/internal networks and DNS rebinding attacks.
Used by hybrid-coordinator and other MCP servers for safe HTTP client initialization.

Usage:
    from shared.ssrf_protection import (
        assert_safe_outbound_url,
        resolve_pinned,
        is_safe_global_ip,
        create_ssrf_safe_http_client,
    )

    # Validate URL before use
    assert_safe_outbound_url(url, purpose="llama_cpp_request")

    # Resolve pinned public IP addresses for HTTP connect
    ips = await resolve_pinned(host, port)
"""

import asyncio
import ipaddress
import os
import socket
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

try:
    import structlog
    _logger = structlog.get_logger()
    def _log_warn(event: str, **kwargs: Any) -> None:
        _logger.warning(event, **kwargs)
    def _log_debug(event: str, **kwargs: Any) -> None:
        _logger.debug(event, **kwargs)
except ImportError:
    import logging
    _logger = logging.getLogger("shared.ssrf_protection")
    def _log_warn(event: str, **kwargs: Any) -> None:
        _logger.warning("%s: %s", event, kwargs)
    def _log_debug(event: str, **kwargs: Any) -> None:
        _logger.debug("%s: %s", event, kwargs)

# Special network ranges that are not safe global destinations
NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")
RFC3056_6TO4_PREFIX = ipaddress.ip_network("2002::/16")
CGNAT_PREFIX = ipaddress.ip_network("100.64.0.0/10")


def _unwrap_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Unwrap IPv4-mapped IPv6 address (e.g. ::ffff:127.0.0.1 -> 127.0.0.1)."""
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        return addr.ipv4_mapped
    return addr


def is_safe_global_ip(addr_or_str: str | ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """
    Check if an address is globally routable and not in private, loopback,
    link-local, cloud metadata, multicast, reserved, NAT64, 6to4, or CGNAT spaces.
    Positive logic as required by agent-auth DESIGN section 4.1.
    """
    try:
        if isinstance(addr_or_str, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            addr = _unwrap_ip(addr_or_str)
        else:
            addr = _unwrap_ip(ipaddress.ip_address(str(addr_or_str).strip()))
    except (ValueError, TypeError):
        return False

    if not addr.is_global:
        return False

    if addr.is_multicast or addr.is_reserved or addr.is_link_local or addr.is_loopback or addr.is_unspecified:
        return False

    if isinstance(addr, ipaddress.IPv6Address):
        if addr in NAT64_PREFIX or addr in RFC3056_6TO4_PREFIX:
            return False
    elif isinstance(addr, ipaddress.IPv4Address):
        if addr in CGNAT_PREFIX:
            return False

    return True


def _ssrf_policy_config() -> Dict[str, Any]:
    """
    Load SSRF policy configuration from environment variables with tighten-only rules.

    Under enforce or lockdown modes (AQ_AGENT_AUTH_MODE), private egress blocking
    is strictly enforced and cannot be disabled by environment variables.
    """
    auth_mode = os.getenv("AQ_AGENT_AUTH_MODE", "").strip().lower()
    is_enforcing = auth_mode in {"enforce", "lockdown"}

    raw_block_private = os.getenv("HYBRID_BLOCK_PRIVATE_EGRESS", "true").lower() == "true"
    if is_enforcing:
        # Tighten-only: always block private ranges under enforce/lockdown
        block_private = True
    else:
        block_private = raw_block_private

    raw_allow_http = os.getenv("HYBRID_ALLOW_PLAINTEXT_HTTP", "false").lower() == "true"
    allow_http = False if is_enforcing else raw_allow_http

    allowed_hosts_raw = os.getenv("HYBRID_OUTBOUND_ALLOWLIST", "").strip()
    allowlist = [item.strip().lower() for item in allowed_hosts_raw.split(",") if item.strip()]

    return {
        "allowlist": allowlist,
        "block_private_ranges": block_private,
        "allow_http": allow_http,
        "is_enforcing": is_enforcing,
    }


def _looks_private_or_local(hostname: str) -> bool:
    """
    Check if a hostname or IP address is in a private/local network range.
    """
    host = (hostname or "").strip().lower()
    if not host:
        return True

    # Check well-known local domains
    if host in {"localhost", "localhost.localdomain"}:
        return True
    if host.endswith(".local") or host.endswith(".localhost"):
        return True

    # Try to parse as IP address directly
    try:
        addr = ipaddress.ip_address(host)
        return not is_safe_global_ip(addr)
    except ValueError:
        pass

    # Resolve hostname to IP
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        _log_warn("ssrf_dns_resolution_failed", hostname=host)
        return True

    for info in infos:
        candidate = info[4][0]
        if not is_safe_global_ip(candidate):
            return True

    return False


async def resolve_pinned(host: str, port: int) -> List[str]:
    """
    Async DNS resolution requiring EVERY returned address to be safe and globally routable.
    Rejects NAT64 (64:ff9b::/96), 6to4 (2002::/16), CGNAT (100.64.0.0/10),
    loopback, private RFC1918, link-local, multicast, and unwraps IPv4-mapped IPv6.

    Returns a list of validated IP literal strings.
    Raises PermissionError if any address is non-global or private.
    """
    host_clean = (host or "").strip().lower()
    if not host_clean:
        raise PermissionError("resolve_pinned: empty host")

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host_clean, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise PermissionError(f"resolve_pinned: DNS resolution failed for '{host_clean}': {exc}") from exc

    if not infos:
        raise PermissionError(f"resolve_pinned: no DNS records found for '{host_clean}'")

    valid_ips: List[str] = []
    for info in infos:
        candidate_raw = info[4][0]
        try:
            addr = _unwrap_ip(ipaddress.ip_address(candidate_raw))
        except ValueError as exc:
            raise PermissionError(f"resolve_pinned: invalid IP address candidate '{candidate_raw}'") from exc

        if not is_safe_global_ip(addr):
            _log_warn(
                "ssrf_pinned_resolution_blocked",
                host=host_clean,
                candidate=str(addr),
            )
            raise PermissionError(
                f"resolve_pinned: host '{host_clean}' resolved to non-global address '{addr}'"
            )
        valid_ips.append(str(addr))

    return valid_ips


def assert_safe_outbound_url(url: str, *, purpose: str = "outbound_request") -> None:
    """
    Validate that an outbound URL is safe to request (not SSRF attack).

    Raises PermissionError if the URL is unsafe.
    """
    parsed = urlparse(url)
    policy = _ssrf_policy_config()
    host = (parsed.hostname or "").strip().lower()
    scheme = (parsed.scheme or "").strip().lower()

    # Check scheme
    if scheme not in {"http", "https"}:
        _log_warn("ssrf_blocked_unsupported_scheme", url=url, purpose=purpose, scheme=scheme)
        raise PermissionError(f"{purpose}: unsupported URL scheme '{scheme}'")

    # Block plaintext HTTP unless explicitly allowed
    if scheme == "http" and not policy["allow_http"]:
        _log_warn("ssrf_blocked_http", url=url, purpose=purpose)
        raise PermissionError(f"{purpose}: plaintext HTTP is blocked by policy")

    # Check hostname present
    if not host:
        _log_warn("ssrf_blocked_missing_host", url=url, purpose=purpose)
        raise PermissionError(f"{purpose}: missing hostname")

    # Check allowlist
    allowlist = policy["allowlist"]
    if allowlist:
        if host not in allowlist and not any(host.endswith(f".{item}") for item in allowlist):
            _log_warn(
                "ssrf_blocked_not_allowlisted",
                url=url,
                purpose=purpose,
                host=host,
                allowlist=allowlist,
            )
            raise PermissionError(f"{purpose}: host '{host}' is not allowlisted")

    # Block private/local ranges
    if policy["block_private_ranges"] and _looks_private_or_local(host):
        _log_warn(
            "ssrf_blocked_private_range",
            url=url,
            purpose=purpose,
            host=host,
        )
        raise PermissionError(f"{purpose}: host '{host}' resolves to private/local network space")

    _log_debug("ssrf_url_allowed", url=url, purpose=purpose)


def create_ssrf_safe_http_client(
    base_url: str,
    timeout: float = 30.0,
    purpose: str = "http_request",
) -> httpx.AsyncClient:
    """
    Create an httpx.AsyncClient with SSRF-safe base URL validation and trust_env=False.
    """
    assert_safe_outbound_url(base_url, purpose=purpose)
    return httpx.AsyncClient(base_url=base_url, timeout=timeout, trust_env=False)
