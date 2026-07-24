#!/usr/bin/env python3
"""Hermetic, offline regression checks for the Q5 lane-eligibility registry.

Covers `scripts/ai/aq-lane-eligibility` (admin CLI: check/list/promote/
revoke/expire-scan) and the registry-filtering wired into
`scripts/ai/aq-role-route`'s `route()`. DESIGN SSOT:
`.agents/plans/agent-agnostic-factory/Q5-LANE-ELIGIBILITY-REGISTRY-DESIGN.md`.

No network, no credentials. Every scenario writes its own temp registry
file (or points at a deliberately-missing path for the fail-safe checks) —
the real `config/lane-eligibility-registry.json` is never mutated by this
suite; the handful of read-only smoke checks against it are explicitly
labelled.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REAL_REGISTRY = ROOT / "config" / "lane-eligibility-registry.json"
LANE_ELIGIBILITY_BIN = ROOT / "scripts" / "ai" / "aq-lane-eligibility"
ROLE_ROUTE_BIN = ROOT / "scripts" / "ai" / "aq-role-route"


def _load(name: str, rel_path: str):
    script = ROOT / rel_path
    loader = importlib.machinery.SourceFileLoader(name, str(script))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


route_mod = _load("aq_role_route", "scripts/ai/aq-role-route")
lane_mod = _load("aq_lane_eligibility", "scripts/ai/aq-lane-eligibility")

FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    if condition:
        print(f"PASS: {label}")
    else:
        print(f"FAIL: {label}")
        FAILURES.append(label)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _write_registry(path: Path, lanes: dict[str, Any], roles: list[str] | None = None) -> None:
    data = {
        "schema_version": 1,
        "roles": roles or [
            "orchestrator", "architect", "implementer", "reviewer",
            "binding-acceptance", "research",
        ],
        "default_ttl_days": 45,
        "lanes": lanes,
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _future(days: int = 30) -> str:
    return _iso(datetime.now(timezone.utc) + timedelta(days=days))


def _past(days: int = 1) -> str:
    return _iso(datetime.now(timezone.utc) - timedelta(days=days))


# ---------------------------------------------------------------------------
# 1. Registry-native eligibility states: eligible / expired / not-listed /
#    hard-ineligible — via aq-lane-eligibility's own `_check` helper, at the
#    registry's native lane granularity (codex/opus/sonnet/antigravity/
#    gemini/local), NOT the coarser routing-lane granularity.
# ---------------------------------------------------------------------------

def test_check_states() -> None:
    with tempfile.TemporaryDirectory() as td:
        reg_path = Path(td) / "registry.json"
        _write_registry(reg_path, {
            "codex": {"eligible": {"implementer": {
                "measured_at": _past(10), "expires_at": _future(30), "evidence": "test",
            }}},
            "sonnet": {"eligible": {"implementer": {
                "measured_at": _past(60), "expires_at": _past(1), "evidence": "test",
            }}},
            "gemini": {},
            "antigravity": {
                "eligible": {"reviewer": {"measured_at": _past(1), "expires_at": _future(30), "evidence": "test"}},
                "ineligible": {"implementer": {"hard": True, "reason": "owner Q5 hard block"}},
            },
        })
        registry = lane_mod._load_registry(reg_path)

        eligible = lane_mod._check(registry, "codex", "implementer")
        check(eligible["eligible"] is True and eligible["status"] == "eligible",
              "check: codex/implementer with future expiry -> eligible")

        expired = lane_mod._check(registry, "sonnet", "implementer")
        check(expired["eligible"] is False and expired["status"] == "expired",
              "check: sonnet/implementer with past expiry -> expired")

        not_listed = lane_mod._check(registry, "gemini", "implementer")
        check(not_listed["eligible"] is False and not_listed["status"] == "not-listed",
              "check: gemini/implementer with no entry -> not-listed")

        hard_blocked = lane_mod._check(registry, "antigravity", "implementer")
        check(hard_blocked["eligible"] is False and hard_blocked["status"] == "hard-ineligible",
              "check: antigravity/implementer -> hard-ineligible (MUST be blocked)")
        check("owner Q5" in (hard_blocked.get("reason") or ""),
              "check: antigravity/implementer hard-block carries the governance reason")


def test_check_real_registry_antigravity_hard_block() -> None:
    """Read-only smoke check against the real seeded registry (no writes)."""
    registry = lane_mod._load_registry(REAL_REGISTRY)
    result = lane_mod._check(registry, "antigravity", "implementer")
    check(result["eligible"] is False and result["status"] == "hard-ineligible",
          "real registry: antigravity/implementer is hard-ineligible per Q5 seed")
    local_result = lane_mod._check(registry, "local", "implementer")
    check(local_result["eligible"] is True and local_result.get("capability_note"),
          "real registry: local/implementer eligible and carries a capability_note")


# ---------------------------------------------------------------------------
# 2. route() integration: excludes ineligible/expired lanes with the right
#    reason, at the routing-lane granularity (claude = union of opus+sonnet;
#    gemini = union of gemini+antigravity — see LANE_TO_REGISTRY_LANES).
# ---------------------------------------------------------------------------

def _reset_route_module(tmp: Path) -> None:
    route_mod.DELEGATION_DIR = tmp
    route_mod.CODEX_COOLDOWN_FILE = tmp / ".codex-quota-cooldown"
    route_mod.MODEL_COORDINATOR = ROOT / "config" / "model-coordinator.json"


def test_route_excludes_hard_ineligible_and_expired() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _reset_route_module(tmp)
        reg_path = tmp / "registry.json"
        _write_registry(reg_path, {
            "codex": {"eligible": {"implementer": {
                "measured_at": _past(10), "expires_at": _future(30), "evidence": "test",
            }}},
            "opus": {"eligible": {"implementer": {
                "measured_at": _past(10), "expires_at": _future(30), "evidence": "test",
            }}},
            "sonnet": {"eligible": {"implementer": {
                "measured_at": _past(60), "expires_at": _past(1), "evidence": "test",
            }}},
            "local": {"eligible": {"implementer": {
                "measured_at": _past(10), "expires_at": _future(30), "evidence": "test",
            }}},
            "gemini": {},
            "antigravity": {
                "ineligible": {"implementer": {"hard": True, "reason": "owner Q5 hard block"}},
            },
        })

        result = route_mod.route("implementer", "subj", [], registry_path=reg_path)
        check(result["ok"] is True, "route: implementer resolves ok with a mixed registry")
        check(result["chosen_agent"] != "gemini",
              "route: gemini lane (antigravity's only home) never chosen for implementer")
        check(result["registry_degraded"] is False, "route: registry loaded cleanly, not degraded")

        excluded_by_lane = {row["lane"]: row["reason"] for row in result["excluded_lanes"]}
        check(excluded_by_lane.get("gemini") == "hard-ineligible",
              "route: gemini excluded_lanes reason is hard-ineligible (antigravity backstop, via registry)")
        # claude is eligible overall because opus (union member) is valid,
        # even though sonnet (the other union member) is expired.
        check("claude" not in excluded_by_lane,
              "route: claude lane still eligible via opus even though sonnet's grant is expired")


def test_rule18_registry_preserves_role_eligibility_membership() -> None:
    """Rule 18 invariant (no single point of failure): turning the registry
    filter on must never narrow ROLE_ELIGIBILITY membership below what the
    running factory depends on, except the ONE ratified delta — gemini
    (antigravity's shared routing lane) dropped from implementer. This is a
    mechanical regression guard: it re-derives registry-eligible[role] for
    the REAL seeded registry, pre-availability (no down-flags/cooldowns
    involved — `_registry_eligibility` doesn't consult health at all), and
    fails loudly if any future registry edit silently strips a role's
    routability (the exact defect an independent review caught: seed rows
    narrower than ROLE_ELIGIBILITY made `orchestrator` collapse to
    codex-only, so a codex cooldown made the orchestrator role unroutable)."""
    registry, status = route_mod._load_registry(route_mod.DEFAULT_LANE_ELIGIBILITY_REGISTRY)
    check(status == "ok", "rule18: real registry loads cleanly for the invariant check")

    ratified_deltas = {"implementer": {"gemini"}}  # antigravity/implementer hard block

    for role, candidates in route_mod.ROLE_ELIGIBILITY.items():
        expected = set(candidates) - ratified_deltas.get(role, set())
        actual = {
            lane for lane in candidates
            if route_mod._registry_eligibility(lane, role, registry or {})[0]
        }
        check(
            actual == expected,
            f"rule18: role '{role}' registry-eligible set {sorted(actual)} == "
            f"ROLE_ELIGIBILITY {sorted(candidates)} minus ratified delta {sorted(expected)}",
        )


def test_route_no_eligible_lane_when_all_expired_or_absent() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _reset_route_module(tmp)
        reg_path = tmp / "registry.json"
        _write_registry(reg_path, {
            "codex": {"eligible": {"implementer": {
                "measured_at": _past(60), "expires_at": _past(1), "evidence": "test",
            }}},
            # opus/sonnet/local/gemini/antigravity: no implementer entries at all.
        })

        result = route_mod.route("implementer", "subj", [], registry_path=reg_path)
        check(result["ok"] is False, "route: all-expired-or-absent registry -> ok is False")
        check(result["reason"] == "no-eligible-lane",
              "route: reason is 'no-eligible-lane', not a misroute")
        reasons = {row["lane"]: row["reason"] for row in result["excluded_lanes"]}
        check(reasons.get("codex") == "expired", "route: codex excluded_lanes reason is 'expired'")
        check(reasons.get("local") == "not-listed", "route: local excluded_lanes reason is 'not-listed'")


# ---------------------------------------------------------------------------
# 3. Fail-safe: registry missing/unparseable -> routing still works AND the
#    antigravity/implementer hard block still applies via the hardcoded
#    backstop (never break routing, never silently drop the governance rule).
# ---------------------------------------------------------------------------

def test_route_failsafe_missing_registry() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _reset_route_module(tmp)
        missing_path = tmp / "does-not-exist.json"

        result = route_mod.route("implementer", "subj", [], registry_path=missing_path)
        check(result["ok"] is True, "route: missing registry file still resolves (fail-safe, never breaks routing)")
        check(result["registry_degraded"] is True, "route: missing registry -> registry_degraded is True")
        check(result["chosen_agent"] != "gemini",
              "route: fail-safe fallback still blocks gemini/antigravity from implementer (hardcoded backstop)")
        excluded_by_lane = {row["lane"]: row["reason"] for row in result["excluded_lanes"]}
        check(excluded_by_lane.get("gemini") == "hard-ineligible",
              "route: fail-safe excluded_lanes still names gemini as hard-ineligible for implementer")


def test_route_failsafe_unparseable_registry() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _reset_route_module(tmp)
        bad_path = tmp / "corrupt.json"
        bad_path.write_text("{not valid json", encoding="utf-8")

        result = route_mod.route("reviewer", "subj", [], registry_path=bad_path)
        check(result["ok"] is True, "route: unparseable registry still resolves for reviewer (fail-safe)")
        check(result["registry_degraded"] is True, "route: unparseable registry -> registry_degraded is True")

        impl_result = route_mod.route("implementer", "subj", [], registry_path=bad_path)
        check(impl_result["chosen_agent"] != "gemini",
              "route: unparseable registry + implementer role -> backstop still blocks gemini")


# ---------------------------------------------------------------------------
# 4. promote refuses without evidence, and sets a real expiry when given one.
# ---------------------------------------------------------------------------

def _run_cli(binary: Path, args: list[str]) -> tuple[int, dict[str, Any]]:
    proc = subprocess.run(
        [sys.executable, str(binary), *args],
        capture_output=True, text=True, timeout=30,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"_raw_stdout": proc.stdout, "_raw_stderr": proc.stderr}
    return proc.returncode, payload


def test_promote_refuses_without_evidence() -> None:
    with tempfile.TemporaryDirectory() as td:
        reg_path = Path(td) / "registry.json"
        _write_registry(reg_path, {})
        before = reg_path.read_text(encoding="utf-8")

        rc, payload = _run_cli(LANE_ELIGIBILITY_BIN, [
            "--registry-path", str(reg_path), "promote", "test-lane", "implementer", "--json",
        ])
        check(rc != 0, "promote: missing --evidence exits non-zero")
        check(payload.get("ok") is False and payload.get("reason") == "evidence-required",
              "promote: missing --evidence returns ok=False reason=evidence-required")
        after = reg_path.read_text(encoding="utf-8")
        check(before == after, "promote: refused promotion never writes to the registry file")


def test_promote_sets_expiry_with_evidence() -> None:
    with tempfile.TemporaryDirectory() as td:
        reg_path = Path(td) / "registry.json"
        _write_registry(reg_path, {})

        rc, payload = _run_cli(LANE_ELIGIBILITY_BIN, [
            "--registry-path", str(reg_path), "promote", "test-lane", "implementer",
            "--evidence", "unit-test evidence pointer", "--ttl-days", "10", "--json",
        ])
        check(rc == 0, "promote: with --evidence exits zero")
        check(payload.get("ok") is True, "promote: with --evidence returns ok=True")

        registry = json.loads(reg_path.read_text(encoding="utf-8"))
        entry = registry["lanes"]["test-lane"]["eligible"]["implementer"]
        check(entry.get("evidence") == "unit-test evidence pointer",
              "promote: registry file records the evidence pointer")
        measured = datetime.fromisoformat(entry["measured_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(entry["expires_at"].replace("Z", "+00:00"))
        delta_days = (expires - measured).total_seconds() / 86400
        check(9.9 <= delta_days <= 10.1, f"promote: expires_at is measured_at + ttl_days (got {delta_days:.2f}d)")

        # check must now see this lane as eligible.
        check_result = lane_mod._check(registry, "test-lane", "implementer")
        check(check_result["eligible"] is True, "promote: promoted entry is eligible via check()")


# ---------------------------------------------------------------------------
# 5. expire-scan finds an expired entry.
# ---------------------------------------------------------------------------

def test_expire_scan_finds_expired_entry() -> None:
    with tempfile.TemporaryDirectory() as td:
        reg_path = Path(td) / "registry.json"
        _write_registry(reg_path, {
            "stale-lane": {"eligible": {"implementer": {
                "measured_at": _past(60), "expires_at": _past(5), "evidence": "test",
            }}},
            "fresh-lane": {"eligible": {"implementer": {
                "measured_at": _past(1), "expires_at": _future(90), "evidence": "test",
            }}},
        })

        rc, payload = _run_cli(LANE_ELIGIBILITY_BIN, [
            "--registry-path", str(reg_path), "expire-scan", "--days", "1", "--json",
        ])
        check(rc == 0, "expire-scan: exits zero")
        rows = payload if isinstance(payload, list) else []
        stale_rows = [r for r in rows if r.get("lane") == "stale-lane"]
        check(len(stale_rows) == 1 and stale_rows[0]["status"] == "expired",
              "expire-scan: finds the expired stale-lane/implementer entry")
        fresh_rows = [r for r in rows if r.get("lane") == "fresh-lane"]
        check(len(fresh_rows) == 0,
              "expire-scan: does not flag the fresh-lane entry (90 days out, --days 1 horizon)")


def main() -> int:
    test_check_states()
    test_check_real_registry_antigravity_hard_block()
    test_rule18_registry_preserves_role_eligibility_membership()
    test_route_excludes_hard_ineligible_and_expired()
    test_route_no_eligible_lane_when_all_expired_or_absent()
    test_route_failsafe_missing_registry()
    test_route_failsafe_unparseable_registry()
    test_promote_refuses_without_evidence()
    test_promote_sets_expiry_with_evidence()
    test_expire_scan_finds_expired_entry()

    print()
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} check(s) failed:")
        for label in FAILURES:
            print(f"  - {label}")
        return 1
    print("PASS: all lane-eligibility checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
