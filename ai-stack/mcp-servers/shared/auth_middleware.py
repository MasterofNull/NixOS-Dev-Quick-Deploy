"""
Unified API Key Authentication Middleware for MCP Servers
==========================================================

Provides reusable authentication components for FastAPI-based MCP servers.
Supports multiple authentication methods and flexible configuration.

Usage:
    from shared.auth_middleware import get_api_key_dependency, require_api_key

    # Create dependency for your service
    require_auth = get_api_key_dependency("MY_SERVICE_API_KEY")

    # Use in FastAPI routes
    @app.get("/protected")
    async def protected_route(api_key: str = Depends(require_auth)):
        return {"status": "authenticated"}

Security Features:
- Supports both x-api-key header and Authorization: Bearer token
- Configurable via environment variables or explicit values
- Constant-time comparison to prevent timing attacks
- Clear error messages for debugging
- Optional authentication (can be disabled for development)

Author: NixOS AI Stack Team
Date: January 2026
"""

import secrets
from typing import Optional
from fastapi import HTTPException, Request, Depends
from fastapi.security import APIKeyHeader, HTTPBearer
import structlog

logger = structlog.get_logger()

# Security schemes
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def constant_time_compare(a: Optional[str], b: Optional[str]) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks.

    Args:
        a: First string
        b: Second string

    Returns:
        True if strings match, False otherwise
    """
    if a is None or b is None:
        return False
    return secrets.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


class APIKeyAuth:
    """
    API Key authentication handler for FastAPI services.

    Can be used as a dependency to protect routes.
    """

    def __init__(
        self,
        service_name: str,
        env_var_name: Optional[str] = None,
        expected_key: Optional[str] = None,
        optional: bool = False
    ):
        """
        Initialize API key authentication.

        Args:
            service_name: Name of the service (for logging)
            env_var_name: Environment variable name containing the API key
            expected_key: Explicit API key (takes precedence over env var)
            optional: If True, allows unauthenticated access when no key is configured
        """
        self.service_name = service_name
        self.env_var_name = env_var_name
        self.optional = optional

        # Load expected key
        self.expected_key = expected_key

        if not self.expected_key and not self.optional:
            logger.warning(
                "auth_key_not_configured",
                service=service_name,
                env_var=env_var_name,
                message="API key not configured - authentication will fail"
            )

    def __call__(
        self,
        request: Request,
        x_api_key: Optional[str] = Depends(api_key_header),
        bearer: Optional[str] = Depends(
            lambda b=Depends(bearer_scheme): b.credentials if b else None
        )
    ) -> str:
        """
        Validate API key from request headers.

        Checks both x-api-key header and Authorization: Bearer token.

        Args:
            request: FastAPI request object
            x_api_key: API key from x-api-key header
            bearer: Token from Authorization: Bearer header

        Returns:
            The validated API key

        Raises:
            HTTPException: 401 if authentication fails
        """
        # If no expected key and optional auth, allow access
        if not self.expected_key:
            if self.optional:
                logger.debug(
                    "auth_optional_skipped",
                    service=self.service_name,
                    path=request.url.path
                )
                return "unauthenticated"
            else:
                logger.error(
                    "auth_key_missing",
                    service=self.service_name,
                    message="API key not configured on server"
                )
                raise HTTPException(
                    status_code=500,
                    detail="Authentication not configured on server"
                )

        # Extract token from headers
        provided_key = x_api_key or bearer

        # Check if token provided
        if not provided_key:
            logger.warning(
                "auth_missing_credentials",
                service=self.service_name,
                path=request.url.path,
                client=request.client.host if request.client else "unknown"
            )
            raise HTTPException(
                status_code=401,
                detail="Missing API key. Provide via x-api-key header or Authorization: Bearer token",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Validate token (constant-time comparison)
        if not constant_time_compare(provided_key, self.expected_key):
            logger.warning(
                "auth_invalid_key",
                service=self.service_name,
                path=request.url.path,
                client=request.client.host if request.client else "unknown",
                key_prefix=provided_key[:8] if len(provided_key) >= 8 else "***"
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Success
        logger.debug(
            "auth_success",
            service=self.service_name,
            path=request.url.path,
            client=request.client.host if request.client else "unknown"
        )
        return provided_key


def get_api_key_dependency(
    service_name: str,
    env_var_name: Optional[str] = None,
    expected_key: Optional[str] = None,
    optional: bool = False
) -> APIKeyAuth:
    """
    Create an API key authentication dependency for FastAPI routes.

    Usage:
        require_auth = get_api_key_dependency(
            service_name="hybrid-coordinator",
            env_var_name="HYBRID_COORDINATOR_API_KEY"
        )

        @app.get("/protected")
        async def protected_route(api_key: str = Depends(require_auth)):
            return {"status": "ok"}

    Args:
        service_name: Name of the service (for logging)
        env_var_name: Environment variable containing the API key
        expected_key: Explicit API key (takes precedence over env var)
        optional: If True, allows unauthenticated access when no key is configured

    Returns:
        APIKeyAuth dependency that can be used with Depends()
    """
    return APIKeyAuth(
        service_name=service_name,
        env_var_name=env_var_name,
        expected_key=expected_key,
        optional=optional
    )


def generate_api_key(length: int = 32) -> str:
    """
    Generate a cryptographically secure random API key.

    Args:
        length: Length of the key in bytes (default: 32)

    Returns:
        Hex-encoded random string (2x length characters)

    Example:
        >>> key = generate_api_key()
        >>> len(key)
        64
    """
    return secrets.token_hex(length)


# Convenience function for simple use cases
def require_api_key(request: Request, expected_key: Optional[str] = None) -> None:
    """
    Simple authentication check for routes.

    Uses explicitly provided expected_key from declarative secret loaders.

    Usage:
        @app.get("/protected")
        async def protected_route(request: Request):
            require_api_key(request)
            return {"status": "ok"}

    Args:
        request: FastAPI request object

    Raises:
        HTTPException: 401 if authentication fails
    """
    if not expected_key:
        return  # Optional auth - no key configured

    # Check headers
    x_api_key = request.headers.get("x-api-key")
    auth_header = request.headers.get("authorization", "")
    bearer_parts = auth_header.split()
    bearer_token = bearer_parts[1] if len(bearer_parts) == 2 and bearer_parts[0].lower() == "bearer" else None

    provided_key = x_api_key or bearer_token

    if not provided_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not constant_time_compare(provided_key, expected_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"}
        )


__all__ = [
    "APIKeyAuth",
    "get_api_key_dependency",
    "generate_api_key",
    "require_api_key",
    "constant_time_compare",
]
