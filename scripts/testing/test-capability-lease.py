#!/usr/bin/env python3
"""Acceptance tests for the Foundation C0 CapabilityLease primitive.

Covers the proof obligations from
`.agents/plans/aqos-foundation-c/C0-IMPLEMENTATION-SPEC.md` §Acceptance:
schema validation, sign/verify roundtrip, tamper detection, canonical
determinism, expiry, epoch-stale, attenuation monotonicity, and the DEV-key
banner. Offline only: uses the deterministic DEV key, no network, no
dependency on a real `/run/secrets` file. `jsonschema` is used if
importable; otherwise a minimal structural check keeps the schema test
running offline.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB_DIR))

import capability_lease as cl  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "capability-lease.schema.json"
GOLDEN_PATH = REPO_ROOT / "scripts" / "testing" / "fixtures" / "capability-lease-golden.json"
CLI_PATH = REPO_ROOT / "scripts" / "ai" / "aq-lease"

try:
    import jsonschema  # type: ignore

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


def load_golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def minimal_structural_validate(schema: dict, instance: dict) -> bool:
    """Fallback validator used only if jsonschema is not importable."""
    lease_def = schema["$defs"]["capability_lease"]
    required = lease_def["required"]
    allowed = set(lease_def["properties"].keys())
    if any(f not in instance for f in required):
        return False
    if any(k not in allowed for k in instance.keys()):
        return False
    return True


def schema_validate(schema: dict, instance: dict) -> bool:
    if HAVE_JSONSCHEMA:
        try:
            jsonschema.validate(instance=instance, schema=schema)
            return True
        except jsonschema.exceptions.ValidationError:
            return False
    return minimal_structural_validate(schema, instance)


# ---------------------------------------------------------------------
# 1. Schema validates golden leases; rejects extra/missing field
# ---------------------------------------------------------------------


def test_schema_validation() -> None:
    schema = load_schema()
    golden = load_golden()

    for name in ("valid", "expired", "tampered", "parent", "child"):
        check(
            f"schema: golden '{name}' lease validates",
            schema_validate(schema, golden[name]),
        )

    missing_field = dict(golden["valid"])
    del missing_field["signature"]
    check(
        "schema: rejects lease missing required field 'signature'",
        not schema_validate(schema, missing_field),
    )

    extra_field = dict(golden["valid"])
    extra_field["not_a_real_field"] = "nope"
    check(
        "schema: rejects lease with an unexpected extra field",
        not schema_validate(schema, extra_field),
    )


# ---------------------------------------------------------------------
# 2. Sign/verify roundtrip + tamper detection
# ---------------------------------------------------------------------


def test_sign_verify_roundtrip() -> None:
    golden = load_golden()
    key = cl.DEV_SIGNING_KEY

    verdict = cl.verify(golden["valid"], key)
    check("sign/verify: roundtrip on a freshly-signed lease -> ok", verdict == cl.VERIFY_OK)

    verdict = cl.verify(golden["tampered"], key)
    check(
        "tamper-detection: mutated 'permissions.actions' -> bad-signature",
        verdict == cl.VERIFY_BAD_SIGNATURE,
    )


def test_tamper_detection_each_field() -> None:
    golden = load_golden()
    key = cl.DEV_SIGNING_KEY
    base = golden["valid"]

    mutations = {
        "lease_id": "lease-mutated-id",
        "owner": "someone-else",
        "issued_to": "principal-attacker",
        "expires_at": "2099-01-01T00:00:00Z",
        "trust_tier": base["trust_tier"] + 5,
        "revocation_epoch": base["revocation_epoch"] + 1,
        "zero_trust_behavior": "strip" if base["zero_trust_behavior"] != "strip" else "none",
    }
    for field_name, new_value in mutations.items():
        mutated = copy.deepcopy(base)
        mutated[field_name] = new_value
        verdict = cl.verify(mutated, key)
        check(
            f"tamper-detection: mutating '{field_name}' -> bad-signature",
            verdict == cl.VERIFY_BAD_SIGNATURE,
        )

    mutated_perms = copy.deepcopy(base)
    mutated_perms["permissions"]["resources"].append("repo:extra")
    check(
        "tamper-detection: mutating 'permissions.resources' -> bad-signature",
        cl.verify(mutated_perms, key) == cl.VERIFY_BAD_SIGNATURE,
    )


# ---------------------------------------------------------------------
# 3. Canonical determinism (field-order-independent)
# ---------------------------------------------------------------------


def test_canonical_determinism() -> None:
    golden = load_golden()
    lease = golden["valid"]

    # Re-serialize with a different key insertion order than the original
    # dict (Python dicts preserve insertion order — build a deliberately
    # shuffled copy).
    keys = list(lease.keys())
    shuffled_keys = keys[::-1]
    shuffled = {k: lease[k] for k in shuffled_keys}

    payload_original = cl.canonical_payload(lease)
    payload_shuffled = cl.canonical_payload(shuffled)
    check(
        "canonical determinism: shuffled top-level key order -> identical payload",
        payload_original == payload_shuffled,
    )

    # Also shuffle nested permissions dict key order.
    shuffled_perms = dict(lease)
    shuffled_perms["permissions"] = {
        k: lease["permissions"][k] for k in reversed(list(lease["permissions"].keys()))
    }
    payload_nested_shuffled = cl.canonical_payload(shuffled_perms)
    check(
        "canonical determinism: shuffled nested 'permissions' key order -> identical payload",
        payload_original == payload_nested_shuffled,
    )

    sig1 = cl.sign(lease, cl.DEV_SIGNING_KEY)
    sig2 = cl.sign(shuffled, cl.DEV_SIGNING_KEY)
    check(
        "canonical determinism: signature identical regardless of key order",
        sig1 == sig2 == lease["signature"],
    )


# ---------------------------------------------------------------------
# 4. Expiry
# ---------------------------------------------------------------------


def test_expiry() -> None:
    golden = load_golden()
    key = cl.DEV_SIGNING_KEY

    check("expiry: is_expired() true for past expires_at", cl.is_expired(golden["expired"]))
    check("expiry: is_expired() false for future expires_at", not cl.is_expired(golden["valid"]))
    check(
        "expiry: verify() on an expired-but-correctly-signed lease -> expired",
        cl.verify(golden["expired"], key) == cl.VERIFY_EXPIRED,
    )


# ---------------------------------------------------------------------
# 5. Epoch-stale
# ---------------------------------------------------------------------


def test_epoch_stale() -> None:
    golden = load_golden()
    key = cl.DEV_SIGNING_KEY
    lease = golden["valid"]
    current_epoch = lease["revocation_epoch"] + 1

    check(
        "epoch-stale: epoch_stale() true when revocation_epoch < current_epoch",
        cl.epoch_stale(lease, current_epoch),
    )
    check(
        "epoch-stale: epoch_stale() false when revocation_epoch >= current_epoch",
        not cl.epoch_stale(lease, lease["revocation_epoch"]),
    )
    check(
        "epoch-stale: verify() with stale current_epoch -> epoch-stale",
        cl.verify(lease, key, current_epoch=current_epoch) == cl.VERIFY_EPOCH_STALE,
    )
    check(
        "epoch-stale: verify() with current current_epoch -> ok",
        cl.verify(lease, key, current_epoch=lease["revocation_epoch"]) == cl.VERIFY_OK,
    )


# ---------------------------------------------------------------------
# 6. Attenuation monotonicity
# ---------------------------------------------------------------------


def test_attenuation_accepts_valid_subset() -> None:
    golden = load_golden()
    parent = golden["parent"]
    child = golden["child"]

    check(
        "attenuation: golden child's parent_lease_id references golden parent",
        child["parent_lease_id"] == parent["lease_id"],
    )
    check(
        "attenuation: golden child actions subset of parent actions",
        set(child["permissions"]["actions"]) <= set(parent["permissions"]["actions"]),
    )
    check(
        "attenuation: golden child resources subset of parent resources",
        set(child["permissions"]["resources"]) <= set(parent["permissions"]["resources"]),
    )
    check(
        "attenuation: golden child trust_tier <= parent trust_tier",
        child["trust_tier"] <= parent["trust_tier"],
    )
    check(
        "attenuation: golden child verifies ok under DEV key",
        cl.verify(child, cl.DEV_SIGNING_KEY) == cl.VERIFY_OK,
    )

    # Build a fresh valid attenuation directly through the library too.
    fresh_child = cl.attenuate(
        parent,
        {
            "lease_id": "lease-c0-test-fresh-child",
            "actions": ["read"],
            "resources": [parent["permissions"]["resources"][0]],
            "trust_tier": parent["trust_tier"] - 1,
            "expires_at": parent["expires_at"],
        },
        key=cl.DEV_SIGNING_KEY,
    )
    check(
        "attenuation: freshly-built valid child verifies ok",
        cl.verify(fresh_child.to_dict(), cl.DEV_SIGNING_KEY) == cl.VERIFY_OK,
    )


def test_attenuation_rejects_widen_attempts() -> None:
    golden = load_golden()
    parent = golden["parent"]
    key = cl.DEV_SIGNING_KEY

    def try_attenuate(delta: dict) -> bool:
        """Returns True iff attenuate() raised ValueError (the expected outcome)."""
        try:
            cl.attenuate(parent, delta, key=key)
        except ValueError:
            return True
        return False

    check(
        "attenuation: extra action not in parent -> raises",
        try_attenuate({"actions": ["read", "detonate-nukes"]}),
    )
    check(
        "attenuation: extra resource not in parent -> raises",
        try_attenuate({"resources": ["repo:not-in-parent"]}),
    )
    check(
        "attenuation: higher trust_tier than parent -> raises",
        try_attenuate({"trust_tier": parent["trust_tier"] + 1}),
    )
    check(
        "attenuation: later expires_at than parent -> raises",
        try_attenuate({"expires_at": "2099-01-01T00:00:00Z"}),
    )
    check(
        "attenuation: dropping a parent constraint key -> raises",
        try_attenuate({"constraints": {}}),
    )
    check(
        "attenuation: loosening a numeric constraint -> raises",
        try_attenuate(
            {
                "constraints": {
                    "max_bytes": parent["permissions"]["constraints"]["max_bytes"] + 1
                }
            }
        ),
    )
    check(
        "attenuation: numeric constraint narrowed (not just equal) -> accepted",
        not try_attenuate(
            {
                "constraints": {
                    "max_bytes": parent["permissions"]["constraints"]["max_bytes"] - 1
                }
            }
        ),
    )
    check(
        "attenuation: adding a brand-new child-only constraint key -> accepted",
        not try_attenuate(
            {
                "constraints": {
                    # delta.constraints REPLACES (not merges with) the
                    # parent's constraints dict, so the parent's existing
                    # key must be carried forward here too — this test is
                    # specifically about the *new* key being accepted, not
                    # about omitting an existing one (that's the separate
                    # "dropping a parent constraint key -> raises" case).
                    "max_bytes": parent["permissions"]["constraints"]["max_bytes"],
                    "new_restriction": "tight",
                }
            }
        ),
    )


# ---------------------------------------------------------------------
# 6b. Attenuation constraint-widening — non-numeric value types
#
# C0-CRYPTO-REVIEW blocking finding: _check_constraints_tighten() used to
# only guard numeric constraint values + key presence. A non-numeric
# constraint (string, list) could be widened and the child still signed +
# verified `ok` — a fail-open monotonicity gap in the primitive that C1+
# consumes as THE attenuation oracle. Fixed to be complete over all value
# types (numeric / list-like / everything-else-must-match-exactly).
# ---------------------------------------------------------------------


def _make_constraint_parent(constraints: dict) -> dict:
    """Synthetic unsigned-parent dict for constraint-widening tests.
    attenuate() never verifies the parent's own signature — it only reads
    permissions/constraints/trust_tier/expires_at off it — so a plain dict
    built from the golden parent's shape is sufficient here."""
    golden_parent = load_golden()["parent"]
    parent = copy.deepcopy(golden_parent)
    parent["permissions"]["constraints"] = constraints
    return parent


