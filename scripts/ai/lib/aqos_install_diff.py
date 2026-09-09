#!/usr/bin/env python3
"""Plain-language semantic diff for an AQ-OS installer selection (P2-c).

Renders the human-facing "what will change" text a
`aq.approval-request.v1` request (see `approval_request.py`) carries in its
`summary` layer -- the ONLY thing a human sees before approving an AI or
guided installer proposal. This module is PURE: it takes two already-
validated selections (`{"golden_profile", "roles", "include_local_ai"}`,
the shape `aqos_ai_proposal.validate_proposal` returns) plus the module
catalog for human-readable labels, and returns a string. No I/O, no
subprocess, no side effects -- so it is trivially unit-testable and cannot
itself be the source of a privacy leak (it never sees a hash, a path, or
any resolver/executor internals).

Privacy contract (mirrors `approval_request.py`'s `summary` boundary): the
returned text MUST NEVER contain a hex digest, a filesystem path, a socket
reference, a key id, or the literal "sha256" -- it is built entirely from
catalog `label` strings, fixed English phrasing, and ON/OFF/verdict words.
`approval_request.validate()` independently re-scans anything rendered into
`summary` for exactly these patterns, so a bug here would be caught at the
record layer too (defense in depth), but this module is written to never
need that backstop.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

# The golden, hardware-tuned default every proposal is diffed against --
# same profile `aqos-guided-install.GOLDEN_PROFILE` uses, AI off by default
# (catalog: "OPTIONAL local AI (off by default)"), no extra roles.
SAFE_DEFAULT_SELECTION: dict[str, Any] = {
    "golden_profile": "profile.aqos-workstation",
    "roles": [],
    "include_local_ai": False,
}

_SELECTION_KEYS = frozenset({"golden_profile", "roles", "include_local_ai"})


def _label(module_catalog: Mapping[str, Any], module_id: Optional[str]) -> str:
    """Best-effort human label for a catalog id; falls back to the raw id
    (still plain text, never a hash) if the catalog has no entry for it."""
    if not module_id:
        return "(none)"
    for entry in module_catalog.get("modules", []):
        if entry.get("id") == module_id:
            label = entry.get("label")
            if isinstance(label, str) and label:
                return label
    return module_id


def render_selection_diff(
    proposed_selection: Mapping[str, Any],
    default_selection: Mapping[str, Any],
    module_catalog: Mapping[str, Any],
    *,
    ai_fit: Optional[Mapping[str, Any]] = None,
) -> str:
    """Plain-language diff of `proposed_selection` against `default_selection`.

    `ai_fit` is the OPTIONAL AI-fit verdict dict (same shape
    `ai_fit.evaluate_fit` / `aqos-guided-install.ai_decision` return, i.e. it
    has a `"verdict"` key in {"recommended", "limited", "not_advised"}) --
    when the proposal turns local AI ON and hardware is `limited` or
    `not_advised`, a one-line honesty note is appended. Pass `None` (the
    default) when no hardware-fit evaluation is available; no note is added.

    Returns one line per changed dimension (profile / roles / local AI), or
    the single sentence "No change from the safe default..." when the
    proposal is identical to `default_selection` in every dimension.
    """
    proposed_profile = proposed_selection.get("golden_profile")
    default_profile = default_selection.get("golden_profile")
    proposed_roles = set(proposed_selection.get("roles") or [])
    default_roles = set(default_selection.get("roles") or [])
    proposed_ai = bool(proposed_selection.get("include_local_ai"))
    default_ai = bool(default_selection.get("include_local_ai"))

    added = sorted(proposed_roles - default_roles)
    removed = sorted(default_roles - proposed_roles)
    profile_changed = proposed_profile != default_profile
    roles_changed = bool(added or removed)
    ai_changed = proposed_ai != default_ai

    if not profile_changed and not roles_changed and not ai_changed:
        return "No change from the safe default -- this proposal matches the golden default exactly."

    lines: list[str] = []

    if profile_changed:
        lines.append(
            f"Profile: {_label(module_catalog, default_profile)} "
            f"-> {_label(module_catalog, proposed_profile)}"
        )
    else:
        lines.append(f"Profile: no change (stays {_label(module_catalog, proposed_profile)})")

    if roles_changed:
        if added:
            lines.append("Roles added: " + ", ".join(_label(module_catalog, r) for r in added))
        if removed:
            lines.append("Roles removed: " + ", ".join(_label(module_catalog, r) for r in removed))
    else:
        lines.append("Roles: no change")

    if ai_changed:
        lines.append("Local AI: OFF -> ON" if proposed_ai else "Local AI: ON -> OFF")
    else:
        lines.append(f"Local AI: no change (stays {'ON' if proposed_ai else 'OFF'})")

    if proposed_ai and ai_fit is not None:
        verdict = ai_fit.get("verdict")
        if verdict == "not_advised":
            lines.append(
                "Honesty note: this hardware is rated NOT ADVISED for local AI "
                "-- expect it to be unusable."
            )
        elif verdict == "limited":
            lines.append(
                "Honesty note: this hardware is rated LIMITED for local AI "
                "-- it will be slower than recommended."
            )

    return "\n".join(lines)
