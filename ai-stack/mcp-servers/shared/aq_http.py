"""
aq_http: Resilient HTTP-over-UDS client helper (AUTH-S3/AUTH-S4).

Supports connecting to Unix Domain Sockets with one-shot retry for peer_gone races.
"""

from contextlib import asynccontextmanager
import logging
from typing import Any, AsyncIterator, Dict, Optional
import httpx

logger = logging.getLogger(__name__)


class AqHttpClient:
    """Async HTTP client targeting Unix Domain Sockets with peer_gone retry."""

    def __init__(self, uds_path: str, timeout: float = 30.0):
        self.uds_path = uds_path
        self.timeout = timeout
        self.transport = httpx.AsyncHTTPTransport(uds=uds_path)
        self.client = httpx.AsyncClient(
            transport=self.transport,
            base_url="http://localhost",
            timeout=timeout,
        )

    async def aclose(self):
        await self.client.aclose()

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """
        Idempotent GET request with one-shot retry if server returned 403 with reason=peer_gone.
        """
        resp = await self.client.get(url, params=params, headers=headers)
        if resp.status_code == 403:
            try:
                body = resp.json()
                if body.get("reason") == "peer_gone" or body.get("retryable") is True:
                    logger.info("Retrying GET %s due to peer_gone / retryable", url)
                    return await self.client.get(url, params=params, headers=headers)
            except Exception:
                pass
        return resp

    async def post(
        self,
        url: str,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """POST request over UDS."""
        return await self.client.post(url, json=json, headers=headers)


@asynccontextmanager
async def open_aq_client(uds_path: str) -> AsyncIterator[AqHttpClient]:
    client = AqHttpClient(uds_path=uds_path)
    try:
        yield client
    finally:
        await client.aclose()
