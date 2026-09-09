#!/usr/bin/env python3
"""Fail-closed validator for untrusted AI installer proposals (P2-a).

The AI proposal is UNTRUSTED input: it may only ever express a selection
(golden_profile / roles / include_local_ai) drawn from the digest-pinned
module catalog. Raw Nix/shell/secrets/disk-authorization content must be
impossible to pass through. This module never raises on bad input --
every failure path returns {"ok": False, "reason": "..."}.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aqos_install_resolver as resolver  # noqa: E402

# Complete-by-construction allowlist: legit catalog IDs are always either a
# golden_profile "profile.*" or a role "role.*", e.g.
# "profile.aqos-workstation", "role.ai-stack", "role.cpp-dev". Requiring the
# category prefix (not just the charset) rejects bare secret-shaped tokens
# with no prefix (e.g. a lowercase-hex string) in addition to anything
# outside [a-z0-9._-] (plain "$", redirection ">"/"<", whitespace, ";", "|",
# backticks, "${", "$(", "/", "\\", uppercase, or any other character) --
# there is no denylist to keep in sync with new injection heuristics.
_ALLOWED_STRING = re.compile(r"^(profile|role)\.[a-z0-9._-]+$")
_MAX_STRING_LEN = 64


def _is_unsafe_string(value: str) -> bool:
    if len(value) > _MAX_STRING_LEN:
        return True
    return _ALLOWED_STRING.fullmatch(value) is None


def _scan_unsafe(value: Any) -> bool:
    """Recursively scan every string VALUE for injection heuristics.

    Mapping keys are intentionally not scanned: at the only call site
    (validate_proposal Step 5) the mapping is `selection`, whose keyset is
    already closed-set validated against the fixed schema names
    {"golden_profile", "roles", "include_local_ai"} in Step 2 -- those key
    strings are schema structure, not attacker-controlled catalog-ID values,
    so they must not be held to the catalog-ID "profile."/"role." allowlist.
    """
    if isinstance(value, str):
        return _is_unsafe_string(value)
    if isinstance(value, Mapping):
        return any(_scan_unsafe(val) for val in value.values())
    if isinstance(value, (list, tuple)):
        return any(_scan_unsafe(item) for item in value)
    return False


def _catalog_ids(module_catalog: Mapping[str, Any], category: str) -> set[str]:
    return {
        entry.get("id")
        for entry in module_catalog.get("modules", [])
        if entry.get("category") == category
    }


def validate_proposal(raw: bytes, module_catalog: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an untrusted AI proposal.

    Returns {"ok": True, "selection": {...normalized...}} on success, or
    {"ok": False, "reason": "<why>"} on any failure. Never raises.
    """
    # Step 1: strict JSON parse (rejects duplicate keys, non-finite numbers).
    try:
        parsed = resolver.parse_json_strict(raw)
    except resolver.ResolverError:
        return {"ok": False, "reason": "json_invalid"}
    except Exception:
        return {"ok": False, "reason": "json_invalid"}

    if not isinstance(parsed, Mapping):
        return {"ok": False, "reason": "unknown_field"}

    # Step 2: closed top-level shape.
    allowed_top = {"artifact_type", "schema_version", "selection"}
    if set(parsed.keys()) - allowed_top:
        return {"ok": False, "reason": "unknown_field"}
    if not {"artifact_type", "schema_version", "selection"} <= set(parsed.keys()):
        return {"ok": False, "reason": "unknown_field"}

    selection = parsed.get("selection")
    if not isinstance(selection, Mapping):
        return {"ok": False, "reason": "unknown_field"}
    allowed_selection = {"golden_profile", "roles", "include_local_ai"}
    if set(selection.keys()) - allowed_selection:
        return {"ok": False, "reason": "unknown_field"}
    if not allowed_selection <= set(selection.keys()):
        return {"ok": False, "reason": "unknown_field"}

    # Step 3: artifact_type / schema_version pin.
    if parsed.get("artifact_type") != "ai_proposal":
        return {"ok": False, "reason": "unknown_field"}
    if parsed.get("schema_version") != resolver.SCHEMA_VERSION:
        return {"ok": False, "reason": "unknown_field"}

    # Step 4: catalog-membership + type checks.
    golden_profile = selection.get("golden_profile")
    roles = selection.get("roles")
    include_local_ai = selection.get("include_local_ai")

    if not isinstance(golden_profile, str):
        return {"ok": False, "reason": "unknown_profile"}
    profile_ids = _catalog_ids(module_catalog, "profile")
    if golden_profile not in profile_ids:
        return {"ok": False, "reason": "unknown_profile"}

    if not isinstance(roles, list):
        return {"ok": False, "reason": "unknown_role"}
    role_ids = _catalog_ids(module_catalog, "role")
    for role in roles:
        if not isinstance(role, str) or role not in role_ids:
            return {"ok": False, "reason": "unknown_role"}

    if not isinstance(include_local_ai, bool):
        return {"ok": False, "reason": "unknown_field"}

    # Step 5: defense in depth -- scan every string value inside the selection
    # for injection heuristics. (artifact_type/schema_version are already
    # pinned consts checked above; scanning them would reject the fixed
    # "aqos-install-plan/v1" version string on its "/".)
    if _scan_unsafe(selection):
        return {"ok": False, "reason": "unsafe_token"}

    normalized = {
        "golden_profile": golden_profile,
        "roles": sorted(set(roles)),
        "include_local_ai": include_local_ai,
    }
    return {"ok": True, "selection": normalized}