def test_attenuation_rejects_nonnumeric_constraint_widening() -> None:
    key = cl.DEV_SIGNING_KEY

    def try_attenuate(parent: dict, delta: dict) -> bool:
        """Returns True iff attenuate() raised ValueError (expected)."""
        try:
            cl.attenuate(parent, delta, key=key)
        except ValueError:
            return True
        return False

    # --- string constraint ---
    str_parent = _make_constraint_parent({"path": "/repo/src"})
    check(
        "attenuation: string constraint widened (path '/repo/src' -> '/') -> raises",
        try_attenuate(str_parent, {"constraints": {"path": "/"}}),
    )
    check(
        "attenuation: string constraint left identical to parent -> accepted",
        not try_attenuate(str_parent, {"constraints": {"path": "/repo/src"}}),
    )

    # --- list constraint ---
    list_parent = _make_constraint_parent({"allowed": ["a"]})
    check(
        "attenuation: list constraint widened (['a'] -> ['a','b','c']) -> raises",
        try_attenuate(list_parent, {"constraints": {"allowed": ["a", "b", "c"]}}),
    )
    list_parent2 = _make_constraint_parent({"allowed": ["a", "b", "c"]})
    check(
        "attenuation: list constraint narrowed to a proper subset -> accepted",
        not try_attenuate(list_parent2, {"constraints": {"allowed": ["a"]}}),
    )
    check(
        "attenuation: list constraint left identical to parent -> accepted",
        not try_attenuate(list_parent2, {"constraints": {"allowed": ["a", "b", "c"]}}),
    )

    # --- reviewer repro #1 (verbatim): parent path=/repo/src, child path=/
    reviewer_repro_1_parent = _make_constraint_parent({"path": "/repo/src"})
    check(
        "reviewer repro #1: parent path='/repo/src' -> child path='/' now RAISES",
        try_attenuate(reviewer_repro_1_parent, {"constraints": {"path": "/"}}),
    )

    # --- reviewer repro #2 (verbatim): parent allowed=["a"], child=["a","b","c"]
    reviewer_repro_2_parent = _make_constraint_parent({"allowed": ["a"]})
    check(
        "reviewer repro #2: parent allowed=['a'] -> child ['a','b','c'] now RAISES",
        try_attenuate(reviewer_repro_2_parent, {"constraints": {"allowed": ["a", "b", "c"]}}),
    )


