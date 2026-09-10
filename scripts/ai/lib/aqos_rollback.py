#!/usr/bin/env python3
"""NixOS generation rollback plans and the inert P0 ACP runbook effect."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import approval_request as AR  # noqa: E402
import aqos_install_resolver as resolver  # noqa: E402

_REPO_ROOT = _LIB.parents[2]
DEFAULT_SYSTEM_PROFILE = Path("/nix/var/nix/profiles/system")
DEFAULT_STATE_PATH = _REPO_ROOT / ".agents" / "state" / "aqos-rollback.json"
RUNBOOK_NAME = "aqos-rollback"

_GENERATION_RE = re.compile(r"(?:^|/)system-(\d+)-link(?:/|$)")
_DESCRIPTION_PATTERN = r"[A-Za-z0-9 ,.()'-]{1,240}"
_LOCK_JSON_PATTERN = r"[\x20-\x7e]{2,20000}"


class RollbackDirection(str, Enum):
    BACK = "back"
    FORWARD = "forward"


@dataclass(frozen=True)
class RollbackPlan:
    direction: RollbackDirection
    current_generation: int
    target_generation: int | None
    description: str
    resolved_lock: Mapping[str, Any] | None = None


def capture_generation(profile_path: Path | str = DEFAULT_SYSTEM_PROFILE) -> int:
    """Return the generation encoded by the current system profile symlink."""
    path = Path(profile_path)
    try:
        target = os.readlink(path)
    except OSError as exc:
        raise ValueError(f"could not read the current system generation: {exc}") from exc
    match = _GENERATION_RE.search(target)
    if match is None:
        raise ValueError("current system profile does not name a NixOS generation")
    generation = int(match.group(1))
    if generation < 1:
        raise ValueError("current system generation must be positive")
    return generation


def plan_rollback(current_gen: int, target_gen: int) -> RollbackPlan:
    if isinstance(current_gen, bool) or not isinstance(current_gen, int) or current_gen < 1:
        raise ValueError("current generation must be a positive integer")
    if isinstance(target_gen, bool) or not isinstance(target_gen, int) or target_gen < 1:
        raise ValueError("target generation must be a positive integer")
    if target_gen >= current_gen:
        raise ValueError("rollback target must be older than the current generation")
    return RollbackPlan(
        direction=RollbackDirection.BACK,
        current_generation=current_gen,
        target_generation=target_gen,
        description=f"Roll back to generation {target_gen}, the system state saved before this install.",
    )


def plan_roll_forward(resolved_lock: Mapping[str, Any]) -> RollbackPlan:
    if not isinstance(resolved_lock, Mapping) or not resolved_lock:
        raise ValueError("resolved plan lock must be a non-empty object")
    return RollbackPlan(
        direction=RollbackDirection.FORWARD,
        current_generation=0,
        target_generation=None,
        description="Roll forward to the known-good installer plan.",
        resolved_lock=dict(resolved_lock),
    )


def request_params(plan: RollbackPlan, *, current_generation: int | None = None) -> dict[str, Any]:
    current = current_generation if current_generation is not None else plan.current_generation
    if plan.direction is RollbackDirection.BACK:
        lock_json = "{}"
        target = plan.target_generation or 0
    else:
        lock_json = json.dumps(plan.resolved_lock, sort_keys=True, separators=(",", ":"))
        target = 0
    return {
        "direction": plan.direction.value,
        "current_generation": current,
        "target_generation": target,
        "description": plan.description,
        "resolved_lock_json": lock_json,
    }


def rollback_state(current_generation: int, captured_generation: int) -> dict[str, Any]:
    return {
        "schema": "aqos.rollback-state.v1",
        "current_generation": current_generation,
        "captured_generation": captured_generation,
        "rollback_available": current_generation > captured_generation >= 1,
    }


def write_rollback_state(
    current_generation: int,
    captured_generation: int,
    state_path: Path | str = DEFAULT_STATE_PATH,
) -> Path:
    """Atomically publish the small state record consumed by dashboard tooling."""
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(rollback_state(current_generation, captured_generation), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path


def _load_projection_inputs() -> tuple[dict[str, Any], bytes]:
    module_catalog_path = _REPO_ROOT / "config" / "aqos-module-catalog-v1.json"
    fieldset_path = _REPO_ROOT / "config" / "aqos-mysystem-fieldset-v1.json"
    return resolver.parse_json_strict(module_catalog_path.read_bytes()), fieldset_path.read_bytes()


def _effect_aqos_rollback(
    *,
    direction: str,
    current_generation: int,
    target_generation: int,
    description: str,
    resolved_lock_json: str,
) -> dict[str, Any]:
    """Resolve an approved recovery action into an inert P0 executor plan."""
    del description
    if direction == RollbackDirection.BACK.value:
        plan_rollback(current_generation, target_generation)
        if resolved_lock_json != "{}":
            raise ValueError("rollback-back must not carry a resolved lock")
        return {
            "runbook": RUNBOOK_NAME,
            "direction": direction,
            "target_generation": target_generation,
            "executor": {
                "argv": ["nixos-rebuild", "switch", "--rollback"],
                "env": {},
                "executable": False,
                "blocked_reason": "p0-inert-approval-effect",
            },
        }

    if direction == RollbackDirection.FORWARD.value:
        if target_generation != 0:
            raise ValueError("roll-forward does not accept a generation target")
        lock = resolver.parse_json_strict(resolved_lock_json)
        plan_roll_forward(lock)
        module_catalog, fieldset_bytes = _load_projection_inputs()
        projection = resolver.compile_projection(lock, module_catalog, fieldset_bytes)
        if projection.get("executor", {}).get("executable") is not False:
            raise ValueError("P0 roll-forward projection must remain inert")
        return {
            "runbook": RUNBOOK_NAME,
            "direction": direction,
            "resolved_lock": lock,
            "projection": projection,
        }

    raise ValueError("unknown rollback direction")


_SPEC = AR.RunbookSpec(
    name=RUNBOOK_NAME,
    required_authority="owner-webauthn",
    risk_class="high",
    reversible=True,
    declared_effects=("select-generation-or-lock", "prepare-native-recovery", "verify-inert-executor"),
    param_schema={
        "direction": {"type": "str", "pattern": r"^(back|forward)$"},
        "current_generation": {"type": "int", "pattern": None},
        "target_generation": {"type": "int", "pattern": None},
        "description": {"type": "str", "pattern": _DESCRIPTION_PATTERN},
        "resolved_lock_json": {"type": "str", "pattern": _LOCK_JSON_PATTERN},
    },
    title_template="Approve system recovery: {direction}",
    what_template="{description}",
    why_template="Restores a known-good system state if the installer result is not usable.",
    effect=_effect_aqos_rollback,
)

AR.RUNBOOK_REGISTRY[RUNBOOK_NAME] = _SPEC
