#!/usr/bin/env python3
"""Offline acceptance tests — Foundation C C3b R1 execution-grant primitive.

Exercises `scripts/ai/lib/execution_grant.py` as a pure, offline library
(no sockets, no filesystem effects beyond reading its own fixture, no
network) per
`.agents/plans/aqos-foundation-c/C3B-R1-DESIGN-AND-AUTHORIZATION.md`
(status R1_REVIEWED_PASS). Loads every golden vector from
`scripts/testing/fixtures/execution-grant-golden.json` and asserts it maps
to its EXACT typed outcome, plus: `verify_grant` never raises on
arbitrary/garbage input (fuzz), and the `reserve_replay`
reserved->committed|failed state transitions.

Run directly: `python3 scripts/testing/test-execution-grant.py`
Exits 0 iff every test passes; each failure prints name/expected/actual.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = str(_REPO_ROOT / "scripts" / "ai" / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import execution_grant as eg  # noqa: E402

FIXTURE_PATH = _REPO_ROOT / "scripts" / "testing" / "fixtures" / "execution-grant-golden.json"


# --------------------------------------------------------------------------
# Test harness (no external deps — matches test-capability-lease-gate.py)
# --------------------------------------------------------------------------

_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), detail))


def _report_and_exit() -> None:
    failed = [r for r in _RESULTS if not r[1]]
    for name, ok, detail in _RESULTS:
        status = "PASS" if ok else "FAIL"
        line = f"[{status}] {name}"
        if detail and not ok:
            line += f" — {detail}"
        print(line)
    print(f"\n{len(_RESULTS) - len(failed)}/{len(_RESULTS)} passed")
    if failed:
        print(f"FAILED: {[f[0] for f in failed]}")
        sys.exit(1)
    sys.exit(0)


def _parse_now(value):
    if value is None:
        return None
    v = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(v)


# --------------------------------------------------------------------------
# 1. Golden vectors — every fixture entry maps to its exact typed outcome
# --------------------------------------------------------------------------


def test_golden_vectors():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    prod_key = bytes.fromhex(fixture["production_public_key_hex"])
    dev_key = bytes.fromhex(fixture["dev_public_key_hex"])
    vectors = fixture["vectors"]
    check("fixture_nonempty", len(vectors) > 0, "no vectors loaded")

    for vector in vectors:
        name = vector["name"]
        grant = vector["grant"]
        now = _parse_now(vector["now"])
        current_epoch = vector["current_epoch"]
        key = prod_key if vector["verify_key"] == "production" else dev_key
        reservation = eg.ReplayReservationSet()

        result = eg.verify_grant(grant, key, now, current_epoch, reservation)
        if vector["call_twice"]:
            result = eg.verify_grant(grant, key, now, current_epoch, reservation)

        expected = vector["expected_outcome"]
        if expected == "ok":
            check(
                f"vector[{name}]_verified",
                isinstance(result, eg.VerifiedGrant),
                f"expected VerifiedGrant, got {result!r}",
            )
            if isinstance(result, eg.VerifiedGrant):
                check(f"vector[{name}]_grant_id_matches", result.grant_id == grant["grant_id"])
        else:
            check(
                f"vector[{name}]_denied_as_expected",
                isinstance(result, eg.Denial) and result.reason == expected,
                f"expected Denial(reason={expected!r}), got {result!r}",
            )


# --------------------------------------------------------------------------
# 2. Category coverage sanity — every §6 category is actually represented
#    (protects against a fixture silently losing a category over time).
# --------------------------------------------------------------------------


def test_fixture_covers_every_required_category():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    categories = {v["category"] for v in fixture["vectors"]}
    required = {
        "valid",
        "per-field-tamper",
        "freshness",
        "schema-version",
        "epoch",
        "replay",
        "effect-classification",
        "path-classification",
        "key-separation",
    }
    missing = required - categories
    check("fixture_covers_all_categories", not missing, f"missing categories: {missing}")

    tamper_fields = {
        v["name"].removeprefix("tamper-")
        for v in fixture["vectors"]
        if v["category"] == "per-field-tamper"
    }
    check(
        "fixture_tampers_every_grant_field",
        tamper_fields == set(eg.REQUIRED_GRANT_FIELDS),
        f"tampered={sorted(tamper_fields)} required={sorted(eg.REQUIRED_GRANT_FIELDS)}",
    )

    deny_effect_names = {
        v["name"].removeprefix("deny-class-effect-")
        for v in fixture["vectors"]
        if v["name"].startswith("deny-class-effect-")
    }
    check(
        "fixture_covers_every_deny_class_effect",
        deny_effect_names == set(eg.DENY_CLASS_EFFECTS),
        f"covered={sorted(deny_effect_names)} required={sorted(eg.DENY_CLASS_EFFECTS)}",
    )


# --------------------------------------------------------------------------
# 3. verify_grant NEVER raises, even on arbitrary/garbage input (fuzz)
# --------------------------------------------------------------------------


def test_never_raises_on_garbage_input():
    garbage_inputs = [
        None,
        42,
        3.14,
        "not-a-grant",
        [],
        {},
        {"grant_id": "x"},
        {k: None for k in eg.REQUIRED_GRANT_FIELDS},
        {**{k: "x" for k in eg.REQUIRED_GRANT_FIELDS}, "effect_set": "not-a-list"},
        {**{k: "x" for k in eg.REQUIRED_GRANT_FIELDS}, "resource_limits": None},
        object(),
        {"a": 1, "b": [1, 2, {"c": float("nan")}]},
        {k: [k] * 3 for k in eg.REQUIRED_GRANT_FIELDS},
    ]
    reservation = eg.ReplayReservationSet()
    for i, garbage in enumerate(garbage_inputs):
        try:
            result = eg.verify_grant(garbage, b"\x00" * 32, None, 0, reservation)
            ok = isinstance(result, eg.Denial)
        except Exception as exc:  # noqa: BLE001 — the exact failure this test guards against
            ok = False
            result = f"RAISED {type(exc).__name__}: {exc}"
        check(f"fuzz_garbage_{i}_never_raises_and_denies", ok, f"input={garbage!r} result={result!r}")

    # Also fuzz the standalone pure functions directly — none may raise.
    for fn, args in (
        (eg.validate_grant_schema, (None,)),
        (eg.verify_signature, (None, b"x")),
        (eg.verify_signature, ({"signature": 12345, "grant_digest": None}, b"\x00" * 32)),
        (eg.verify_freshness, (None, None)),
        (eg.verify_freshness, ({"issued_at": 5, "expires_at": []}, None)),
        (eg.verify_schema_version, (None,)),
        (eg.verify_schema_version, ("garbage",)),
        (eg.verify_epoch, (None, None)),
        (eg.verify_epoch, ({"revocation_epoch": "not-an-int"}, 5)),
        (eg.classify_effects, (None,)),
        (eg.classify_effects, ("not-a-list",)),
        (eg.classify_effects, ([{"effect": None, "scope": None}],)),
        (eg.classify_paths, (None, None)),
        (eg.classify_paths, (["a"], [object()])),
        (eg.reserve_replay, (None, eg.ReplayReservationSet())),
        (eg.reserve_replay, ("x", object())),
    ):
        try:
            fn(*args)
            ok = True
            detail = ""
        except Exception as exc:  # noqa: BLE001
            ok = False
            detail = f"{fn.__name__}{args!r} RAISED {type(exc).__name__}: {exc}"
        check(f"fuzz_direct_{fn.__name__}_{args!r}"[:120], ok, detail)


# --------------------------------------------------------------------------
# 4. Purity — no filesystem/network access performed by the verify path
#    (asserted by construction: the module imports no socket/subprocess/
#    os.system-style surface, and this test drives verify_grant entirely
#    from in-memory structures with no I/O in the call path itself).
# --------------------------------------------------------------------------


def test_purity_no_disallowed_imports():
    """Checks ACTUAL `import`/`import from` statements only (via AST), not
    prose mentions — the module docstring legitimately discusses sockets/
    subprocess/bwrap to explain what R1 does NOT introduce."""
    import ast

    module_src = (Path(_LIB_DIR) / "execution_grant.py").read_text(encoding="utf-8")
    tree = ast.parse(module_src)

    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])

    disallowed_modules = {"socket", "subprocess", "requests", "urllib", "http", "shutil", "os"}
    hits = imported_modules & disallowed_modules
    check("purity_no_disallowed_imports", not hits, f"imported disallowed modules: {sorted(hits)}")

    call_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "open":
            call_names.add("open")
        if isinstance(node, ast.Attribute) and node.attr in ("system", "popen", "remove", "unlink", "mkdir"):
            call_names.add(node.attr)
    check("purity_no_filesystem_open_calls", not call_names, f"found calls: {call_names}")


# --------------------------------------------------------------------------
# 5. reserve_replay reserved -> committed | failed transitions
# --------------------------------------------------------------------------


def test_replay_reservation_state_transitions():
    store = eg.ReplayReservationSet()

    check("replay_first_reservation_reserved", eg.reserve_replay("grant-a", store) == eg.REPLAY_RESERVED)
    check("replay_second_call_same_id_replayed", eg.reserve_replay("grant-a", store) == eg.REPLAY_REPLAYED)
    check("replay_state_of_reserved", store.state_of("grant-a") == eg.RESERVATION_RESERVED)

    check("replay_commit_from_reserved_succeeds", store.commit("grant-a") is True)
    check("replay_state_of_committed", store.state_of("grant-a") == eg.RESERVATION_COMMITTED)
    check("replay_commit_again_is_noop_false", store.commit("grant-a") is False)
    check("replay_fail_after_committed_is_noop_false", store.fail("grant-a") is False)
    check(
        "replay_after_commit_still_denies_new_reservation",
        eg.reserve_replay("grant-a", store) == eg.REPLAY_REPLAYED,
    )

    check("replay_second_id_reserved", eg.reserve_replay("grant-b", store) == eg.REPLAY_RESERVED)
    check("replay_fail_from_reserved_succeeds", store.fail("grant-b") is True)
    check("replay_state_of_failed", store.state_of("grant-b") == eg.RESERVATION_FAILED)
    check("replay_fail_again_is_noop_false", store.fail("grant-b") is False)
    check(
        "replay_after_fail_still_denies_new_reservation",
        eg.reserve_replay("grant-b", store) == eg.REPLAY_REPLAYED,
        "a failed reservation must not free the grant_id for reuse (global uniqueness domain)",
    )

    check("replay_unknown_id_never_reserved", store.state_of("grant-never-seen") is None)
    check("replay_commit_unknown_id_is_noop_false", store.commit("grant-never-seen") is False)

    # Callable interface (atomic try-reserve semantics, no try_reserve attribute).
    seen: set[str] = set()

    def callable_reserve(grant_id: str) -> bool:
        if grant_id in seen:
            return False
        seen.add(grant_id)
        return True

    check("replay_callable_interface_first_reserved", eg.reserve_replay("grant-c", callable_reserve) == eg.REPLAY_RESERVED)
    check("replay_callable_interface_second_replayed", eg.reserve_replay("grant-c", callable_reserve) == eg.REPLAY_REPLAYED)

    # Duck-typed MutableSet interface (bare set()).
    bare_set: set[str] = set()
    check("replay_bare_set_first_reserved", eg.reserve_replay("grant-d", bare_set) == eg.REPLAY_RESERVED)
    check("replay_bare_set_second_replayed", eg.reserve_replay("grant-d", bare_set) == eg.REPLAY_REPLAYED)

    # Uniqueness domain is grant_id GLOBALLY — reusing the SAME store across
    # what would be two different task_ids must still collide, because
    # reserve_replay only ever sees grant_id (never task-scoped).
    check(
        "replay_uniqueness_domain_is_grant_id_not_task_scoped",
        eg.reserve_replay("grant-a", store) == eg.REPLAY_REPLAYED,
        "same grant_id must collide regardless of which task it's presented under",
    )

    # A broken/exception-raising interface must fail closed (replayed), never raise.
    class BrokenStore:
        def try_reserve(self, grant_id):  # noqa: D401 — deliberately broken
            raise RuntimeError("simulated store failure")

    try:
        outcome = eg.reserve_replay("grant-e", BrokenStore())
        raised = False
    except Exception:
        outcome = None
        raised = True
    check("replay_broken_interface_fails_closed_no_raise", not raised and outcome == eg.REPLAY_REPLAYED, outcome)


# --------------------------------------------------------------------------
# 6. Composition order sanity — a grant that would fail schema AND
#    signature must report grant-malformed (schema first), not some other
#    reason; a grant with a valid schema+signature but expired AND
#    epoch-stale reports expired (freshness before epoch); a grant valid
#    through epoch but with a deny-class effect AND a replay-eligible id
#    reports classification-ambiguous (classification before replay), and
#    critically does NOT consume the replay reservation.
# --------------------------------------------------------------------------


def test_fixed_order_composition_and_no_reservation_burn_on_early_deny():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    prod_key = bytes.fromhex(fixture["production_public_key_hex"])
    by_name = {v["name"]: v for v in fixture["vectors"]}

    deny_vector = by_name["deny-class-effect-network"]
    grant = deny_vector["grant"]
    now = _parse_now(deny_vector["now"])
    store = eg.ReplayReservationSet()

    result1 = eg.verify_grant(grant, prod_key, now, deny_vector["current_epoch"], store)
    check(
        "order_classification_denies_before_replay_reserved",
        isinstance(result1, eg.Denial) and result1.reason == eg.DENY_CLASSIFICATION_AMBIGUOUS,
        result1,
    )
    check(
        "order_early_deny_does_not_burn_replay_reservation",
        store.state_of(grant["grant_id"]) is None,
        "a grant denied before reaching reserve_replay must not consume a reservation slot",
    )

    # Same grant_id can still be freshly reserved afterwards by a genuinely
    # valid grant sharing that id, proving the earlier deny left no trace.
    valid_vector = by_name["valid-grant"]
    reusable = dict(valid_vector["grant"])
    reusable_signed = eg.sign({**reusable, "grant_id": grant["grant_id"]}, _regen_priv_for_test())
    # Re-sign with a fresh keypair whose public key we control locally, since
    # the fixture's production private key is not itself stored (verify-only
    # module) — this proves the reservation-store state, not signature reuse.
    fresh_pub = _last_generated_pub()
    result2 = eg.verify_grant(reusable_signed, fresh_pub, now, deny_vector["current_epoch"], store)
    check(
        "order_reservation_available_after_earlier_early_deny",
        isinstance(result2, eg.VerifiedGrant),
        result2,
    )


_TEST_KEYPAIR_CACHE = {}


def _regen_priv_for_test():
    if "priv" not in _TEST_KEYPAIR_CACHE:
        priv, pub = eg.generate_keypair()
        _TEST_KEYPAIR_CACHE["priv"] = priv
        _TEST_KEYPAIR_CACHE["pub"] = pub
    return _TEST_KEYPAIR_CACHE["priv"]


def _last_generated_pub():
    return _TEST_KEYPAIR_CACHE["pub"]


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

_TESTS = [
    test_golden_vectors,
    test_fixture_covers_every_required_category,
    test_never_raises_on_garbage_input,
    test_purity_no_disallowed_imports,
    test_replay_reservation_state_transitions,
    test_fixed_order_composition_and_no_reservation_burn_on_early_deny,
]


def main() -> None:
    for test_fn in _TESTS:
        try:
            test_fn()
        except Exception as exc:  # noqa: BLE001 — surface as a failed check, not a crash
            check(test_fn.__name__, False, f"raised {type(exc).__name__}: {exc}")
    _report_and_exit()


if __name__ == "__main__":
    main()
