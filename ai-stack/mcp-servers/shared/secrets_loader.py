"""
Secrets Loader for Docker Secrets
==================================

Utility functions to load sensitive values (passwords, keys) from Docker secrets.

Docker secrets are mounted at /run/secrets/<secret_name> and should be used
instead of environment variables for sensitive data.

Usage:
    from shared.secrets_loader import load_secret, get_postgres_password

    # Load any secret
    api_key = load_secret("my_api_key")

    # Load specific secrets with fallback
    postgres_pw = get_postgres_password()
    redis_pw = get_redis_password()

Author: NixOS AI Stack Team
Date: January 2026
"""

import os
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()


def load_secret(secret_name: str, fallback_env_var: Optional[str] = None) -> Optional[str]:
    """
    Load a secret from Docker secrets or fall back to environment variable.

    Args:
        secret_name: Name of the secret file (e.g., "postgres_password")
        fallback_env_var: Environment variable to check if secret file not found

    Returns:
        Secret value as string, or None if not found

    Example:
        password = load_secret("postgres_password", "POSTGRES_PASSWORD")
    """
    # Try Docker secret first
    secret_path = Path(f"/run/secrets/{secret_name}")
    if secret_path.exists():
        try:
            value = secret_path.read_text().strip()
            logger.debug("loaded_secret_from_file", secret=secret_name)
            return value
        except Exception as e:
            logger.warning("failed_to_read_secret", secret=secret_name, error=str(e))

    # Fall back to environment variable
    if fallback_env_var:
        value = os.environ.get(fallback_env_var)
        if value:
            logger.debug("loaded_secret_from_env", secret=secret_name, env_var=fallback_env_var)
            return value

    logger.warning("secret_not_found", secret=secret_name, env_var=fallback_env_var)
    return None


def get_postgres_password() -> Optional[str]:
    """
    Get PostgreSQL password from Docker secret or environment variable.

    Returns:
        PostgreSQL password, or None if not configured
    """
    return load_secret("postgres_password", "POSTGRES_PASSWORD")


def get_redis_password() -> Optional[str]:
    """
    Get Redis password from Docker secret or environment variable.

    Returns:
        Redis password, or None if not configured
    """
    return load_secret("redis_password", "REDIS_PASSWORD")


def get_grafana_admin_password() -> Optional[str]:
    """
    Get Grafana admin password from Docker secret or environment variable.

    Returns:
        Grafana admin password, or None if not configured
    """
    return load_secret("grafana_admin_password", "GRAFANA_ADMIN_PASSWORD")


def build_postgres_url(
    host: str = "localhost",
    port: int = 5432,
    database: str = "mcp",
    user: str = "mcp",
    password: Optional[str] = None
) -> str:
    """
    Build PostgreSQL connection URL with password from secrets.

    Args:
        host: PostgreSQL host (default: localhost)
        port: PostgreSQL port (default: 5432)
        database: Database name (default: mcp)
        user: Database user (default: mcp)
        password: Password (if None, loads from secrets)

    Returns:
        PostgreSQL connection URL (e.g., "postgresql://user:pass@host:port/db")

    Example:
        url = build_postgres_url(host="postgres", database="aidb")
    """
    if password is None:
        password = get_postgres_password()

    if not password:
        logger.warning("postgres_password_not_found",
                      message="Using connection without password (may fail)")
        return f"postgresql://{user}@{host}:{port}/{database}"

    # URL-encode password to handle special characters
    from urllib.parse import quote_plus
    encoded_password = quote_plus(password)

    return f"postgresql://{user}:{encoded_password}@{host}:{port}/{database}"


def build_redis_url(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    password: Optional[str] = None
) -> str:
    """
    Build Redis connection URL with password from secrets.

    Args:
        host: Redis host (default: localhost)
        port: Redis port (default: 6379)
        db: Redis database number (default: 0)
        password: Password (if None, loads from secrets)

    Returns:
        Redis connection URL (e.g., "redis://:pass@host:port/db")

    Example:
        url = build_redis_url(host="redis", db=0)
    """
    if password is None:
        password = get_redis_password()

    if not password:
        logger.debug("redis_password_not_found",
                    message="Using connection without password")
        return f"redis://{host}:{port}/{db}"

    # URL-encode password to handle special characters
    from urllib.parse import quote_plus
    encoded_password = quote_plus(password)

    return f"redis://:{encoded_password}@{host}:{port}/{db}"


__all__ = [
    "load_secret",
    "get_postgres_password",
    "get_redis_password",
    "get_grafana_admin_password",
    "build_postgres_url",
    "build_redis_url",
]
