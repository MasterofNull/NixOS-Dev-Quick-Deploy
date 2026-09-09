#!/usr/bin/env python3
"""Fail-closed tests for the untrusted AI installer proposal validator (P2-a).

Every case asserts the exact (ok, reason) the validator returns. The AI
proposal is untrusted input: it may only ever express a catalog-enum
selection -- never free text, host_target, authorization/disk/command
fields, or raw Nix/shell content.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB_DIR = REPO / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB_DIR))

import aqos_ai_proposal as proposal  # noqa: E402

CATALOG_PATH = REPO / "config" / "aqos-module-catalog-v1.json"
MODULE_CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

SCHEMA_VERSION = "aqos-install-plan/v1"

CLEAN = {
    "artifact_type": "ai_proposal",
    "schema_version": SCHEMA_VERSION,
    "selection": {
        "golden_profile": "profile.gaming",
        "roles": ["role.gaming"],
        "include_local_ai": False,
    },
}

_failures: list[str] = []
_count = 0


def _bytes(obj) -> bytes:
    return json.dumps(obj).encode("utf-8")


def check(name: str, raw: bytes, expect_ok: bool, expect_reason: str | None = None,
          catalog=MODULE_CATALOG) -> None:
    global _count
    _count += 1
    result = proposal.validate_proposal(raw, catalog)
    ok = result.get("ok")
    if ok != expect_ok:
        _failures.append(f"{name}: expected ok={expect_ok}, got {result!r}")
        return
    if expect_ok:
        return
    reason = result.get("reason")
    if reason != expect_reason:
        _failures.append(f"{name}: expected reason={expect_reason!r}, got {reason!r} ({result!r})")


# 1. Clean proposal is accepted and normalized.
def test_accepts_clean_proposal() -> None:
    global _count
    _count += 1
    result = proposal.validate_proposal(_bytes(CLEAN), MODULE_CATALOG)
    expected = {
        "ok": True,
        "selection": {
            "golden_profile": "profile.gaming",
            "roles": ["role.gaming"],
            "include_local_ai": False,
        },
    }
    if result != expected:
        _failures.append(f"clean proposal: expected {expected!r}, got {result!r}")


def _clean_with(**overrides):
    doc = json.loads(json.dumps(CLEAN))
    doc.update(overrides)
    return doc


def _clean_selection_with(**overrides):
    doc = json.loads(json.dumps(CLEAN))
    doc["selection"].update(overrides)
    return doc


test_accepts_clean_proposal()

# 2. Extra top-level field.
check(
    "extra top-level field",
    _bytes(_clean_with(host_target="hyperd-ai-dev")),
    False, "unknown_field",
)

# 3. Extra selection field.
extra_selection = _clean_with(selection={**CLEAN["selection"], "authorization": "grant"})
check("extra selection field", _bytes(extra_selection), False, "unknown_field")

# 4. Non-enum golden_profile.
check(
    "non-enum golden_profile",
    _bytes(_clean_selection_with(golden_profile="profile.does-not-exist")),
    False, "unknown_profile",
)

# 5. Non-enum role.
check(
    "non-enum role",
    _bytes(_clean_selection_with(roles=["role.does-not-exist"])),
    False, "unknown_role",
)

# 6. include_local_ai as a string.
check(
    "include_local_ai as string",
    _bytes(_clean_selection_with(include_local_ai="true")),
    False, "unknown_field",
)

# 7. A role string carrying shell metacharacters -- rejected before it can
#    ever reach a shell/Nix boundary (not a catalog member either way).
check(
    "role carrying shell metacharacters",
    _bytes(_clean_selection_with(roles=["role.gaming; rm -rf /"])),
    False, "unknown_role",
)

# 8. golden_profile carrying Nix interpolation syntax.
check(
    "golden_profile with ${ interpolation",
    _bytes(_clean_selection_with(golden_profile="profile.${evil}")),
    False, "unknown_profile",
)

# 9. golden_profile carrying a pkgs. reference.
check(
    "golden_profile with pkgs. reference",
    _bytes(_clean_selection_with(golden_profile="pkgs.writeShellScript")),
    False, "unknown_profile",
)

# 10. A role carrying a raw Nix expression.
check(
    "role carrying raw Nix expression",
    _bytes(_clean_selection_with(roles=["import <nixpkgs> {}"])),
    False, "unknown_role",
)

# 11. Non-JSON bytes.
check("non-JSON bytes", b"{not json at all", False, "json_invalid")

# 12. A disk/auth-looking top-level key.
check(
    "disk/auth-looking top-level key",
    _bytes(_clean_with(disk_authorization="wipe")),
    False, "unknown_field",
)

# 13. Wrong artifact_type.
check(
    "wrong artifact_type",
    _bytes(_clean_with(artifact_type="request_plan")),
    False, "unknown_field",
)

# 14. Wrong schema_version.
check(
    "wrong schema_version",
    _bytes(_clean_with(schema_version="aqos-install-plan/v2")),
    False, "unknown_field",
)

# 15. roles not a list.
check(
    "roles not a list",
    _bytes(_clean_selection_with(roles="role.gaming")),
    False, "unknown_role",
)

# 16. golden_profile not a string.
check(
    "golden_profile not a string",
    _bytes(_clean_selection_with(golden_profile=1)),
    False, "unknown_profile",
)

# 17. Defense in depth: even if a malicious catalog entry slipped an unsafe
#     token past the enum-membership check, the recursive string scan over
#     `selection` must still reject it. This proves step 5 is a real,
#     independently-effective layer and not dead code shadowed by step 4.
_poisoned_catalog = {
    "modules": MODULE_CATALOG["modules"] + [
        {"id": "profile.${evil}", "category": "profile"},
    ]
}
check(
    "defense in depth: poisoned catalog entry still rejected as unsafe",
    _bytes(_clean_selection_with(golden_profile="profile.${evil}")),
    False, "unsafe_token",
    catalog=_poisoned_catalog,
)

# 18. Duplicate JSON key.
check(
    "duplicate JSON key",
    b'{"artifact_type":"ai_proposal","artifact_type":"ai_proposal",'
    b'"schema_version":"aqos-install-plan/v1","selection":'
    b'{"golden_profile":"profile.gaming","roles":[],"include_local_ai":false}}',
    False, "json_invalid",
)

# 19. Allowlist regression: poisoned catalog carrying a plain shell variable
#     ("$HOME") -- the exact gap the incomplete denylist missed (it only
#     matched "${" / "$(", not a bare "$"). The allowlist rejects it because
#     "$" is outside [a-z0-9._-].
_poisoned_dollar = {
    "modules": MODULE_CATALOG["modules"] + [
        {"id": "profile.$HOME", "category": "profile"},
    ]
}
check(
    "allowlist: plain $ shell variable rejected as unsafe",
    _bytes(_clean_selection_with(golden_profile="profile.$HOME")),
    False, "unsafe_token",
    catalog=_poisoned_dollar,
)

# 20. Allowlist regression: output redirection ">".
_poisoned_redirect_out = {
    "modules": MODULE_CATALOG["modules"] + [
        {"id": "role.x>out", "category": "role"},
    ]
}
check(
    "allowlist: output redirection > rejected as unsafe",
    _bytes(_clean_selection_with(roles=["role.x>out"])),
    False, "unsafe_token",
    catalog=_poisoned_redirect_out,
)

# 21. Allowlist regression: input redirection "<".
_poisoned_redirect_in = {
    "modules": MODULE_CATALOG["modules"] + [
        {"id": "role.x<in", "category": "role"},
    ]
}
check(
    "allowlist: input redirection < rejected as unsafe",
    _bytes(_clean_selection_with(roles=["role.x<in"])),
    False, "unsafe_token",
    catalog=_poisoned_redirect_in,
)

# 22. Allowlist regression: secret-shaped value (uppercase AWS-style access
#     key id) -- rejected because uppercase letters are outside the
#     lowercase-only allowlist charset.
_poisoned_secret = {
    "modules": MODULE_CATALOG["modules"] + [
        {"id": "profile.AKIAIOSFODNN7EXAMPLE", "category": "profile"},
    ]
}
check(
    "allowlist: secret-shaped uppercase value rejected as unsafe",
    _bytes(_clean_selection_with(golden_profile="profile.AKIAIOSFODNN7EXAMPLE")),
    False, "unsafe_token",
    catalog=_poisoned_secret,
)

# 23. Allowlist regression: whitespace inside the value.
_poisoned_whitespace = {
    "modules": MODULE_CATALOG["modules"] + [
        {"id": "profile.a b", "category": "profile"},
    ]
}
check(
    "allowlist: whitespace value rejected as unsafe",
    _bytes(_clean_selection_with(golden_profile="profile.a b")),
    False, "unsafe_token",
    catalog=_poisoned_whitespace,
)

# 24. Allowlist regression: lowercase-hex secret-shaped golden_profile value
#     with NO "profile." prefix -- matches the charset [a-z0-9._-] but is
#     rejected because it lacks the required category prefix.
_poisoned_hex_profile = {
    "modules": MODULE_CATALOG["modules"] + [
        {"id": "deadbeefcafe0123feedface", "category": "profile"},
    ]
}
check(
    "allowlist: lowercase-hex secret-shaped value rejected (no prefix)",
    _bytes(_clean_selection_with(golden_profile="deadbeefcafe0123feedface")),
    False, "unsafe_token",
    catalog=_poisoned_hex_profile,
)

# 25. Allowlist regression: lowercase secret-shaped role value with no
#     "role." prefix.
_poisoned_hex_role = {
    "modules": MODULE_CATALOG["modules"] + [
        {"id": "abcdef0123456789abcdef", "category": "role"},
    ]
}
check(
    "allowlist: lowercase secret-shaped role rejected (no prefix)",
    _bytes(_clean_selection_with(roles=["abcdef0123456789abcdef"])),
    False, "unsafe_token",
    catalog=_poisoned_hex_role,
)

# 26. Allowlist regression: bare golden_profile missing the "profile." prefix
#     entirely (e.g. an attacker-poisoned catalog entry that drops the
#     category namespace).
_poisoned_bare = {
    "modules": MODULE_CATALOG["modules"] + [
        {"id": "gaming", "category": "profile"},
    ]
}
check(
    "allowlist: bare value missing profile. prefix rejected",
    _bytes(_clean_selection_with(golden_profile="gaming")),
    False, "unsafe_token",
    catalog=_poisoned_bare,
)

# 27. Allowlist does not over-reject a real hyphenated catalog id.
check(
    "allowlist: clean hyphenated catalog id accepted",
    _bytes(_clean_selection_with(
        golden_profile="profile.aqos-workstation",
        roles=["role.cpp-dev", "role.ai-stack"],
    )),
    True,
)

if _failures:
    for failure in _failures:
        print(f"FAIL: {failure}")
    print(f"test-aqos-ai-proposal: ok {_count - len(_failures)}/{_count}")
    sys.exit(1)

print(f"test-aqos-ai-proposal: ok {_count}/{_count}")
