"""
Rate limiting middleware for aiohttp services.

Provides sliding-window rate limiting with tiered limits and configurable policies.

Usage:
    from shared.rate_limiter import create_rate_limiter_middleware, RateLimiterConfig

    config = RateLimiterConfig(
        enabled=True,
        default_rpm=100,
        endpoint_limits={"/query": 30, "/hints": 60},
        burst_multiplier=1.5,
    )
    rate_limiter, middleware = create_rate_limiter_middleware(config)

    app = web.Application(middlewares=[middleware])
"""

import os
import time
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Optional, Set

from aiohttp import web


logger = logging.getLogger("rate-limiter")


@dataclass
class RateLimiterConfig:
    """Configuration for rate limiter."""
    enabled: bool = True
    default_rpm: int = 100
    default_rph: int = 3000
    burst_multiplier: float = 1.5
    endpoint_limits: Dict[str, int] = field(default_factory=dict)
    exempt_paths: Set[str] = field(default_factory=lambda: {"/health", "/metrics"})
    header_name: str = "X-API-Key"
    include_retry_after: bool = True

    @classmethod
    def from_env(cls) -> "RateLimiterConfig":
        """Load configuration from environment variables."""
        return cls(
            enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
            default_rpm=int(os.getenv("RATE_LIMIT_DEFAULT_RPM", "100")),
            default_rph=int(os.getenv("RATE_LIMIT_DEFAULT_RPH", "3000")),
            burst_multiplier=float(os.getenv("RATE_LIMIT_BURST_MULTIPLIER", "1.5")),
        )


class SlidingWindowRateLimiter:
    """Sliding window rate limiter with minute and hour windows."""

    def __init__(self, config: RateLimiterConfig):
        self.config = config
        self._minute_windows: Dict[str, Deque[float]] = defaultdict(deque)
        self._hour_windows: Dict[str, Deque[float]] = defaultdict(deque)
        self._endpoint_windows: Dict[str, Dict[str, Deque[float]]] = defaultdict(lambda: defaultdict(deque))

    def _get_client_id(self, request: web.Request) -> str:
        """Extract client identifier from request."""
        api_key = request.headers.get(self.config.header_name)
        if api_key:
            return f"key:{api_key[:16]}"
        if request.remote:
            return f"ip:{request.remote}"
        return "unknown"

    def _get_endpoint_limit(self, path: str) -> int:
        """Get rate limit for specific endpoint."""
        for pattern, limit in self.config.endpoint_limits.items():
            if path.startswith(pattern):
                return limit
        return self.config.default_rpm

    def check(self, request: web.Request) -> tuple[bool, Optional[str], Optional[int]]:
        """
        Check if request is allowed under rate limits.

        Returns:
            tuple of (allowed, error_message, retry_after_seconds)
        """
        if not self.config.enabled:
            return True, None, None

        path = request.path
        if path in self.config.exempt_paths:
            return True, None, None

        client_id = self._get_client_id(request)
        now = time.time()

        # Check minute window
        minute_window = self._minute_windows[client_id]
        while minute_window and now - minute_window[0] > 60:
            minute_window.popleft()

        rpm_limit = self._get_endpoint_limit(path)
        burst_limit = int(rpm_limit * self.config.burst_multiplier)

        if len(minute_window) >= burst_limit:
            retry_after = int(60 - (now - minute_window[0])) + 1
            logger.warning(
                "rate_limit_exceeded",
                client_id=client_id,
                path=path,
                current=len(minute_window),
                limit=burst_limit,
            )
            return False, f"Rate limit exceeded: {burst_limit}/min", retry_after

        # Check hour window
        hour_window = self._hour_windows[client_id]
        while hour_window and now - hour_window[0] > 3600:
            hour_window.popleft()

        if len(hour_window) >= self.config.default_rph:
            retry_after = int(3600 - (now - hour_window[0])) + 1
            logger.warning(
                "hourly_rate_limit_exceeded",
                client_id=client_id,
                path=path,
                current=len(hour_window),
                limit=self.config.default_rph,
            )
            return False, f"Hourly rate limit exceeded: {self.config.default_rph}/hour", retry_after

        # Check endpoint-specific window
        endpoint_window = self._endpoint_windows[path][client_id]
        while endpoint_window and now - endpoint_window[0] > 60:
            endpoint_window.popleft()

        if len(endpoint_window) >= rpm_limit:
            retry_after = int(60 - (now - endpoint_window[0])) + 1
            return False, f"Endpoint rate limit exceeded: {rpm_limit}/min for {path}", retry_after

        # Record this request
        minute_window.append(now)
        hour_window.append(now)
        endpoint_window.append(now)

        return True, None, None

    def get_stats(self, client_id: Optional[str] = None) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        if client_id:
            return {
                "client_id": client_id,
                "minute_requests": len(self._minute_windows.get(client_id, [])),
                "hour_requests": len(self._hour_windows.get(client_id, [])),
            }

        total_clients = len(self._minute_windows)
        total_minute_requests = sum(len(w) for w in self._minute_windows.values())
        total_hour_requests = sum(len(w) for w in self._hour_windows.values())

        return {
            "total_clients": total_clients,
            "total_minute_requests": total_minute_requests,
            "total_hour_requests": total_hour_requests,
            "config": {
                "enabled": self.config.enabled,
                "default_rpm": self.config.default_rpm,
                "default_rph": self.config.default_rph,
                "burst_multiplier": self.config.burst_multiplier,
            },
        }


def create_rate_limiter_middleware(
    config: Optional[RateLimiterConfig] = None,
) -> tuple[SlidingWindowRateLimiter, Callable]:
    """
    Create a rate limiter and its aiohttp middleware.

    Args:
        config: Rate limiter configuration (defaults to env-based config)

    Returns:
        tuple of (rate_limiter, middleware)
    """
    if config is None:
        config = RateLimiterConfig.from_env()

    limiter = SlidingWindowRateLimiter(config)

    @web.middleware
    async def rate_limit_middleware(
        request: web.Request,
        handler: Callable,
    ) -> web.Response:
        """Rate limiting middleware for aiohttp."""
        allowed, error_msg, retry_after = limiter.check(request)

        if not allowed:
            headers = {}
            if config.include_retry_after and retry_after:
                headers["Retry-After"] = str(retry_after)
                headers["X-RateLimit-Reset"] = str(int(time.time()) + retry_after)

            return web.json_response(
                {
                    "error": error_msg,
                    "retry_after_seconds": retry_after,
                },
                status=429,
                headers=headers,
            )

        response = await handler(request)

        # Add rate limit headers to response
        client_id = limiter._get_client_id(request)
        minute_remaining = config.default_rpm - len(limiter._minute_windows.get(client_id, []))
        response.headers["X-RateLimit-Limit"] = str(config.default_rpm)
        response.headers["X-RateLimit-Remaining"] = str(max(0, minute_remaining))

        return response

    return limiter, rate_limit_middleware
