#!/usr/bin/env python3
"""Registers the `aqos-install-resolve` runbook into the Approval Control
Plane's `approval_request.RUNBOOK_REGISTRY` (P2-c).

This is the ONLY place the installer's "AI/guided proposes, human approves"
flow touches the resolve step: `approval_executor.execute_request()` calls
`RUNBOOK_REGISTRY[runbook].effect(**params)` ONLY once a record's
`status == "approved"` (see that module's docstring for the full audited
contract -- hash-verify, resolve, execute, transition). The effect
registered here is the SAME engine every other adapter uses --
`aqos_install_resolver.normalize_adapter("ai", ...)` ->
`resolve_plan` -> `compile_projection` -- so an approved request resolves
to the byte-identical lock a manual `aqos-install-resolve --adapter manual`
call with the equivalent selection produces (the "one engine" proof
`test-aqos-adapter-parity.py` already established for guided/ai/manual/
legacy; this module extends the same proof to the approval path).

Importing this module registers the runbook as a side effect (idempotent --
re-import is a no-op). `scripts/ai/aqos-approve-install` and
`scripts/testing/test-aqos-p2c-approve.py` both import it before building or
executing an `aqos-install-resolve` request.

Environment seams (`_HW_LOADER`, `_SOURCE_IDENTITY_LOADER`): the resolver
needs a hardware summary and a verified source identity in addition to the
approved selection. Production defaults mirror
`scripts/ai/aqos-install-resolve` exactly (live `hw_probe.probe_hardware`,
live `aqos_install_resolver.collect_source_identity` against this checked-
out repo). Tests swap both module-level callables for fixed fixtures (same
pattern `aqos_ai_propose.py` uses for its `_post_chat` HTTP seam) so the
byte-identity proof is fully offline and reproducible -- no live git/hw
state, no network, matching the "mock any live approval" test contract.

`declared_effects`/`required_authority`/`risk_class`/`reversible` are
registry-owned (never caller-supplied), same as every other
`RUNBOOK_REGISTRY` entry -- see `approval_request.py`'s module docstring for
why that binding matters. Nothing this runbook's effect does writes to disk
or touches Nix/systemd: `resolve_plan`/`compile_projection` are pure
computations over already-verified inputs, and `compile_projection` itself
keeps `executor.executable = False` at this P0 stage (see that function's
docstring) -- so even an approved-and-executed request here produces an
INERT resolved lock + projection, never a live mutation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import approval_request as AR  # noqa: E402
import aqos_install_resolver as resolver  # noqa: E402

_REPO_ROOT = _LIB.parents[2]

RUNBOOK_NAME = "aqos-install-resolve"

# Printable ASCII + newline, bounded length -- covers every character
# `aqos_install_diff.render_selection_diff` can produce (catalog labels,
# fixed English phrasing, "->", punctuation). `approval_request.validate()`
# independently re-scans the rendered `summary.what` for privacy leaks
# regardless of this pattern (defense in depth).
_DIFF_PATTERN = r"[\x20-\x7e\n]{1,4000}"

# Compact `json.dumps(selection, sort_keys=True, separators=(",", ":"))`
# output only ever uses this charset for the three fixed selection keys
# (`golden_profile`, `roles`, `include_local_ai`) and catalog-id values
# (`profile.*` / `role.*`, `[a-z0-9._-]+` per `aqos_ai_proposal.py`).
_SELECTION_JSON_PATTERN = r'[a-z0-9.\-_,:\[\]{}"]{2,2000}'

_PARAM_SCHEMA: dict[str, dict[str, Any]] = {
    "diff": {"type": "str", "pattern": _DIFF_PATTERN},
    "selection_json": {"type": "str", "pattern": _SELECTION_JSON_PATTERN},
    # Reuse the registry's own host/service identifier pattern rather than
    # inventing a second one (minimal-code).
    "host_target": {"type": "str", "pattern": AR.SERVICE_NAME_PATTERN},
}

_SCHEMA_PATH = _REPO_ROOT / "config" / "schemas" / "aqos-install-plan-v1.schema.json"
_MODULE_CATALOG_PATH = _REPO_ROOT / "config" / "aqos-module-catalog-v1.json"
_AI_CATALOG_PATH = _REPO_ROOT / "config" / "aqos-ai-fit-policy-catalog-v1.json"
_FIELDSET_PATH = _REPO_ROOT / "config" / "aqos-mysystem-fieldset-v1.json"

_SELECTION_KEYS = frozenset({"golden_profile", "roles", "include_local_ai"})


def _load_static_environment() -> tuple[dict, dict, bytes, bytes, bytes]:
    """The digest-pinned, on-disk parts of the resolver's input -- schema +
    module catalog + AI-fit catalog + mySystem field-set. Deterministic
    given the checked-out repo; the SAME four files
    `scripts/ai/aqos-install-resolve` reads for a manual resolve, so an
    approved request and a manual one are comparing apples to apples."""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    module_bytes = _MODULE_CATALOG_PATH.read_bytes()
    ai_bytes = _AI_CATALOG_PATH.read_bytes()
    fieldset_bytes = _FIELDSET_PATH.read_bytes()
    module_catalog = resolver.parse_json_strict(module_bytes)
    return schema, module_catalog, module_bytes, ai_bytes, fieldset_bytes


def _default_hw_loader() -> dict[str, Any]:
    try:
        import hw_probe  # sibling module in scripts/ai/lib
    except Exception:  # noqa: BLE001 - hw probing is best-effort, never fatal here
        return {}
    try:
        return hw_probe.probe_hardware(repo_root=_REPO_ROOT)
    except Exception:  # noqa: BLE001 - same
        return {}


def _default_source_identity_loader(host_target: str) -> dict[str, Any]:
    nix_system = resolver._nix_system(_REPO_ROOT)
    flake_installable = f"path:{_REPO_ROOT}#nixosConfigurations.{host_target}"
    return resolver.collect_source_identity(
        _REPO_ROOT, host_target, nix_system, flake_installable, system_probe=lambda: nix_system
    )


# Module-level seams -- production defaults above; tests monkeypatch these
# two names directly (`aqos_install_runbook._HW_LOADER = ...`) to run the
# byte-identity proof fully offline. No other part of this module is
# test-specific.
_HW_LOADER: Callable[[], dict[str, Any]] = _default_hw_loader
_SOURCE_IDENTITY_LOADER: Callable[[str], dict[str, Any]] = _default_source_identity_loader


def _effect_aqos_install_resolve(*, diff: str, selection_json: str, host_target: str) -> dict[str, Any]:
    """The runbook's effect -- called ONLY by `approval_executor.execute_request`
    on an already hash-verified, `status == "approved"` record (review finding
    #9: no parameter this function sees was ever injected outside that
    hash-verified record). Runs the SAME engine every adapter runs:
    `normalize_adapter("ai", ...)` -> `resolve_plan` -> `compile_projection`.
    `diff` is accepted but not re-used here (it already did its job -- it is
    what the human read in `summary.what` before approving); it is part of
    the signature only because it is one of this runbook's registered
    params (bound into the record's canonical hash together with
    `selection_json`/`host_target`, so a tampered diff invalidates the hash
    the executor checks before this function is ever called)."""
    del diff  # already served its purpose as the approved summary text

    parsed = resolver.parse_json_strict(selection_json)
    if not isinstance(parsed, dict) or set(parsed.keys()) != _SELECTION_KEYS:
        raise ValueError("selection_json does not match the expected selection shape")

    request = resolver.normalize_adapter("ai", {"proposal": parsed, "host_target": host_target})
    schema, module_catalog, module_bytes, ai_bytes, fieldset_bytes = _load_static_environment()
    hw = _HW_LOADER()
    source_identity = _SOURCE_IDENTITY_LOADER(host_target)

    lock = resolver.resolve_plan(
        request, hw, module_catalog, module_bytes, ai_bytes, fieldset_bytes, schema, source_identity
    )
    projection = resolver.compile_projection(lock, module_catalog, fieldset_bytes)

    return {
        "runbook": RUNBOOK_NAME,
        "host_target": host_target,
        "resolved_lock_sha256": resolver.sha256_bytes(resolver.jcs_bytes(lock)),
        "resolved_lock": lock,
        "projection": projection,
    }


_SPEC = AR.RunbookSpec(
    name=RUNBOOK_NAME,
    required_authority="owner-webauthn",
    risk_class="medium",
    reversible=True,
    declared_effects=("validate-proposal", "normalize-adapter", "resolve-plan", "compile-projection"),
    param_schema=_PARAM_SCHEMA,
    title_template="Apply the proposed installer selection",
    what_template="{diff}",
    why_template=(
        "This selection only takes effect on {host_target} after you approve it here; "
        "nothing is applied until then."
    ),
    effect=_effect_aqos_install_resolve,
)

# Typed, safe-handler-table style registration -- a literal dict assignment
# of a `RunbookSpec` dataclass, never eval/exec. Idempotent: re-importing
# this module (e.g. from both the CLI and the test suite) overwrites the
# entry with an identical spec rather than raising or duplicating it.
AR.RUNBOOK_REGISTRY[RUNBOOK_NAME] = _SPEC
