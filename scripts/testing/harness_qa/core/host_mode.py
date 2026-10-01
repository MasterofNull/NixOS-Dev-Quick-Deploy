"""Deterministic host/CI detection for aq-qa phase 0.

Host-only checks probe a live NixOS stack (units, ports, AppArmor, inference /health).  On a GitHub
runner or any machine that is not the stack host they can only fail, so each run's verdict used to
depend on whether the downstream gate happened to classify every failing id as "live-service".  Here
the decision is explicit: when the machine is not a stack host, host-only checks that FAILED are
reported as SKIP with an honest reason.  A pass is never fabricated and checks that actually passed
stay passed.  On a real host nothing changes.
"""
from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from .result import CheckResult, Status

# Same classes as tier0 LIVE_SERVICE_CLASS_IDS plus host-installed tooling probes.
HOST_ONLY_IDS = frozenset({
    "0.1.1", "0.1.2", "0.1.3", "0.2.1", "0.2.2", "0.2.3", "0.2.4", "0.2.5",
    "0.3.1", "0.3.2", "0.3.3", "0.4.1", "0.4.2", "0.4.3", "0.5.1", "0.5.3",
    "0.6.1", "0.6.2", "0.7.4", "0.8.1", "0.10.22",
    # Live HTTP endpoints of the deployed stack (switchboard, hybrid-coordinator, dashboard).
    "0.5.2", "0.7.1", "0.7.2", "0.9.1", "0.9.2", "0.9.3", "0.10.40", "0.10.42", "0.10.44",
    "0.12.1", "0.16.2", "86.7",
    # Deployed host state absent off-host: the active model file, untracked operational state
    # (PULSE.log, RESUME.json, candidates.json) and the fine-tuning dataset under /var/lib.
    "0.10.5", "0.13.2", "0.13.4", "0.152.3", "0.152.4", "0.152.9",
})
_TRUE = {"1", "true", "yes", "on"}


def host_mode(env=None, nixos_marker: Path = Path("/etc/NIXOS")) -> tuple[str, str]:
    """Return (mode, why) where mode is "host" or "ci".  AQ_QA_HOST_MODE=host|ci overrides detection."""
    env = os.environ if env is None else env
    forced = env.get("AQ_QA_HOST_MODE", "").strip().lower()
    if forced in ("host", "ci"):
        return forced, f"AQ_QA_HOST_MODE={forced}"
    if env.get("GITHUB_ACTIONS", "").lower() in _TRUE or env.get("CI", "").lower() in _TRUE:
        return "ci", "CI environment"
    if not nixos_marker.exists():
        return "ci", f"{nixos_marker} absent: not a NixOS stack host"
    return "host", "NixOS stack host"


def demote_host_only(results: list[CheckResult], env=None, nixos_marker: Path = Path("/etc/NIXOS")) -> list[CheckResult]:
    mode, why = host_mode(env, nixos_marker)
    if mode != "ci":
        return results
    out = []
    for r in results:
        base = r.id.split(":", 1)[0]
        if r.status is Status.FAIL and base in HOST_ONLY_IDS:
            out.append(replace(r, status=Status.SKIP, reason=f"host-only check not run: {why}; authoritative on the stack host",
                               details=None))
        else:
            out.append(r)
    return out
