"""
core/auth_middleware.py — Backwards-compatibility re-export shim.

Phase R2.7: canonical auth module moved to middleware/auth.py.
This shim keeps existing imports working during the transition.

All new code should import from middleware.auth directly.
"""

from middleware.auth import (  # noqa: F401
    API_KEY_HEADER,
    PUBLIC_PATHS,
    LOOPBACK_AGENT_PREFIXES,
    _is_loopback_request,
    _is_loopback_agent_request,
    create_api_key_middleware,
)
