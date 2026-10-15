"""
middleware/http_guard.py — browser-origin guard for the hybrid-coordinator (AUTH-S0).

Closes DNS-rebinding and CSRF against the loopback-trusted API surface:
  1. Host allowlist (every request): loopback names/addresses only, plus
     AQ_COORD_ALLOWED_HOSTS extras.
  2. Origin allowlist: any request carrying Origin must match an allowed origin
     (same-service loopback origin, or AQ_COORD_ALLOWED_ORIGINS). No Origin
     (MCP bridge, CLI, services) is allowed.
  3. State-changing methods with a body must be application/json (a cross-site
     text/plain or form POST is a CORS "simple request" with no preflight).
  4. Sec-Fetch-Site: cross-site is rejected for all methods.

Mode via AQ_COORD_HTTP_GUARD: enforce (default) | shadow (log only) | off.
Env is read per request so the kill switch needs no code change.
"""

import logging
import os
from typing import Optional
from urllib.parse import urlsplit

from aiohttp import web

logger = logging.getLogger("hybrid-coordinator.http_guard")

STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

try:  # metrics are optional (tests / minimal imports)
    from prometheus_client import Counter

    HTTP_GUARD_REJECTIONS = Counter(
        "hybrid_http_guard_rejections_total",
        "Requests rejected (or would-be rejected in shadow mode) by the HTTP guard",
        ["reason", "mode"],
    )
except Exception:  # noqa: BLE001
    HTTP_GUARD_REJECTIONS = None


def _mode() -> str:
    mode = os.getenv("AQ_COORD_HTTP_GUARD", "enforce").strip().lower()
    return mode if mode in {"enforce", "shadow", "off"} else "enforce"


def _csv_env(name: str) -> set:
    return {v.strip().lower() for v in os.getenv(name, "").split(",") if v.strip()}


def _own_port() -> Optional[int]:
    raw = os.getenv("MCP_SERVER_PORT") or os.getenv("PORT") or ""
    return int(raw) if raw.isdigit() else None


def _split_host(value: str) -> tuple:
    """Return (hostname, port|None) from a Host header or URL netloc."""
    value = value.strip().lower()
    if value.startswith("["):
        host, _, rest = value[1:].partition("]")
        port = rest[1:] if rest.startswith(":") else ""
    elif value.count(":") == 1:
        host, _, port = value.partition(":")
    else:  # bare name, or unbracketed IPv6
        host, port = value, ""
    return host, (int(port) if port.isdigit() else None)


def _host_allowed(host_header: str) -> bool:
    if not host_header:  # HTTP/1.0 without Host; rebinding always sends one
        return True
    if host_header.strip().lower() in _csv_env("AQ_COORD_ALLOWED_HOSTS"):
        return True
    host, port = _split_host(host_header)
    if host not in LOOPBACK_HOSTS:
        return False
    own = _own_port()
    if port is None:
        return True
    return own is not None and port == own  # unknown own port: fail closed on explicit ports


def _origin_allowed(origin: str) -> bool:
    """Exact, canonical match only: browsers always send scheme://host[:port]
    in lower case with no path, so anything else is not a real browser Origin."""
    origin = origin.strip()
    if origin in {v.strip() for v in os.getenv("AQ_COORD_ALLOWED_ORIGINS", "").split(",") if v.strip()}:
        return True
    parts = urlsplit(origin)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return False  # includes "null"
    if origin != f"{parts.scheme}://{parts.netloc}" or origin != origin.lower():
        return False
    host, port = _split_host(parts.netloc)
    own = _own_port()
    return host in LOOPBACK_HOSTS and own is not None and port == own


def _is_json_content_type(content_type: str) -> bool:
    ctype = content_type.split(";", 1)[0].strip().lower()
    return ctype == "application/json" or (ctype.startswith("application/") and ctype.endswith("+json"))


def check_request(request: web.Request) -> Optional[tuple]:
    """Return (reason, status, hint) when the request violates the guard, else None."""
    headers = request.headers
    if not _host_allowed(headers.get("Host", "")):
        return ("host_not_allowed", 421,
                "Use http://127.0.0.1:<port> or http://localhost:<port>; add other names via AQ_COORD_ALLOWED_HOSTS.")
    origin = headers.get("Origin")
    if origin is not None and not _origin_allowed(origin):
        return ("origin_not_allowed", 403,
                "Cross-origin browser requests are refused; call from a non-browser client or add the origin to AQ_COORD_ALLOWED_ORIGINS.")
    if headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
        # Browsers send this on cross-site no-cors GETs too, which carry no Origin.
        return ("cross_site_request", 403, "Cross-site requests are refused.")
    if request.method in STATE_CHANGING_METHODS:
        if request.body_exists and not _is_json_content_type(headers.get("Content-Type", "")):
            return ("content_type_not_json", 415, "State-changing requests must send Content-Type: application/json.")
    return None


def create_http_guard_middleware():
    """Return the aiohttp middleware implementing the guard.

    Raises RuntimeError at startup (unless mode is off) when the service port
    is unknown: the Host port check and own-origin match depend on it. The
    server already requires MCP_SERVER_PORT, which is where the app binds.
    """
    mode = _mode()
    if mode != "enforce":
        logger.warning("http_guard mode=%s: DNS-rebinding/CSRF protection is %s",
                       mode, "log-only" if mode == "shadow" else "DISABLED")
    if mode != "off" and _own_port() is None:
        raise RuntimeError(
            "http_guard: MCP_SERVER_PORT (or PORT) must be set to the coordinator's "
            "listening port; set AQ_COORD_HTTP_GUARD=off to bypass explicitly."
        )

    @web.middleware
    async def http_guard_middleware(request: web.Request, handler):
        mode = _mode()
        if mode == "off":
            return await handler(request)
        violation = check_request(request)
        if violation is None:
            return await handler(request)
        reason, status, hint = violation
        logger.warning(
            "http_guard %s reason=%s method=%s path=%s host=%s origin=%s",
            "rejected" if mode == "enforce" else "would_reject",
            reason, request.method, request.path,
            request.headers.get("Host", ""), request.headers.get("Origin", ""),
        )
        if HTTP_GUARD_REJECTIONS is not None:
            HTTP_GUARD_REJECTIONS.labels(reason, mode).inc()
        if mode == "shadow":
            return await handler(request)
        return web.json_response({"error": reason, "hint": hint}, status=status)

    return http_guard_middleware
