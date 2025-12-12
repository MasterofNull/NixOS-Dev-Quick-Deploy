"""API Response Caching Middleware for AI-Optimizer
Caches GET requests to improve performance and reduce database load.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import redis.asyncio as redis


class CacheMiddleware(BaseHTTPMiddleware):
    """Middleware to cache GET requests in Redis."""

    # Paths that should be cached
    CACHEABLE_PATHS = [
        '/health',
        '/skills',
        '/documents',
        '/metrics',
    ]

    # Default TTL for cached responses (seconds)
    DEFAULT_TTL = 300  # 5 minutes

    # Path-specific TTLs
    TTL_MAP = {
        '/health': 30,      # 30 seconds
        '/skills': 600,     # 10 minutes
        '/documents': 300,  # 5 minutes
        '/metrics': 60,     # 1 minute
    }

    def __init__(self, app, redis_url: str = "redis://redis:6379"):
        super().__init__(app)
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

    def _should_cache(self, request: Request) -> bool:
        """Determine if this request should be cached."""
        if request.method != "GET":
            return False

        path = request.url.path
        return any(path.startswith(cacheable) for cacheable in self.CACHEABLE_PATHS)

    def _get_cache_key(self, request: Request) -> str:
        """Generate a unique cache key for the request."""
        # Include path + query parameters in cache key
        url_str = str(request.url)
        key_hash = hashlib.md5(url_str.encode()).hexdigest()
        return f"api:cache:{key_hash}"

    def _get_ttl(self, request: Request) -> int:
        """Get the TTL for this request path."""
        path = request.url.path
        for cached_path, ttl in self.TTL_MAP.items():
            if path.startswith(cached_path):
                return ttl
        return self.DEFAULT_TTL

    async def dispatch(self, request: Request, call_next):
        """Process the request and cache if applicable."""

        # Skip caching if not applicable
        if not self._should_cache(request):
            return await call_next(request)

        cache_key = self._get_cache_key(request)

        # Try to get from cache
        try:
            cached = await self.redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                return JSONResponse(
                    content=data,
                    headers={"X-Cache": "HIT", "X-Cache-Key": cache_key}
                )
        except Exception:
            # Cache read failed, continue to upstream
            pass

        # Call the actual endpoint
        response = await call_next(request)

        # Cache successful GET responses
        if request.method == "GET" and response.status_code == 200:
            try:
                # Read response body
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk

                # Try to parse as JSON
                try:
                    data = json.loads(body)
                    ttl = self._get_ttl(request)

                    # Store in cache
                    await self.redis_client.setex(
                        cache_key,
                        ttl,
                        json.dumps(data)
                    )

                    # Return response with cache header
                    return JSONResponse(
                        content=data,
                        status_code=response.status_code,
                        headers={"X-Cache": "MISS", "X-Cache-TTL": str(ttl)}
                    )
                except json.JSONDecodeError:
                    # Not JSON, return as-is
                    return Response(
                        content=body,
                        status_code=response.status_code,
                        headers=dict(response.headers)
                    )

            except Exception:
                # Caching failed, return original response
                pass

        return response

    async def close(self):
        """Clean up Redis connection."""
        await self.redis_client.aclose()
