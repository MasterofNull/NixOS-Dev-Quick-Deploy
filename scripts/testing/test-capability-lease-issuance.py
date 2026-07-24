#!/usr/bin/env python3
"""Acceptance tests for the Foundation C1 shadow admission->issuance policy.

Covers the proof obligations from
`.agents/plans/aqos-foundation-c/C1-IMPLEMENTATION-SPEC.md` §Tests: the
admission->lease policy table, the secret-or-token-required strip override,
the deny path (needs-review/blocked), purity/additive-ness of
`shadow_issue()`, and JSONL append + schema validation of
`append_shadow_log()`. Fully OFFLINE: synthetic audit_result + candidate
dicts, no subprocess, no network, the C0 DEV signing key throughout.
`jsonschema` is used if importable; otherwise a minimal structural check
keeps the schema test running offline (same pattern as
scripts/testing/test-capability-lease.py).
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB_DIR))

import capability_lease as cl  # noqa: E402
import capability_lease_issuance as cli_policy  # noqa: E402

RECORD_SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "capability-lease-shadow-record.schema.json"
LEASE_SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "capability-lease.schema.json"
CLI_PATH = REPO_ROOT / "scripts" / "ai" / "aq-capability-shadow"

try:
    import jsonschema  # type: ignore
    from jsonschema import Draft202012Validator, RefResolver  # type: ignore

    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover - offline fallback path
    HAVE_JSONSCHEMA = False


passed = 0
failed = 0


def check(label: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS: {label}")
    else:
        failed += 1
        print(f"FAIL: {label}")


# ---------------------------------------------------------------------
# Schema validation helpers (jsonschema with fallback, mirrors
# test-capability-lease.py's pattern)
# ---------------------------------------------------------------------


def _minimal_structural_validate_record(instance: dict[str, Any]) -> bool:
    schema = json.loads(RECORD_SCHEMA_PATH.read_text(encoding="utf-8"))
    record_def = schema["$defs"]["shadow_record"]
    required = record_def["required"]
    allowed = set(record_def["properties"].keys())
    if any(f not in instance for f in required):
        return False
    if any(k not in allowed for k in instance.keys()):
        return False
    lease = instance.get("lease")
    if lease is not None:
        lease_schema = json.loads(LEASE_SCHEMA_PATH.read_text(encoding="utf-8"))
        lease_def = lease_schema["$defs"]["capability_lease"]
        lease_required = lease_def["required"]
        lease_allowed = set(lease_def["properties"].keys())
        if any(f not in lease for f in lease_required):
            return False
        if any(k not in lease_allowed for k in lease.keys()):
            return False
    return True


def schema_validate_record(instance: dict[str, Any]) -> bool:
    if HAVE_JSONSCHEMA:
        try:
            schema = json.loads(RECORD_SCHEMA_PATH.read_text(encoding="utf-8"))
            resolver = RefResolver(base_uri=RECORD_SCHEMA_PATH.resolve().as_uri(), referrer=schema)
            validator = Draft202012Validator(schema, resolver=resolver)
            validator.validate(instance)
            return True
        except jsonschema.exceptions.ValidationError:
            return False
        except Exception:
            # Resolver/version incompatibility — fall back rather than
            # spuriously fail an otherwise-correct record.
            return _minimal_structural_validate_record(instance)
    return _minimal_structural_validate_record(instance)


# ---------------------------------------------------------------------
# Synthetic fixtures (no dependency on the real candidate registry)
# ---------------------------------------------------------------------


def make_candidate(candidate_id: str, tool_allowlist: list[str], network: Any, writes: Any) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "name": f"synthetic candidate {candidate_id}",
        "tool_allowlist": list(tool_allowlist),
        "permissions": {"network": network, "writes": writes},
    }


def make_audit(candidate_id: str, admission: str, risk_flags: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "name": f"synthetic candidate {candidate_id}",
        "admission": admission,
        "risk_flags": list(risk_flags or []),
        "tool_audits": [],
    }


KEY = cl.DEV_SIGNING_KEY


# ---------------------------------------------------------------------
# 1. low-risk -> issue, trust_tier 3, zero_trust_behavior none, verifies
# ---------------------------------------------------------------------


def test_low_risk_issues_tier3() -> None:
    candidate = make_candidate("cand-low", ["tool_a", "tool_b"], network="github-api", writes=True)
    audit = make_audit("cand-low", "low-risk")

    record = cli_policy.shadow_issue(audit, candidate, key=KEY)

    check("low-risk: would_issue is True", record["would_issue"] is True)
    check("low-risk: deny_reason is None", record["deny_reason"] is None)
    check("low-risk: lease is not None", record["lease"] is not None)
    lease = record["lease"]
    check("low-risk: trust_tier == 3", lease["trust_tier"] == 3)
    check("low-risk: zero_trust_behavior == none", lease["zero_trust_behavior"] == "none")
    check(
        "low-risk: permissions.actions == candidate.tool_allowlist",
        lease["permissions"]["actions"] == ["tool_a", "tool_b"],
    )
    check(
        "low-risk: resources include 'network' (permissions.network truthy)",
        "network" in lease["permissions"]["resources"],
    )
    check(
        "low-risk: resources include 'write' (permissions.writes == True, not report-only)",
        "write" in lease["permissions"]["resources"],
    )
    check(
        "low-risk: constraints mirror permissions.network/writes",
        lease["permissions"]["constraints"] == {"network": "github-api", "writes": True},
    )
    check(
        "low-risk: lease VERIFIES ok under the C0 DEV key",
        cl.verify(lease, KEY) == cl.VERIFY_OK,
    )
    check("low-risk: record schema-validates", schema_validate_record(record))


# ---------------------------------------------------------------------
# 2. accepted-with-mitigations -> tier 2, issues, verifies; report-only
#    writes value is NOT treated as write-capable
# ---------------------------------------------------------------------


def test_accepted_with_mitigations_issues_tier2() -> None:
    candidate = make_candidate("cand-mit", ["x"], network=False, writes="report-output-only")
    audit = make_audit("cand-mit", "accepted-with-mitigations")

    record = cli_policy.shadow_issue(audit, candidate, key=KEY)

    check("accepted-with-mitigations: would_issue is True", record["would_issue"] is True)
    lease = record["lease"]
    check("accepted-with-mitigations: trust_tier == 2", lease["trust_tier"] == 2)
    check("accepted-with-mitigations: zero_trust_behavior == none", lease["zero_trust_behavior"] == "none")
    check(
        "accepted-with-mitigations: resources empty (network False, writes report-output-only)",
        lease["permissions"]["resources"] == [],
    )
    check(
        "accepted-with-mitigations: lease VERIFIES ok",
        cl.verify(lease, KEY) == cl.VERIFY_OK,
    )
    check("accepted-with-mitigations: record schema-validates", schema_validate_record(record))


# ---------------------------------------------------------------------
# 3. review-recommended -> issues but strip, tier 1
# ---------------------------------------------------------------------


def test_review_recommended_issues_but_strips() -> None:
    candidate = make_candidate("cand-rev", ["y"], network="localhost", writes=False)
    audit = make_audit("cand-rev", "review-recommended")

    record = cli_policy.shadow_issue(audit, candidate, key=KEY)

    check("review-recommended: would_issue is True", record["would_issue"] is True)
    lease = record["lease"]
    check("review-recommended: trust_tier == 1", lease["trust_tier"] == 1)
    check("review-recommended: zero_trust_behavior == strip", lease["zero_trust_behavior"] == "strip")
    check("review-recommended: lease VERIFIES ok", cl.verify(lease, KEY) == cl.VERIFY_OK)


# ---------------------------------------------------------------------
# 4. secret-or-token-required forces strip even on an otherwise
#    none-behavior (low-risk) admission
# ---------------------------------------------------------------------


def test_secret_or_token_required_forces_strip() -> None:
    candidate = make_candidate("cand-secret", ["z"], network="api", writes=False)
    audit = make_audit("cand-secret", "low-risk", risk_flags=["secret-or-token-required"])

    record = cli_policy.shadow_issue(audit, candidate, key=KEY)

    check("secret-flag: would_issue is True (low-risk still issues)", record["would_issue"] is True)
    lease = record["lease"]
    check("secret-flag: trust_tier unaffected (still 3, low-risk tier)", lease["trust_tier"] == 3)
    check(
        "secret-flag: zero_trust_behavior forced to strip despite low-risk admission",
        lease["zero_trust_behavior"] == "strip",
    )
    check("secret-flag: lease VERIFIES ok", cl.verify(lease, KEY) == cl.VERIFY_OK)
    check(
        "secret-flag: risk_flags carried through on the record",
        "secret-or-token-required" in record["risk_flags"],
    )


# ---------------------------------------------------------------------
# 5. needs-review and blocked -> would_issue False, lease None, deny_reason set
# ---------------------------------------------------------------------


def test_needs_review_and_blocked_deny() -> None:
    candidate = make_candidate("cand-nr", ["a"], network=False, writes=False)

    audit_nr = make_audit("cand-nr", "needs-review")
    record_nr = cli_policy.shadow_issue(audit_nr, candidate, key=KEY)
    check("needs-review: would_issue is False", record_nr["would_issue"] is False)
    check("needs-review: lease is None", record_nr["lease"] is None)
    check("needs-review: deny_reason == 'needs-review'", record_nr["deny_reason"] == "needs-review")
    check("needs-review: record schema-validates", schema_validate_record(record_nr))

    audit_blocked = make_audit("cand-nr", "blocked")
    record_blocked = cli_policy.shadow_issue(audit_blocked, candidate, key=KEY)
    check("blocked: would_issue is False", record_blocked["would_issue"] is False)
    check("blocked: lease is None", record_blocked["lease"] is None)
    check("blocked: deny_reason == 'blocked'", record_blocked["deny_reason"] == "blocked")
    check("blocked: record schema-validates", schema_validate_record(record_blocked))


# ---------------------------------------------------------------------
# 6. Additive / purity proof — shadow_issue never mutates its inputs and
#    never raises on normal (or minimal/degenerate) inputs
# ---------------------------------------------------------------------


def test_shadow_issue_is_pure_and_total() -> None:
    candidate = make_candidate("cand-pure", ["p1", "p2"], network="net", writes="scope-receipts-and-reports")
    audit = make_audit("cand-pure", "accepted-with-mitigations", risk_flags=["unpinned-version"])
    candidate_snapshot = copy.deepcopy(candidate)
    audit_snapshot = copy.deepcopy(audit)

    try:
        cli_policy.shadow_issue(audit, candidate, key=KEY)
        raised = False
    except Exception:  # noqa: BLE001 - proving shadow_issue must NOT raise
        raised = True
    check("purity: shadow_issue on well-formed inputs does not raise", not raised)
    check("purity: candidate dict unmutated after shadow_issue", candidate == candidate_snapshot)
    check("purity: audit_result dict unmutated after shadow_issue", audit == audit_snapshot)

    # Degenerate minimal inputs (no tool_allowlist/permissions keys at all,
    # unknown admission value) must still return a well-formed deny record,
    # never raise.
    minimal_candidate = {"id": "cand-minimal"}
    minimal_audit = {"id": "cand-minimal", "admission": "some-future-admission-value"}
    try:
        minimal_record = cli_policy.shadow_issue(minimal_audit, minimal_candidate, key=KEY)
        minimal_raised = False
    except Exception:  # noqa: BLE001
        minimal_record = None
        minimal_raised = True
    check("purity: unknown admission value does not raise", not minimal_raised)
    check(
        "purity: unknown admission value fails closed (would_issue False, lease None)",
        minimal_record is not None and minimal_record["would_issue"] is False and minimal_record["lease"] is None,
    )


# ---------------------------------------------------------------------
# 7. append_shadow_log: two records -> two valid JSONL lines, each
#    schema-valid
# ---------------------------------------------------------------------


def test_append_shadow_log_two_records() -> None:
    candidate_a = make_candidate("cand-a", ["only-a"], network="a-net", writes=False)
    audit_a = make_audit("cand-a", "low-risk")
    record_a = cli_policy.shadow_issue(audit_a, candidate_a, key=KEY)

    candidate_b = make_candidate("cand-b", ["only-b"], network=False, writes=False)
    audit_b = make_audit("cand-b", "blocked")
    record_b = cli_policy.shadow_issue(audit_b, candidate_b, key=KEY)

    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "nested" / "capability-lease-shadow.jsonl"
        cli_policy.append_shadow_log(record_a, log_path)
        cli_policy.append_shadow_log(record_b, log_path)

        lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        check("append-log: two records produce two JSONL lines", len(lines) == 2)

        parsed = [json.loads(line) for line in lines]
        check("append-log: line 1 parses back to record_a", parsed[0] == record_a)
        check("append-log: line 2 parses back to record_b", parsed[1] == record_b)
        check("append-log: line 1 schema-validates", schema_validate_record(parsed[0]))
        check("append-log: line 2 schema-validates", schema_validate_record(parsed[1]))

    # Fail-open: a bad/unwritable path must never raise.
    try:
        cli_policy.append_shadow_log(record_a, "/nonexistent-root-only-dir/definitely/not/writable.jsonl")
        append_raised = False
    except Exception:  # noqa: BLE001 - proving append_shadow_log must NOT raise
        append_raised = True
    check("append-log: unwritable path does not raise (fail-open)", not append_raised)


# ---------------------------------------------------------------------
# 8. DEV-key honesty (C1 review FIX 1) — `dev_key` field on the record
#    reflects whether the DEV signing key was used/would-be-used, and the
#    CLI surfaces the same DEV_KEY_BANNER contract as aq-lease.
# ---------------------------------------------------------------------


def test_dev_key_field_reflects_resolved_key() -> None:
    candidate = make_candidate("cand-devkey", ["t"], network="net", writes=False)
    audit = make_audit("cand-devkey", "low-risk")

    # No explicit key -> forces the real resolve_key() path; point
    # AQ_LEASE_SIGNING_KEY at a nonexistent file so it deterministically
    # falls back to the DEV key regardless of the host environment (same
    # pattern as test-capability-lease.py's test_dev_key_banner).
    old_env_val = os.environ.get(cl.ENV_KEY_PATH)
    with tempfile.TemporaryDirectory() as tmp:
        missing_path = os.path.join(tmp, "does-not-exist")
        try:
            os.environ[cl.ENV_KEY_PATH] = missing_path
            record = cli_policy.shadow_issue(audit, candidate)
        finally:
            if old_env_val is None:
                os.environ.pop(cl.ENV_KEY_PATH, None)
            else:
                os.environ[cl.ENV_KEY_PATH] = old_env_val

    check("dev-key: DEV-fallback record has dev_key True", record["dev_key"] is True)
    check(
        "dev-key: DEV-fallback lease still verifies ok under the DEV key",
        cl.verify(record["lease"], cl.DEV_SIGNING_KEY) == cl.VERIFY_OK,
    )
    check("dev-key: DEV-fallback record schema-validates", schema_validate_record(record))

    # Explicit non-DEV key -> dev_key False.
    other_key = b"not-the-dev-key-some-other-signing-key-value"
    record_explicit = cli_policy.shadow_issue(audit, candidate, key=other_key)
    check("dev-key: explicit non-DEV key -> dev_key False", record_explicit["dev_key"] is False)

    # Explicit DEV_SIGNING_KEY passed directly -> still honestly flagged.
    record_explicit_dev = cli_policy.shadow_issue(audit, candidate, key=cl.DEV_SIGNING_KEY)
    check("dev-key: explicit DEV_SIGNING_KEY passed directly -> dev_key True", record_explicit_dev["dev_key"] is True)

    # Deny records (no lease issued) still carry the field for schema
    # consistency (additionalProperties:false requires it on every record).
    audit_blocked = make_audit("cand-devkey", "blocked")
    record_blocked = cli_policy.shadow_issue(audit_blocked, candidate, key=cl.DEV_SIGNING_KEY)
    check(
        "dev-key: deny record still carries dev_key field",
        "dev_key" in record_blocked and record_blocked["dev_key"] is True,
    )
    check("dev-key: deny record schema-validates with dev_key field", schema_validate_record(record_blocked))


def test_cli_prints_dev_key_banner() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        audit_path = Path(tmp) / "audit.json"
        audit_path.write_text(
            json.dumps({"id": "osv-scanner", "admission": "low-risk", "risk_flags": []}),
            encoding="utf-8",
        )
        log_path = Path(tmp) / "shadow.jsonl"

        env = dict(os.environ)
        env[cl.ENV_KEY_PATH] = os.path.join(tmp, "does-not-exist")

        result = subprocess.run(
            [
                sys.executable,
                str(CLI_PATH),
                "run",
                "--audit-json",
                str(audit_path),
                "--log",
                str(log_path),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    check("cli dev-key: run still exits 0 under DEV fallback", result.returncode == 0)
    check("cli dev-key: CLI prints the DEV-KEY banner to stderr", cl.DEV_KEY_BANNER in result.stderr)
    check("cli dev-key: banner is attributed to aq-capability-shadow", "aq-capability-shadow" in result.stderr)


def main() -> int:
    test_low_risk_issues_tier3()
    test_accepted_with_mitigations_issues_tier2()
    test_review_recommended_issues_but_strips()
    test_secret_or_token_required_forces_strip()
    test_needs_review_and_blocked_deny()
    test_shadow_issue_is_pure_and_total()
    test_append_shadow_log_two_records()
    test_dev_key_field_reflects_resolved_key()
    test_cli_prints_dev_key_banner()

    print(f"\n{passed} passed, {failed} failed (of {passed + failed} assertions)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
