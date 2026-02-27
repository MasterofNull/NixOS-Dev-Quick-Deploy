"""
Phase 13.2.2 — SSRF (Server-Side Request Forgery) Protection

Provides URL validation to prevent outbound requests to private/internal networks.
Used by hybrid-coordinator and other MCP servers for safe HTTP client initialization.

Usage:
    from shared.ssrf_protection import assert_safe_outbound_url, create_ssrf_safe_http_client
    
    # Validate URL before use
    assert_safe_outbound_url(url, purpose="llama_cpp_request")
    
    # Or create a pre-validated client
    client = create_ssrf_safe_http_client(base_url=Config.LLAMA_CPP_URL)
"""

import ipaddress
import os
import socket
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
import structlog

logger = structlog.get_logger()


def _ssrf_policy_config() -> Dict[str, Any]:
    """
    Load SSRF policy configuration from environment variables.
    
    Environment variables:
    - HYBRID_OUTBOUND_ALLOWLIST: Comma-separated list of allowed hostnames
    - HYBRID_BLOCK_PRIVATE_EGRESS: Block private/local IP ranges (default: true)
    - HYBRID_ALLOW_PLAINTEXT_HTTP: Allow HTTP (not just HTTPS) (default: false)
    """
    allowed_hosts_raw = os.getenv("HYBRID_OUTBOUND_ALLOWLIST", "").strip()
    allowlist = [item.strip().lower() for item in allowed_hosts_raw.split(",") if item.strip()]
    return {
        "allowlist": allowlist,
        "block_private_ranges": os.getenv("HYBRID_BLOCK_PRIVATE_EGRESS", "true").lower() == "true",
        "allow_http": os.getenv("HYBRID_ALLOW_PLAINTEXT_HTTP", "false").lower() == "true",
    }


def _looks_private_or_local(hostname: str) -> bool:
    """
    Check if a hostname or IP address is in a private/local network range.
    
    Blocks:
    - localhost, .local, .localhost domains
    - Private IP ranges (10.x.x.x, 172.16-31.x.x, 192.168.x.x)
    - Loopback (127.x.x.x)
    - Link-local (169.254.x.x)
    - Multicast (224-239.x.x.x)
    - Reserved/unspecified addresses
    
    Returns True if the host is private/local (should be blocked).
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
        return _is_private_or_special(addr)
    except ValueError:
        pass
    
    # Resolve hostname to IP
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # DNS failures should not bypass policy — block by default
        logger.warning("ssrf_dns_resolution_failed", hostname=host)
        return True
    
    for info in infos:
        candidate = info[4][0]
        try:
            addr = ipaddress.ip_address(candidate)
        except ValueError:
            return True
        if _is_private_or_special(addr):
            return True
    
    return False


def _is_private_or_special(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is private, loopback, link-local, multicast, reserved, or unspecified."""
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def assert_safe_outbound_url(url: str, *, purpose: str = "outbound_request") -> None:
    """
    Validate that an outbound URL is safe to request (not SSRF attack).
    
    Raises PermissionError if the URL is unsafe.
    
    Checks:
    1. URL scheme must be http or https
    2. HTTP (plaintext) blocked unless explicitly allowed
    3. Host must be in allowlist (if allowlist is configured)
    4. Host must not resolve to private/local IP ranges (if block_private_ranges enabled)
    """
    parsed = urlparse(url)
    policy = _ssrf_policy_config()
    host = (parsed.hostname or "").strip().lower()
    scheme = (parsed.scheme or "").strip().lower()
    
    # Check scheme
    if scheme not in {"http", "https"}:
        logger.warning("ssrf_blocked_unsupported_scheme", url=url, purpose=purpose, scheme=scheme)
        raise PermissionError(f"{purpose}: unsupported URL scheme '{scheme}'")
    
    # Block plaintext HTTP unless explicitly allowed
    if scheme == "http" and not policy["allow_http"]:
        logger.warning("ssrf_blocked_http", url=url, purpose=purpose)
        raise PermissionError(f"{purpose}: plaintext HTTP is blocked by policy")
    
    # Check hostname present
    if not host:
        logger.warning("ssrf_blocked_missing_host", url=url, purpose=purpose)
        raise PermissionError(f"{purpose}: missing hostname")
    
    # Check allowlist
    allowlist = policy["allowlist"]
    if allowlist:
        if host not in allowlist and not any(host.endswith(f".{item}") for item in allowlist):
            logger.warning(
                "ssrf_blocked_not_allowlisted",
                url=url,
                purpose=purpose,
                host=host,
                allowlist=allowlist,
            )
            raise PermissionError(f"{purpose}: host '{host}' is not allowlisted")
    
    # Block private/local ranges
    if policy["block_private_ranges"] and _looks_private_or_local(host):
        logger.warning(
            "ssrf_blocked_private_range",
            url=url,
            purpose=purpose,
            host=host,
        )
        raise PermissionError(f"{purpose}: host '{host}' resolves to private/local network space")
    
    logger.debug("ssrf_url_allowed", url=url, purpose=purpose)


def create_ssrf_safe_http_client(
    base_url: str,
    timeout: float = 30.0,
    purpose: str = "http_request",
) -> httpx.AsyncClient:
    """
    Create an httpx.AsyncClient with SSRF-safe base URL validation.
    
    The base_url is validated at client creation time. All subsequent requests
    through this client will use the validated base URL.
    
    Args:
        base_url: The base URL for the HTTP client (validated for SSRF)
        timeout: Request timeout in seconds
        purpose: Purpose string for logging (e.g., "llama_cpp_request")
    
    Returns:
        Configured httpx.AsyncClient instance
    
    Raises:
        PermissionError: If base_url fails SSRF validation
    """
    assert_safe_outbound_url(base_url, purpose=purpose)
    return httpx.AsyncClient(base_url=base_url, timeout=timeout)
