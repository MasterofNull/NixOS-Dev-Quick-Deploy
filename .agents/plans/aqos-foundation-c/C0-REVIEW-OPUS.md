# C0 CapabilityLease — Independent Review (claude-opus)

**Reviewer:** claude-opus (independent; did not author or implement this slice)
**Slice:** Foundation C — C0 report-only CapabilityLease primitive
**Spec:** `.agents/plans/aqos-foundation-c/C0-IMPLEMENTATION-SPEC.md`
**Files reviewed (5):** `config/schemas/capability-lease.schema.json`,
`scripts/ai/lib/capability_lease.py`, `scripts/ai/aq-lease`,
`scripts/testing/test-capability-lease.py`,
`scripts/testing/fixtures/capability-lease-golden.json`
**Sanity:** ran the suite → `42 passed, 0 failed`; `jsonschema 4.26.0` present (full
schema validation exercised, not the offline fallback). Empirically reproduced the two
findings below (widen slip-through returns a validly-signed `ok` child; verify crash).

---

## VERDICT: **REVISE**

One BLOCKING monotonicity gap: `attenuate()` silently **widens non-numeric constraint
values** and emits a validly-signed child that `verify()` returns `ok` for. That is a
slip-through widen in the primitive's core security property, and the docstrings claim
full tightening. The crypto core (canonicalization, HMAC, constant-time compare,
fail-closed verify ordering, signature-before-trust) is otherwise **sound** — those are
correct and I say so with reasons in the "What is correct" section. Fix the one BLOCKING
item plus the SHOULD-FIX verify-totality gap and this is a clean PASS.

---

## Findings

### BLOCKING

**B1 — `attenuate()` lets a child widen non-numeric constraint values (monotonicity fail-open).**
`scripts/ai/lib/capability_lease.py:292-307` (`_check_constraints_tighten`).
The tightening check only enforces two things: (a) every parent constraint key is present
in the child (line 296), and (b) *numeric* values may not increase (lines 301-306). Any
constraint value that is **not** an `int`/`float` — a string path scope, a list allow-set,
a bool, a nested dict — can be replaced with an arbitrarily broader value and it passes.
The resulting child is signed and verifies `ok`. Reproduced:

```
parent.constraints = {"max_bytes": 2097152, "path": "/repo/src"}
child  delta        = {"constraints": {"max_bytes": 2097152, "path": "/"}}
=> child.path = "/"   verify(child) = ok       # scope widened, accepted
parent.constraints = {..., "allowed": ["a"]}
child  delta        = {"constraints": {..., "allowed": ["a","b","c"]}}
=> child.allowed = ["a","b","c"]               # allow-set widened, accepted
```

This contradicts the function's own contract (`capability_lease.py:319-320`, "constraints
only tightened" / "a parent constraint dropped or numerically loosened by the child") and
the spec (`C0-IMPLEMENTATION-SPEC.md:50-51`, "constraints only tightened"). The schema
declares `constraints.additionalProperties: true` (`capability-lease.schema.json:51-56`),
so this is exactly the free-form surface where a fail-closed default matters. C0 is inert,
but the whole reason to ship the primitive is that C1+ consumes `attenuate()`/`verify()`
as the monotonicity oracle; shipping it with a documented-as-total guarantee that is
actually partial bakes a latent privilege-escalation path into every downstream consumer.

*Fix (small, fail-closed):* in `_check_constraints_tighten`, after the numeric branch, add
an else branch that raises unless the child value is **equal** to the parent value — i.e.
non-comparable/non-numeric constraint values may be carried through unchanged or a new key
added, but never replaced with a different value. Concretely:

```python
if isinstance(parent_v, (int, float)) and isinstance(child_v, (int, float)):
    if child_v > parent_v:
        raise ValueError(...)
elif child_v != parent_v:
    raise ValueError(
        f"attenuate: delta replaces non-numeric constraint {k!r} "
        f"({child_v!r} != parent {parent_v!r}); cannot prove tightening"
    )
```

Then add a test in `test_attenuation_rejects_widen_attempts` that seeds a string/list
constraint on the parent and asserts a broadened replacement raises (the current widen
tests only cover numeric + key-drop, `test-capability-lease.py:332-345`, which is why this
slipped past a green suite).

---

### SHOULD-FIX

