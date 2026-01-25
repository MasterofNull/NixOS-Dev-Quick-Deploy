"""
Authenticated HTTP Client for Inter-Service Communication
==========================================================

Provides httpx client wrappers that automatically include API key authentication
for calls between MCP services.

Usage:
    from shared.auth_http_client import create_authenticated_client

    # Create client with target service's API key
    client = create_authenticated_client("embeddings_api_key")

    # Use like normal httpx client - auth header added automatically
    response = await client.get("http://embeddings:8081/embed")

Security:
- Reads API keys from Docker secrets
- Automatically adds Authorization: Bearer header
- Supports both sync and async clients
- Proper timeout and connection pooling

Author: NixOS AI Stack Team
Date: January 2026
"""

import os
from pathlib import Path
from typing import Optional
import httpx
import structlog

logger = structlog.get_logger()


def load_service_api_key(service_name: str) -> Optional[str]:
    """
    Load API key for a target service from Docker secrets.

    Args:
        service_name: Name of the secret file (e.g., "embeddings_api_key")

    Returns:
        API key string, or None if not found

    Example:
        key = load_service_api_key("embeddings_api_key")
    """
    # Try Docker secret first
    secret_file = f"/run/secrets/{service_name}"
    if Path(secret_file).exists():
        try:
            api_key = Path(secret_file).read_text().strip()
            logger.debug("loaded_api_key_from_secret", service=service_name)
            return api_key
        except Exception as e:
            logger.warning("failed_to_read_secret", service=service_name, error=str(e))

    # Fallback to environment variable (development mode)
    env_var_name = service_name.upper()
    api_key = os.environ.get(env_var_name)
    if api_key:
        logger.debug("loaded_api_key_from_env", service=service_name)
        return api_key

    logger.warning("no_api_key_found", service=service_name,
                   secret_file=secret_file, env_var=env_var_name)
    return None


class AuthenticatedAsyncClient(httpx.AsyncClient):
    """
    Async HTTP client that automatically adds authentication headers.

    This client wraps httpx.AsyncClient and injects the Authorization header
    into all requests.
    """

    def __init__(self, api_key: Optional[str] = None, service_name: Optional[str] = None,
                 **kwargs):
        """
        Initialize authenticated HTTP client.

        Args:
            api_key: Explicit API key to use
            service_name: Service name to load key from secrets (e.g., "embeddings_api_key")
            **kwargs: Additional arguments passed to httpx.AsyncClient

        Example:
            # Using explicit key
            client = AuthenticatedAsyncClient(api_key="abc123...")

            # Using service name (loads from secrets)
            client = AuthenticatedAsyncClient(service_name="embeddings_api_key")
        """
        super().__init__(**kwargs)

        # Load API key
        if api_key:
            self.api_key = api_key
        elif service_name:
            self.api_key = load_service_api_key(service_name)
        else:
            self.api_key = None

        self.service_name = service_name

        # Set up default headers if we have a key
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
            logger.debug("authenticated_client_created", service=service_name)
        else:
            logger.warning("authenticated_client_no_key", service=service_name,
                          message="Client will make unauthenticated requests")


class AuthenticatedClient(httpx.Client):
    """
    Sync HTTP client that automatically adds authentication headers.

    This client wraps httpx.Client and injects the Authorization header
    into all requests.
    """

    def __init__(self, api_key: Optional[str] = None, service_name: Optional[str] = None,
                 **kwargs):
        """
        Initialize authenticated HTTP client.

        Args:
            api_key: Explicit API key to use
            service_name: Service name to load key from secrets (e.g., "embeddings_api_key")
            **kwargs: Additional arguments passed to httpx.Client

        Example:
            # Using explicit key
            client = AuthenticatedClient(api_key="abc123...")

            # Using service name (loads from secrets)
            client = AuthenticatedClient(service_name="embeddings_api_key")
        """
        super().__init__(**kwargs)

        # Load API key
        if api_key:
            self.api_key = api_key
        elif service_name:
            self.api_key = load_service_api_key(service_name)
        else:
            self.api_key = None

        self.service_name = service_name

        # Set up default headers if we have a key
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
            logger.debug("authenticated_client_created", service=service_name)
        else:
            logger.warning("authenticated_client_no_key", service=service_name,
                          message="Client will make unauthenticated requests")


def create_authenticated_client(
    service_name: str,
    timeout: float = 30.0,
    async_client: bool = True,
    **kwargs
) -> httpx.AsyncClient | httpx.Client:
    """
    Factory function to create an authenticated HTTP client.

    Args:
        service_name: Target service's secret name (e.g., "embeddings_api_key")
        timeout: Request timeout in seconds (default: 30.0)
        async_client: If True, return AsyncClient; if False, return sync Client
        **kwargs: Additional arguments for httpx client

    Returns:
        Authenticated httpx client (async or sync)

    Example:
        # Create async client for embeddings service
        client = create_authenticated_client("embeddings_api_key", timeout=60.0)
        response = await client.post("http://embeddings:8081/embed", json=data)

        # Create sync client
        client = create_authenticated_client("aidb_api_key", async_client=False)
        response = client.get("http://aidb:8091/health")
    """
    if async_client:
        return AuthenticatedAsyncClient(
            service_name=service_name,
            timeout=timeout,
            **kwargs
        )
    else:
        return AuthenticatedClient(
            service_name=service_name,
            timeout=timeout,
            **kwargs
        )


# Convenience functions for common services

def create_embeddings_client(timeout: float = 30.0, **kwargs) -> httpx.AsyncClient:
    """Create authenticated client for embeddings service"""
    return create_authenticated_client("embeddings_api_key", timeout=timeout, **kwargs)


def create_aidb_client(timeout: float = 30.0, **kwargs) -> httpx.AsyncClient:
    """Create authenticated client for AIDB service"""
    return create_authenticated_client("aidb_api_key", timeout=timeout, **kwargs)


def create_hybrid_coordinator_client(timeout: float = 30.0, **kwargs) -> httpx.AsyncClient:
    """Create authenticated client for hybrid-coordinator service"""
    return create_authenticated_client("hybrid_coordinator_api_key", timeout=timeout, **kwargs)


def create_container_engine_client(timeout: float = 30.0, **kwargs) -> httpx.AsyncClient:
    """Create authenticated client for container-engine service"""
    return create_authenticated_client("container_engine_api_key", timeout=timeout, **kwargs)


def create_ralph_wiggum_client(timeout: float = 30.0, **kwargs) -> httpx.AsyncClient:
    """Create authenticated client for ralph-wiggum service"""
    return create_authenticated_client("ralph_wiggum_api_key", timeout=timeout, **kwargs)


def create_aider_wrapper_client(timeout: float = 30.0, **kwargs) -> httpx.AsyncClient:
    """Create authenticated client for aider-wrapper service"""
    return create_authenticated_client("aider_wrapper_api_key", timeout=timeout, **kwargs)


def create_nixos_docs_client(timeout: float = 30.0, **kwargs) -> httpx.AsyncClient:
    """Create authenticated client for nixos-docs service"""
    return create_authenticated_client("nixos_docs_api_key", timeout=timeout, **kwargs)


__all__ = [
    "load_service_api_key",
    "AuthenticatedAsyncClient",
    "AuthenticatedClient",
    "create_authenticated_client",
    "create_embeddings_client",
    "create_aidb_client",
    "create_hybrid_coordinator_client",
    "create_container_engine_client",
    "create_ralph_wiggum_client",
    "create_aider_wrapper_client",
    "create_nixos_docs_client",
]
