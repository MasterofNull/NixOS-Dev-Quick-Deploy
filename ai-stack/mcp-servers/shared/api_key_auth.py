"""Shared API-key primitives for the coordinator and aidb (agent-auth AUTH-S0).

Design: .agents/plans/agent-auth/DESIGN.md section 5.3 (constant-time compare)
and section 8.1 AUTH-S0 (empty-key startup error when AI_STACK_REQUIRE_API_KEY).
"""

from __future__ import annotations

import hmac
import os

REQUIRE_API_KEY_ENV = "AI_STACK_REQUIRE_API_KEY"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def keys_equal(presented: object, expected: object) -> bool:
    """Constant-time key comparison. Empty or non-string values never match."""
    if not isinstance(presented, str) or not isinstance(expected, str):
        return False
    if not presented or not expected:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def api_key_required() -> bool:
    """True when the deployment declares that a key is always provisioned.

    Nix sets this wherever mySystem.secrets.enable is true (asserted for the
    AI stack), so an empty key there is a provisioning fault, not a dev mode.
    """
    return os.environ.get(REQUIRE_API_KEY_ENV, "").strip().lower() in _TRUTHY


def assert_key_provisioned(key: object, service: str) -> None:
    """Raise at startup when a key is required but empty (fail closed)."""
    if api_key_required() and not (isinstance(key, str) and key.strip()):
        raise RuntimeError(
            f"{service}: {REQUIRE_API_KEY_ENV} is set but no API key was loaded; "
            "refusing to start without authentication"
        )