**S1 — `verify()` is not total: uncaught `ValueError` on a signed lease with a non-int
integer field.** `capability_lease.py:228-230` (`epoch_stale` → `int(data["revocation_epoch"])`)
and `:238-260` (`_is_malformed` type-checks `permissions`, `actions`, `resources`,
`constraints`, `signature`, and `expires_at`, but **not** the integer fields
`revocation_epoch`, `trust_tier`, `version`). Reproduced: a lease validly signed with the
DEV key but `revocation_epoch="not-an-int"`, verified with `current_epoch=5`, raises
`ValueError` out of `verify()` instead of returning a verdict. `verify()`'s documented
contract (`:266-268`) is a *typed, report-only verdict*; a raise breaks that totality.
Note this is **not** a security fail-open — the crash needs a valid signature (the
signature check at `:275` fires `bad-signature` first for any unsigned/attacker lease, so
the path is only reachable by a key-holder who signed a type-invalid lease) — which is why
it is SHOULD-FIX, not BLOCKING. *Fix:* have `_is_malformed` reject non-`int`
`revocation_epoch`/`trust_tier`/`version` (mirrors the existing type checks and makes the
schema's `integer` constraints enforced by the library too), returning `malformed`.

**S2 — Docstrings overclaim the constraint guarantee.** `capability_lease.py:320` ("a
parent constraint dropped or numerically loosened") and the module/spec language
"constraints only tightened" read as full monotonicity. Even with B1 fixed, keep the
wording precise ("numeric values only narrow; non-numeric values must be unchanged; keys
may be added") so C1+ authors don't assume a stronger lattice than is enforced.

---

### NICE-TO-HAVE

**N1 — Library `attenuate()` discards the `is_dev` flag on the key-fallback path.**
`capability_lease.py:390` (`resolve_key()[0]`). If a library caller invokes
`attenuate(parent, delta)` with no `key`, it silently DEV-signs with no signal. The CLI is
safe (`aq-lease:119-122` always passes an explicit resolved key and banners via
`_maybe_banner`), and the module docstring warns callers, so this is minor — but consider
returning/logging `is_dev` from the fallback so a pure-library consumer can't be fooled.

**N2 — `attenuate()` does not verify the parent's signature before deriving a child.**
`capability_lease.py:322` trusts `parent` contents as-is. Correct for an inert C0 builder,
but C1+ must `verify(parent)` before trusting a chain; worth a one-line note in the
docstring so it isn't forgotten downstream.

**N3 — Offline schema fallback is weak.** `test-capability-lease.py:64-73`
(`minimal_structural_validate`) only checks required + unknown-key when `jsonschema` is
absent; enums/types/formats go unchecked. Fine as a degraded offline path (full validation
ran here), just flagging that a green run on a box without `jsonschema` proves less.

**N4 — `principal` `$def` is defined but unreferenced by the root `$ref`.**
`capability-lease.schema.json:8-37`. The lease stores `issued_to` as a bare
`principal_id` string, so nothing validates a Principal object through this schema. Not a
defect (Principal is a standalone def other schemas can `$ref`), just latent.

---

## What is correct (verified, not rubber-stamped)

- **Canonicalization is deterministic and collision-free for the lease shape.**
  `canonical_payload` (`:160-173`) uses `json.dumps(..., sort_keys=True,
  separators=(",", ":"))`, and `sort_keys=True` sorts **recursively** at every nesting
  level (confirmed by the nested-`permissions` shuffle test passing, `:189-198`). Signable
  set = "everything except top-level `signature`" via a dict comprehension (`:170`). A key
  literally named `signature` nested inside `constraints`/`input_schema` is **not** stripped
  (only the top-level key is), so it stays signed — no strip-collision. All numeric lease
  fields are ints; no float-repr ambiguity in the fixed schema. No flattening, so two
  distinct leases cannot map to the same signable bytes.
- **Signature is real HMAC, constant-time compared.** `sign` (`:176-178`) is
  `hmac.new(key, payload, sha256)` — HMAC, not `sha256(key||msg)`, so no length-extension
  footgun. `verify` (`:275`) uses `hmac.compare_digest`, not `==`.
- **`verify()` is fail-closed and correctly ordered.** malformed → bad-signature → expired
  → epoch-stale → ok (`:270-284`). Critically, the **signature is checked (`:273-275`)
  BEFORE** `is_expired`/`epoch_stale` read `expires_at`/`revocation_epoch`, so an
  attacker-mutated `expires_at` or `revocation_epoch` changes the canonical payload and is
  caught as `bad-signature` — never silently trusted. `compare_digest` on unequal-length
  hex returns False (no throw). Every tampered/malformed/missing path returns a non-`ok`
  verdict (except the S1 crash, which still never returns `ok`).
- **DEV-key safety is sound.** The DEV key is an obvious non-secret
  (`b"...DO-NOT-TRUST-IN-PRODUCTION"`, `:40`); `resolve_key` returns `is_dev` and never
  raises on a missing `/run/secrets` path (`:181-201`); the CLI banners on stderr whenever
  the fallback is used (`aq-lease:50-52,69,82,119`). A DEV-signed lease only verifies under
  the DEV key, so a production verifier with a real key returns `bad-signature` — a dev
  signature cannot be mistaken for trust-rooted. No `/run/secrets` dependency to run
  offline (confirmed: suite is fully offline).
- **Attenuation is otherwise complete + verifiable.** actions/resources intersected and
  membership-checked (`:337-346`), `trust_tier`/`expires_at` upper-bounded (`:347-356`),
  `parent_lease_id` set and child re-signed (`:384-391`); the re-signed child verifies `ok`
  (test `:297-300`). Only the non-numeric-constraint dimension (B1) is unguarded.
- **Schema matches the code contract.** All 16 lease fields required with
  `additionalProperties:false`; enums (`kind`, `zero_trust_behavior`) correct; `signature`
  `minLength:1` matches the `_is_malformed` non-empty check; `version` `minimum:1`,
  `trust_tier`/`revocation_epoch` `minimum:0` align with the builders' defaults. No field
  the code writes is forbidden by the schema, and none the schema requires is unwritten.
- **Tests are real, not vacuous (42/42).** Tamper tests deep-copy then mutate a signed
  field and assert `bad-signature` (`:135-163`) — genuine mutation, not a re-sign.
  Canonical-determinism actually reverses key order at top level and nested
  (`:171-205`) and pins `sig == golden["signature"]`. Widen-reject covers action/resource/
  trust_tier/expires_at/drop-constraint/numeric-loosen (`:303-345`). The one coverage hole
  is the B1 dimension (non-numeric constraint widen), which is why the suite is green
  despite the defect.

---

## Bottom line

Crypto core, fail-closed verify, DEV-key hygiene, schema, and test integrity are solid and
correctly built. The single blocker is that monotonic attenuation is advertised as total
but only enforces numeric/key-presence tightening, so a non-numeric constraint can be
widened into a validly-signed child. Close B1 (fail-closed on non-numeric replacement +
a covering test) and S1 (make `verify` total), tighten the S2 wording, and this slice is a
PASS.
