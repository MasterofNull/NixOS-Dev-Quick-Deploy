#!/usr/bin/env python3
"""Fast-lane staleness checker (split-channel packaging sc-2).

.agents/plans/split-channel-packaging/DESIGN.md: this dev system pulls a
curated "fast-lane" of packages from nixpkgs-unstable (see
nix/overlays/fast-lane-manifest.nix, the single source of truth) while
everything else stays pinned on stable nixpkgs. This checker answers two
questions, NOTIFY-ONLY (it never runs `nix flake update` or rebuilds — blind
auto-update is exactly what pinning protects against; the owner decides when
to bump):

  1. Per fast-lane package: is the version resolved by the CURRENT flake.lock
     nixpkgs-unstable pin ("installed") behind the version nixpkgs-unstable
     offers RIGHT NOW at its live nixos-unstable HEAD ("available")?
  2. Is the nixpkgs-unstable input pin itself stale (lastModified age vs a
     threshold)?

Designed to run as a systemd timer (see
nix/modules/core/fast-lane-staleness-monitor.nix). Writes a status JSON for
dashboard/API consumers and pushes an attention-queue alert (the same
notify surface scripts/health/ai-stack-health-monitor.py uses) when
anything is behind or the pin is stale.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(os.environ.get("REPO_ROOT", Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ai" / "lib"))

_MANIFEST_PATH = _REPO_ROOT / "nix" / "overlays" / "fast-lane-manifest.nix"
_FLAKE_LOCK_PATH = Path(os.environ.get("FLAKE_LOCK_PATH", _REPO_ROOT / "flake.lock"))
_STATUS_PATH = Path(
    os.environ.get("FAST_LANE_STATUS_PATH", _REPO_ROOT / ".agents" / "health-monitor" / "fast-lane-staleness.json")
)
_NIX_BIN = os.environ.get("NIX_BIN", "nix")
_NIX_SYSTEM = os.environ.get("NIX_SYSTEM", "x86_64-linux")
# nixos-unstable is the live/floating ref: re-fetching it (rather than the
# locked rev) is exactly how we detect "nixpkgs-unstable has moved on".
_UNSTABLE_LIVE_REF = os.environ.get("FAST_LANE_UNSTABLE_LIVE_REF", "github:NixOS/nixpkgs/nixos-unstable")
_PIN_STALE_DAYS = float(os.environ.get("FAST_LANE_PIN_STALE_DAYS", "30"))
_NIX_EVAL_TIMEOUT_S = int(os.environ.get("FAST_LANE_NIX_EVAL_TIMEOUT_S", "120"))
_SOURCE = "fast-lane-staleness-check"
_COOLDOWN_S = int(os.environ.get("FAST_LANE_ALERT_COOLDOWN_S", "3600"))


@dataclass
class PackageStatus:
    name: str
    unstable_attr: str
    installed_version: Optional[str]
    available_version: Optional[str]
    behind: bool
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "unstable_attr": self.unstable_attr,
            "installed_version": self.installed_version,
            "available_version": self.available_version,
            "behind": self.behind,
            "error": self.error,
        }


def load_manifest() -> dict:
    """Read the SAME manifest the overlay uses — never a duplicated list."""
    proc = subprocess.run(
        [_NIX_BIN, "eval", "--json", "--file", str(_MANIFEST_PATH)],
        capture_output=True, text=True, timeout=_NIX_EVAL_TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"failed to evaluate {_MANIFEST_PATH}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def load_locked_unstable_rev() -> Optional[dict]:
    """Return the nixpkgs-unstable node from flake.lock, or None if absent/unreadable."""
    try:
        data = json.loads(_FLAKE_LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data.get("nodes", {}).get("nixpkgs-unstable", {}).get("locked")


def pin_age_days(locked: Optional[dict]) -> Optional[float]:
    """Age of the nixpkgs-unstable flake.lock pin in days, or None if unknown."""
    if not locked or "lastModified" not in locked:
        return None
    return (time.time() - float(locked["lastModified"])) / 86400.0


def _nix_eval_version(flake_ref: str, attr: str) -> Optional[str]:
    """Evaluate <flake_ref>#<attr>.version. Returns None on any failure — a
    network hiccup or a since-removed attr must never crash the checker."""
    try:
        proc = subprocess.run(
            [_NIX_BIN, "eval", "--raw", f"{flake_ref}#{attr}.version"],
            capture_output=True, text=True, timeout=_NIX_EVAL_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    version = proc.stdout.strip()
    return version or None


def compare_versions(installed: Optional[str], available: Optional[str]) -> bool:
    """True iff `installed` is behind `available`. Pure/testable: no I/O.

    We deliberately do NOT attempt semantic version ordering (dotted-version
    comparison breaks on nixpkgs' date-suffixed / rc / unstable-* schemes).
    A simple string inequality is exactly what's needed here: the two
    versions come from the SAME attr at two different nixpkgs-unstable
    revisions, so any difference means unstable has moved since our pin.
    Unknown values (None) are never reported as "behind" — no false alarms
    from a transient eval failure.
    """
    if installed is None or available is None:
        return False
    return installed != available


def check_package(name: str, renames: dict, locked_flake_ref: str) -> PackageStatus:
    unstable_attr = renames.get(name, name)
    installed = _nix_eval_version(locked_flake_ref, unstable_attr)
    available = _nix_eval_version(_UNSTABLE_LIVE_REF, unstable_attr)
    error = None
    if installed is None:
        error = f"could not resolve {unstable_attr}.version from locked nixpkgs-unstable pin"
    elif available is None:
        error = f"could not resolve {unstable_attr}.version from live {_UNSTABLE_LIVE_REF}"
    return PackageStatus(
        name=name,
        unstable_attr=unstable_attr,
        installed_version=installed,
        available_version=available,
        behind=compare_versions(installed, available),
        error=error,
    )


def write_status(status: dict) -> None:
    _STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _STATUS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(_STATUS_PATH)


def main() -> int:
    try:
        manifest = load_manifest()
    except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        write_status({
            "source": _SOURCE,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "error": f"manifest load failed: {e}",
            "packages": [],
            "behind_count": 0,
        })
        print(f"[{_SOURCE}] manifest load failed: {e}", file=sys.stderr)
        return 1

    active = manifest.get("active", [])
    renames = manifest.get("renames", {})
    locked = load_locked_unstable_rev()
    locked_rev = (locked or {}).get("rev")
    locked_flake_ref = f"github:NixOS/nixpkgs/{locked_rev}" if locked_rev else _UNSTABLE_LIVE_REF
    age_days = pin_age_days(locked)
    pin_stale = age_days is not None and age_days > _PIN_STALE_DAYS

    results = [check_package(name, renames, locked_flake_ref) for name in active]
    behind = [r for r in results if r.behind]

    status = {
        "source": _SOURCE,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest_path": str(_MANIFEST_PATH),
        "locked_unstable_rev": locked_rev,
        "locked_unstable_pin_age_days": None if age_days is None else round(age_days, 1),
        "pin_stale_threshold_days": _PIN_STALE_DAYS,
        "pin_stale": pin_stale,
        "packages": [r.to_dict() for r in results],
        "behind_count": len(behind),
        "total_count": len(results),
    }
    write_status(status)

    if not behind and not pin_stale:
        print(f"[{_SOURCE}] {len(results)} fast-lane package(s) up to date; pin age "
              f"{status['locked_unstable_pin_age_days']}d")
        return 0

    # Notify (never auto-apply) — same attention-queue surface as
    # ai-stack-health-monitor.py, so it lands on the dashboard + next shell prompt.
    try:
        from attention_queue import push  # noqa: PLC0415 — optional dep, imported lazily

        lines = [f"  {r.name} ({r.unstable_attr}): installed={r.installed_version} "
                 f"available={r.available_version}" for r in behind]
        if pin_stale:
            lines.append(f"  nixpkgs-unstable pin is {status['locked_unstable_pin_age_days']}d old "
                         f"(>{_PIN_STALE_DAYS}d)")
        push(
            source=_SOURCE,
            severity="low",
            autonomy_boundary="human_gate",
            title=f"Fast-lane: {len(behind)} package(s) behind nixpkgs-unstable"
                  + (" + stale pin" if pin_stale else ""),
            detail=(
                "The fast-lane staleness checker found newer versions available on "
                "nixpkgs-unstable than what the current flake.lock pin resolves to. "
                "This is advisory only — nothing was changed.\n" + "\n".join(lines)
                + "\n\nTo bump: review nix/overlays/fast-lane-manifest.nix, then run "
                  "`nix flake lock --update-input nixpkgs-unstable` and rebuild-test."
            ),
            proposed_action="Review and, if desired, bump nixpkgs-unstable + rebuild-test.",
            ttl_s=_COOLDOWN_S,
        )
    except Exception as e:  # noqa: BLE001 — notification must never crash the checker
        print(f"[{_SOURCE}] attention_queue push failed (non-fatal): {e}", file=sys.stderr)

    print(f"[{_SOURCE}] {len(behind)}/{len(results)} package(s) behind; pin_stale={pin_stale}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