# ---------------------------------------------------------------------
# 6c. verify() totality — SHOULD-FIX
#
# verify() must be a typed, TOTAL function that never raises. A validly-
# shaped-but-non-int revocation_epoch (or trust_tier/version) used to slip
# past _is_malformed's type checks and blow up uncaught inside
# epoch_stale()'s int() call when current_epoch was passed. Never a
# security fail-open (it never returned "ok"), but it violated the
# "typed verdict, never raises" contract. Fixed by rejecting non-int
# revocation_epoch/trust_tier/version (bool excluded) as "malformed".
# ---------------------------------------------------------------------


def test_verify_is_total_over_non_int_fields() -> None:
    golden = load_golden()
    key = cl.DEV_SIGNING_KEY

    bad = copy.deepcopy(golden["valid"])
    bad["revocation_epoch"] = "not-an-int"
    bad["signature"] = cl.sign(bad, key)  # validly signed, just malformed field type

    try:
        verdict = cl.verify(bad, key, current_epoch=1)
        raised = False
    except Exception:  # noqa: BLE001 - we're proving verify() must NOT raise
        verdict = None
        raised = True

    check(
        "verify() totality: non-int revocation_epoch + current_epoch passed -> no exception",
        not raised,
    )
    check(
        "verify() totality: non-int revocation_epoch + current_epoch passed -> malformed",
        verdict == cl.VERIFY_MALFORMED,
    )

    bad_tt = copy.deepcopy(golden["valid"])
    bad_tt["trust_tier"] = True  # bool must not pass as a valid int trust_tier
    bad_tt["signature"] = cl.sign(bad_tt, key)
    check(
        "verify() totality: bool trust_tier is rejected as malformed (bool != int here)",
        cl.verify(bad_tt, key) == cl.VERIFY_MALFORMED,
    )


