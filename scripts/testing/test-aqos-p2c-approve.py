#!/usr/bin/env python3
"""Acceptance tests for the P2c semantic-diff human-approval surface
(`scripts/ai/lib/aqos_install_diff.py`, `scripts/ai/lib/aqos_install_runbook.py`,
`scripts/ai/aqos-approve-install`).

Covers the P2C-SLICE-PLAN.md "Validation / acceptance" goals:
  (a) no-approval path -- emitting a request resolves NOTHING.
  (b) approval path -- after transition to "approved", the audited executor
      produces the SAME resolved lock (byte-identical, RFC 8785 JCS) a
      manual `resolve_plan` call with the equivalent selection produces.
  (c) reject/timeout -- fail-safe, nothing applied.
  (d) the human-facing diff text is plain language (no hashes) across
      profile / role / AI-toggle cases, including the no-change case.

Fully offline: no network, no live git/hw probe, no real WebAuthn --
`aqos_install_runbook`'s `_HW_LOADER`/`_SOURCE_IDENTITY_LOADER` seams are
monkeypatched to fixed fixtures (same pattern
`scripts/testing/test-aqos-adapter-parity.py` uses for its own
`hardware()`/`source()` fixtures), and approval is driven directly through
`approval_request.transition()` -- no `aq-approve-headless`/FIDO2 involved.

`check()` raises `AssertionError` immediately on a failed condition (see
`test-approval-request.py` for why); `main()` runs every `test_*` and
aggregates failures for a human-readable summary when run directly.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB_DIR))

import approval_executor as AE  # noqa: E402
import approval_request as AR  # noqa: E402
import aqos_install_diff as install_diff  # noqa: E402
import aqos_install_resolver as resolver  # noqa: E402
import aqos_install_runbook as runbook  # noqa: E402  (side effect: registers RUNBOOK_NAME)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# --------------------------------------------------------------------------
# Fixtures -- fixed hardware + source identity (mirrors
# test-aqos-adapter-parity.py's hardware()/source()), monkeypatched into
# aqos_install_runbook's env seams so the byte-identity proof never touches
# live git or a real hardware probe.
# --------------------------------------------------------------------------

HOST = "p2c-test-host"


def _fixed_hardware() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "cpu": {"architecture": "x86_64", "model": "t", "cores": 8, "threads": 16},
        "ram": {"total_bytes": 32 * 1024**3},
        "gpu": {"outcome": "detected", "devices": [], "present": False},
    }


def _fixed_source(host_target: str) -> dict[str, Any]:
    return {
        "oid_algorithm": "sha1", "git_commit": "a" * 40, "git_tree": "b" * 40,
        "clean_worktree": True, "flake_lock_sha256": "c" * 64, "nix_system": "x86_64-linux",
        "flake_installable": f"path:/repo#nixosConfigurations.{host_target}",
        "host_target": host_target,
    }


def _install_fixtures() -> None:
    runbook._HW_LOADER = _fixed_hardware
    runbook._SOURCE_IDENTITY_LOADER = lambda host_target: _fixed_source(host_target)


_MODULE_CATALOG = json.loads((REPO_ROOT / "config" / "aqos-module-catalog-v1.json").read_text())

_SELECTION = {"golden_profile": "profile.gaming", "roles": ["role.gaming"], "include_local_ai": False}


def _build_params(selection: dict, *, host_target: str = HOST) -> dict[str, str]:
    diff_text = install_diff.render_selection_diff(selection, install_diff.SAFE_DEFAULT_SELECTION, _MODULE_CATALOG)
    return {
        "diff": diff_text,
        "selection_json": json.dumps(selection, sort_keys=True, separators=(",", ":")),
        "host_target": host_target,
    }


def _new_request(request_id: str, selection: dict = _SELECTION, *, host_target: str = HOST) -> dict:
    return AR.create_request(
        request_id=request_id,
        created_by="test-aqos-p2c-approve",
        runbook=runbook.RUNBOOK_NAME,
        params=_build_params(selection, host_target=host_target),
        grant_subject=host_target,
    )


class _Store:
    """Trivial in-memory record store -- the same load_record/save_record
    shape `approval_executor.execute_request` expects (design invariant 6:
    P0 has no live confined store; the executor takes these as callables)."""

    def __init__(self) -> None:
        self._records: dict[str, dict] = {}

    def put(self, record: dict) -> None:
        self._records[record["request_id"]] = record

    def load(self, request_id: str):
        return self._records.get(request_id)

    def save(self, record: dict) -> None:
        self._records[record["request_id"]] = record


# --------------------------------------------------------------------------
# (a) No-approval path -- emitting a request resolves NOTHING.
# --------------------------------------------------------------------------


def test_no_resolve_before_approval() -> None:
    _install_fixtures()
    record = _new_request("p2c-req-pending-0001")
    check(record["status"] == AR.STATUS_PENDING, "freshly created request must be pending")

    store = _Store()
    store.put(record)
    outcome = AE.execute_request("p2c-req-pending-0001", load_record=store.load, save_record=store.save)

    check(outcome.ok is False, "executor must refuse a pending (un-approved) request")
    check(outcome.reason == AE.REASON_NOT_APPROVED, f"expected not-approved, got {outcome.reason}")
    check(
        store.load("p2c-req-pending-0001")["status"] == AR.STATUS_PENDING,
        "a refused execution must not mutate the record's status",
    )
    check(
        not any(e["event"] == "effect_executed" for e in outcome.events),
        "no effect_executed event may appear before approval -- nothing may have resolved",
    )


# --------------------------------------------------------------------------
# (b) Approval path -- approve == manual == one engine, byte-identical.
# --------------------------------------------------------------------------


def test_approved_execution_matches_manual_resolve_byte_identical() -> None:
    _install_fixtures()
    record = _new_request("p2c-req-approve-0001")

    approved, _event = AR.transition(record, AR.STATUS_APPROVED, actor="owner-webauthn")
    store = _Store()
    store.put(approved)

    outcome = AE.execute_request("p2c-req-approve-0001", load_record=store.load, save_record=store.save)
    check(outcome.ok is True, f"approved execution must succeed, got reason={outcome.reason}")
    check(outcome.record["status"] == AR.STATUS_EXECUTED, "executed record must reach status=executed")

    effect_events = [e for e in outcome.events if e["event"] == "effect_executed"]
    check(len(effect_events) == 1, "exactly one effect_executed event expected")
    resolved_lock = effect_events[0]["result"]["resolved_lock"]

    # The manual path: the SAME selection through normalize_adapter("manual", ...)
    # -> resolve_plan, using the identical on-disk catalog/schema/hw/source
    # fixtures the approved effect used (via the monkeypatched seams above).
    schema, module_catalog, module_bytes, ai_bytes, fieldset_bytes = runbook._load_static_environment()
    manual_request = resolver.normalize_adapter(
        "manual",
        {
            "artifact_type": "request_plan",
            "schema_version": resolver.SCHEMA_VERSION,
            "selection": dict(_SELECTION),
            "host_target": HOST,
        },
    )
    manual_lock = resolver.resolve_plan(
        manual_request, _fixed_hardware(), module_catalog, module_bytes, ai_bytes, fieldset_bytes,
        schema, _fixed_source(HOST),
    )

    check(
        resolver.jcs_bytes(resolved_lock) == resolver.jcs_bytes(manual_lock),
        "approved-via-executor lock must be byte-identical (JCS) to a manual resolve of the same selection",
    )


# --------------------------------------------------------------------------
# (c) Reject / timeout -- fail-safe, nothing applied.
# --------------------------------------------------------------------------


def test_denied_request_applies_nothing() -> None:
    _install_fixtures()
    record = _new_request("p2c-req-denied-0001")
    denied, _event = AR.transition(record, AR.STATUS_DENIED, actor="owner")
    store = _Store()
    store.put(denied)

    outcome = AE.execute_request("p2c-req-denied-0001", load_record=store.load, save_record=store.save)
    check(outcome.ok is False, "a denied request must never execute")
    check(outcome.reason == AE.REASON_NOT_APPROVED, f"expected not-approved, got {outcome.reason}")
    check(store.load("p2c-req-denied-0001")["status"] == AR.STATUS_DENIED, "denied status must be sticky")


def test_expired_request_applies_nothing() -> None:
    _install_fixtures()
    record = _new_request("p2c-req-expired-0001")
    expired, _event = AR.transition(record, AR.STATUS_EXPIRED, actor="system-ttl")
    store = _Store()
    store.put(expired)

    outcome = AE.execute_request("p2c-req-expired-0001", load_record=store.load, save_record=store.save)
    check(outcome.ok is False, "an expired (timed-out) request must never execute")
    check(outcome.reason == AE.REASON_NOT_APPROVED, f"expected not-approved, got {outcome.reason}")


# --------------------------------------------------------------------------
# (d) Plain-language diff -- no hashes/jargon, across profile/role/AI cases.
# --------------------------------------------------------------------------

_HEX64_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")


def _assert_plain_language(text: str, label: str) -> None:
    check(isinstance(text, str) and text, f"{label}: diff text must be a non-empty string")
    check(_HEX64_RE.search(text) is None, f"{label}: diff text must not contain a 64-hex digest")
    check("sha256" not in text.lower(), f"{label}: diff text must not contain the literal 'sha256'")
    check("/run/secrets" not in text, f"{label}: diff text must not reference /run/secrets")


def test_diff_is_plain_language_across_cases() -> None:
    default = install_diff.SAFE_DEFAULT_SELECTION

    no_change = install_diff.render_selection_diff(dict(default), default, _MODULE_CATALOG)
    _assert_plain_language(no_change, "no-change")
    check("no change" in no_change.lower(), "identical selection must say so in plain language")

    profile_change = install_diff.render_selection_diff(
        {"golden_profile": "profile.gaming", "roles": [], "include_local_ai": False}, default, _MODULE_CATALOG
    )
    _assert_plain_language(profile_change, "profile-change")
    check("Profile:" in profile_change, "a profile change must be called out")

    role_change = install_diff.render_selection_diff(
        {"golden_profile": default["golden_profile"], "roles": ["role.cpp-dev"], "include_local_ai": False},
        default, _MODULE_CATALOG,
    )
    _assert_plain_language(role_change, "role-change")
    check("Roles added" in role_change, "an added role must be called out")

    ai_on_marginal = install_diff.render_selection_diff(
        {"golden_profile": default["golden_profile"], "roles": [], "include_local_ai": True},
        default, _MODULE_CATALOG, ai_fit={"verdict": "not_advised"},
    )
    _assert_plain_language(ai_on_marginal, "ai-on-marginal-hardware")
    check("Local AI: OFF -> ON" in ai_on_marginal, "an AI toggle must be called out")
    check("Honesty note" in ai_on_marginal, "marginal-hardware AI-on must carry an honesty note")

    ai_on_fit = install_diff.render_selection_diff(
        {"golden_profile": default["golden_profile"], "roles": [], "include_local_ai": True},
        default, _MODULE_CATALOG, ai_fit={"verdict": "recommended"},
    )
    _assert_plain_language(ai_on_fit, "ai-on-recommended-hardware")
    check("Honesty note" not in ai_on_fit, "recommended-hardware AI-on must not carry a marginal-hardware warning")


def main() -> int:
    tests = [
        test_no_resolve_before_approval,
        test_approved_execution_matches_manual_resolve_byte_identical,
        test_denied_request_applies_nothing,
        test_expired_request_applies_nothing,
        test_diff_is_plain_language_across_cases,
    ]
    failures: list[str] = []
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failures.append(f"{test.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001 - surface unexpected errors as failures too
            failures.append(f"{test.__name__}: unexpected {exc.__class__.__name__}: {exc}")

    if failures:
        print(f"test-aqos-p2c-approve: FAILED {len(failures)}/{len(tests)}")
        for line in failures:
            print(f"  - {line}")
        return 1

    print(f"test-aqos-p2c-approve: ok {len(tests)}/{len(tests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
