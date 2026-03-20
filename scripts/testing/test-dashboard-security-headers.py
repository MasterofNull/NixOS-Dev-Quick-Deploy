#!/usr/bin/env python3
"""Live regression for dashboard HTTP security headers."""

import os
import sys
import urllib.request


BASE_URL = os.getenv("DASHBOARD_API_URL", "http://127.0.0.1:8889").rstrip("/")
EXPECTED_HEADERS = {
    "x-frame-options": "DENY",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
}
EXPECTED_CSP_PARTS = [
    "default-src 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "connect-src 'self' ws: wss:",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
]


def fetch_headers(path: str):
    with urllib.request.urlopen(f"{BASE_URL}{path}") as response:
        return {k.lower(): v for k, v in response.headers.items()}


def validate_headers(path: str) -> None:
    headers = fetch_headers(path)
    missing = []
    for name, expected in EXPECTED_HEADERS.items():
        if headers.get(name) != expected:
            missing.append(f"{name}={headers.get(name)!r}")
    csp = headers.get("content-security-policy", "")
    for fragment in EXPECTED_CSP_PARTS:
        if fragment not in csp:
            missing.append(f"csp-missing:{fragment}")
    if missing:
        raise AssertionError(f"{path} missing/invalid security headers: {', '.join(missing)}")
    print(f"PASS: {path} security headers")


def main() -> int:
    validate_headers("/")
    validate_headers("/api/health")
    print("PASS: dashboard security header regression")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise
