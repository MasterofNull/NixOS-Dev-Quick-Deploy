# Foundation C — C2 Build Re-Review (codex round 2) — VERDICT: PASS

Binding independent re-review of the C2 enforcement build after the round-1 REVISE fold.

## Chain
1. **Build** (Sonnet, Rule-17 cheapest-eligible override: security-critical multi-file enforcement + adversarial tests, above local's envelope) — 5-file ceiling, flag DEFAULT-OFF.
2. **Round-1 binding review** (codex, `codex-20260729-043758-15dyvwxxxxxx.log`): **REVISE** — 2 HIGH blocking + 3 MEDIUM non-blocking, all independently proven with adversarial output.
3. **Fold** (Sonnet) — both HIGH + all 3 MEDIUM, within the 5-file ceiling, nothing else touched. Suite 56→83 tests.
4. **Round-2 binding re-review** (codex, `codex-20260729-163121-22icsvxxxxxx.log`): **PASS** (this record).

## Round-1 findings and their closure (codex-confirmed adversarially in round 2)
- **HIGH-1 — zero-trust posture not monotonic; caller could weaken a signed strip.**
  Fixed: `_normalize_zero_trust()` (unknown/malformed → "strip" fail-safe; None/False → "none"
  contribution, never overrides a signed strip) + per-tool effective posture `inherited_strip OR
  lease_strip` in BOTH candidate (`capability_lease_gate.py:570`) and first-party (`:623`)
  branches. Round-2: privileged signed-strip leases denied with ctx `"none"`, `False`, and
  omitted; a safe signed-strip tool stays admitted — verified through switchboard `_admit_tool_call`.
- **HIGH-2 — manifest↔signed-risk metadata mismatch did not fail closed (codex-3).**
  Fixed: `_lease_bound_security_projection()` / `_manifest_bound_security_projection()`; after
  signature verify, any divergence between the verified lease's bound metadata and the validated
  manifest entry denies with `bound-metadata-manifest-mismatch` (`capability_lease_gate.py:606`) —
  a tripwire that can only deny, never supply the risk decision. Round-2: independent mutations of
  actions, network/write/exec capability, secret/delegate resources, trust tier, constraints,
  resources, and zero-trust behavior all denied; untampered admission succeeded.
- **MEDIUM-3 — audit decisions discarded.** Fixed: `_emit_lease_decision_audit()` +
  `_lease_gate_exception_decision()` wired into `_admit_tool_call` (`switchboard.py:1161`),
  schema-conformant JSON to stderr behind the flag-ON branch, logging wrapped so it can never
  affect admission; the import/exception path now emits an audit record too.
- **MEDIUM-4 — test realism.** `BUNDLE_TOOLS` now derives from live `switchboard._TOOL_LEASE_PRIORITY`
  keys (`test-capability-lease-gate.py:89`); B1 cleanup saves+restores `_capability_lease_request_ctx`.
- **MEDIUM-5 — schema unvalidated.** `test_decision_schema_validates_admit_deny_degrade`
  (`test-capability-lease-gate.py:691`) validates real admit/deny/degrade decisions.

## Invariants re-confirmed (round 2)
- CAPABILITY_LEASE_ENFORCEMENT default OFF (`switchboard.py:656`); flag-OFF path byte-behavior-identical
  (parity tests pass; no audit stderr on flag-OFF calls).
- `enforce()` never raises (outer fail-closed wrapper intact); deny-closed everywhere; DEV-key +
  unresolvable-epoch degrade; first-party leases non-self-reissuing after epoch changes.
- Only the 5 ceiling files changed. Suite: **83/83 passing**.

## Commit consequence — L2B golden re-pin (in the same cycle)
The C2 edit to `ai-stack/switchboard/switchboard.py` changes a file pinned by the
`local-inference-l2b` golden manifest (`scripts/testing/fixtures/local-inference-l2b-payload-golden.json`,
`live_source_manifest`). C2's change is additive tool-admission code and does NOT touch the payload-
canonicalization path the L2B contract guards (source-shape predicate `contains "payload =
build_llama_payload("` still holds). The single manifest hash for switchboard.py was re-pinned
(`8744a455…` → `8fbc28b9…`) as part of this reviewed commit; `test-local-inference-l2b.py` returns
to green (16 checks, exit 0), which resolves the full drift→transport-health→dashboard-projection
cascade.

## Status: CLEARED to commit — flag DEFAULT-OFF
Enforcement is NOT live. Turning `CAPABILITY_LEASE_ENFORCEMENT` on in the running system (plus the
Nix option, Rule 13) remains a further, separate owner act.