# ---------------------------------------------------------------------
# 7. DEV-key banner
# ---------------------------------------------------------------------


def test_dev_key_banner() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        missing_path = os.path.join(tmp, "does-not-exist")
        env = dict(os.environ)
        env["AQ_LEASE_SIGNING_KEY"] = missing_path
        # scrub any stray production key path from the test env
        key, is_dev = None, None
        old_env_val = os.environ.get(cl.ENV_KEY_PATH)
        try:
            os.environ[cl.ENV_KEY_PATH] = missing_path
            key, is_dev = cl.resolve_key()
        finally:
            if old_env_val is None:
                os.environ.pop(cl.ENV_KEY_PATH, None)
            else:
                os.environ[cl.ENV_KEY_PATH] = old_env_val

    check(
        "dev-key: resolve_key() falls back to DEV key + is_dev=True when path absent",
        key == cl.DEV_SIGNING_KEY and is_dev is True,
    )

    # CLI-level: verify against the tampered fixture with no --key (forces
    # the missing-secret-path DEV fallback) and confirm the banner text
    # appears on stderr.
    golden_valid = load_golden()["valid"]
    with tempfile.TemporaryDirectory() as tmp:
        lease_path = Path(tmp) / "valid-lease.json"
        lease_path.write_text(json.dumps(golden_valid), encoding="utf-8")
        cli_env = dict(os.environ)
        cli_env["AQ_LEASE_SIGNING_KEY"] = os.path.join(tmp, "does-not-exist")
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "verify", str(lease_path)],
            env=cli_env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    check(
        "dev-key: CLI prints the DEV-KEY banner to stderr when secret path is absent",
        cl.DEV_KEY_BANNER in result.stderr,
    )
    check("dev-key: CLI verify of golden 'valid' lease -> ok", result.stdout.strip() == "ok")


def main() -> int:
    test_schema_validation()
    test_sign_verify_roundtrip()
    test_tamper_detection_each_field()
    test_canonical_determinism()
    test_expiry()
    test_epoch_stale()
    test_attenuation_accepts_valid_subset()
    test_attenuation_rejects_widen_attempts()
    test_attenuation_rejects_nonnumeric_constraint_widening()
    test_verify_is_total_over_non_int_fields()
    test_dev_key_banner()

    print(f"\n{passed} passed, {failed} failed (of {passed + failed} assertions)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
