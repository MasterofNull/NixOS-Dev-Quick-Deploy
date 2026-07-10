# AQ-OS Cycle 0 — Planning Decision State Contract

**Status:** proposed v2 contract; owner policy defaults require explicit ratification  
**Scope:** planning direction, plan ratification and implementation authorization only

## Canonical bytes and commit point

Cycle 0 uses `aq-canonical-json-v1`, a dependency-free restricted JSON profile:

- UTF-8 without BOM; Unicode values normalized to NFC before validation.
- Objects, arrays, strings, booleans, null and signed integers only; floats/NaN/infinity are forbidden.
- Object keys are non-empty ASCII `[a-z][a-z0-9_]*`, unique and sorted by byte value.
- Integers use minimal base-10 form; strings use JSON escaping with `ensure_ascii=false` and no optional
  whitespace; arrays preserve declared order, while set-like fields are schema-sorted before encoding.
- Python reference operation: schema normalization, then
  `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` and
  UTF-8 encoding. Cross-language golden vectors are required before implementation.
- Hash records as `sha-256:<lowercase hex>`. Artifact hashes remain SHA-256 of exact raw bytes.

This deliberately avoids an unverified dependency: live Nix evaluation on 2026-07-10 found no
`python313Packages.jcs` attribute. RFC 8785 remains a Cycle 1 interoperability candidate, not the Cycle
0 hash contract.

Immutable contribution, review and aggregate artifacts are written to temporary files, flushed,
`fsync`ed, renamed and parent-directory `fsync`ed. Hashes are then verified. One canonical manifest is
the commit point and references only verified immutable artifacts. Its update requires an exclusive
writer lock plus expected prior revision/hash, temp write, file `fsync`, atomic rename and directory
`fsync`. Crash fixtures cover every boundary. Cross-file rename is never described as atomic.

## Proposed owner policy defaults

These are defaults for owner acceptance, not current authority:

- Only the owner may issue `implementation_authorized`; delegation requires a separately ratified,
  expiring policy and is not part of Cycle 0.
- Ratification requires at least two eligible `APPROVE` reviews from **both** distinct model-family
  lineages **and** distinct execution principals/trust domains, with assurance at least
  `ORCHESTRATOR_ATTESTED`.
- Every required lane must be terminal. An owner may waive an unavailable lane for this round only;
  the attributed, expiring waiver supplies zero approval weight and cannot reduce the two-family/two-
  principal minimum.
- Every eligible non-abstaining review must approve. Any eligible reject blocks until adjudication and
  a new subject revision. Operator override is a separate decision; it never rewrites consensus.
- Proxy work may satisfy a procedural assignment only if policy permits, but shares the proxying
  model's lineage and contributes no additional diversity.
- `APPROVE_WITH_CHANGES` never approves its subject. Each change becomes `ACCEPTED`, `REJECTED`, or
  `SUPERSEDED`; any accepted change creates a new subject revision requiring fresh `APPROVE` reviews.

## Direction transitions

| From | Command/event and actor | Preconditions | To | Cascade / stable failure |
|---|---|---|---|---|
| — | `create-direction`, orchestrator | Unique intent and revision 1 | `PENDING` | duplicate ID: `DUPLICATE_DECISION` |
| `PENDING` | `ratify-direction`, decision engine | Exact subject hash; eligible quorum; no reject/change/conflict; package root verifies | `RATIFIED` | otherwise remains pending with reason |
| `PENDING` | `reject-direction`, owner/decision engine | Eligible reject or owner rejection record | `REJECTED` | terminal for this revision |
| `PENDING` | invariant validator | Corrupt/missing/conflicting committed evidence | `CORRUPT` | all downstream actions blocked |
| `RATIFIED` | new direction revision | New subject hash/revision | `SUPERSEDED` | atomically supersede related plan decisions and suspend active authorization |
| `RATIFIED` | invariant validator | Previously accepted evidence becomes unverifiable | `CORRUPT` | atomically mark plans corrupt/superseded and suspend authorization |
| any nonterminal | `cancel-direction`, owner | Attributed reason | `CANCELLED` | block plan/authorization |

`REJECTED`, `SUPERSEDED`, `CORRUPT`, and `CANCELLED` are immutable terminal records. Recovery creates a
new linked revision; it never transitions a corrupt record back to validity.

## Plan transitions

| From | Command/event and actor | Preconditions | To | Cascade / stable failure |
|---|---|---|---|---|
| — | `create-plan`, orchestrator | Direction absent/unratified | `BLOCKED_ON_DIRECTION` | records exact intended direction revision |
| `BLOCKED_ON_DIRECTION` | direction ratified | Exact direction link/hash matches | `PENDING_REVIEW` | mismatch: `DIRECTION_HASH_MISMATCH` |
| — | `create-plan`, orchestrator | Current direction ratified | `PENDING_REVIEW` | — |
| `PENDING_REVIEW` | `ratify-plan`, decision engine | Exact plan/package root; eligible fresh approvals; contracts dispositioned | `RATIFIED` | otherwise remains pending |
| `PENDING_REVIEW` | eligible reject/owner rejection | Exact subject revision | `REJECTED` | terminal revision |
| `PENDING_REVIEW` or `RATIFIED` | subject mutation/new revision | Hash changes | `SUPERSEDED` | suspend active authorization atomically |
| `PENDING_REVIEW` or `RATIFIED` | invariant validator | Evidence corrupt/unverifiable | `CORRUPT` | suspend active authorization atomically |
| any nonterminal | direction becomes rejected/cancelled/superseded/corrupt | Linked direction transition commits | `SUPERSEDED` or `CORRUPT` | authorization blocked/suspended |

## Authorization transitions

| From | Command/event and actor | Preconditions | To | Cascade / stable failure |
|---|---|---|---|---|
| — | authorization evaluation | Direction or plan not ratified/current | `BLOCKED` | stable reasons identify missing predicate |
| `BLOCKED` | `authorize-implementation`, owner | Exact current direction/plan/package roots, signed-off contracts, ownership preflight, current validation evidence, expiry and use limit | `AUTHORIZED` | any absent predicate: remains blocked |
| `AUTHORIZED` | first valid assignment claim | Matching idempotency key, unexpired, unused authorization | `CONSUMED` | exactly one assignment effect |
| `AUTHORIZED` | direction/plan supersession, late critical reject, evidence corruption, ownership conflict | Cascade is in same commit as triggering decision | `SUSPENDED` | assignment blocked |
| `AUTHORIZED` or `SUSPENDED` | `revoke-authorization`, owner/policy | Attributed reason | `REVOKED` | terminal |
| `AUTHORIZED` or `SUSPENDED` | deadline | Recorded clock policy | `EXPIRED` | terminal |

`CONSUMED`, `REVOKED` and `EXPIRED` are terminal. `SUSPENDED` cannot return to `AUTHORIZED`; recovery or
review creates a new authorization record with a new ID and links the predecessor.

## Assignment and active-execution transitions

Consuming authorization creates an assignment record in the same commit; this record remains
intervenable while work is active.

| From | Command/event | Preconditions | To | Cascade |
|---|---|---|---|---|
| — | authorization consumption | Valid exact-hash authorization and idempotency key | `ASSIGNED` | Authorization becomes `CONSUMED` atomically |
| `ASSIGNED` | worker claim | Matching principal/lease and ownership hash | `RUNNING` | Emit attributed start event |
| `ASSIGNED` or `RUNNING` | direction/plan supersession, late critical reject, evidence corruption, lease revocation or ownership conflict | Triggering decision commits | `SUSPENDED` | Revoke effect capability, request cancellation and block new tool effects/checkpoints |
| `RUNNING` | bounded cancellation completes | Suspension/cancel request observed | `CANCELLED` | Preserve partial artifacts as quarantined evidence |
| `RUNNING` | task outcome | Current subject and lease remain valid | `SUCCEEDED` or `FAILED` | Immutable terminal outcome |
| `SUSPENDED` | owner/policy abort | Attributed reason | `CANCELLED` | Terminal |
| `SUSPENDED` | fresh package review and new authorization | New assignment record required | remains `SUSPENDED` | Old work never resumes in place; a new attempt may start |

If an external effect cannot be cancelled immediately, `SUSPENDED` forbids subsequent effects and
records `CANCELLATION_PENDING` until the lease/sandbox boundary confirms termination. The safety bound
and timeout are part of the task contract; silent continuation is invalid.

## Assignment invariant

Every assignment path, including legacy `CONSENSUS_LOCKED` consumers, must call one validator. It
requires an unexpired, unconsumed `AUTHORIZED` record whose direction, plan, package and ownership-
preflight hashes all match current committed revisions. Legacy enum state alone always returns
`LEGACY_STATE_NOT_AUTHORIZATION`.

## Recovery record

Recovery requires authorized actor, exclusive lock, corrupt revision/hash, quarantine path/hash,
validation failures, proposed reconstruction hash, dry-run diff hash, decision, reason, time and new
revision link. Exit codes are `0=valid`, `2=invalid evidence`, `3=internal error`, `4=lock conflict`,
`5=unauthorized actor`. Quarantine is owner-readable, non-executable, retention-bound and immutable.
A mistaken repair is superseded by another recovery record; original evidence is never modified.

## Mandatory end-to-end fixtures

Negative fixtures cover empty, abstain, reject, conditional change, proxy, self-review, unknown
producer, bad hash, unavailable required lane and late critical rejection. The positive/cascade fixture:

1. Two eligible independent approvals ratify direction only; assignment stays blocked.
2. Fresh exact-hash approvals ratify plan; assignment stays blocked.
3. Explicit owner authorization permits exactly one assignment and becomes consumed.
4. Subject mutation, late critical rejection, hash mismatch, expiry and revocation each block assignment;
   a late critical rejection after assignment suspends active execution, revokes effects and reaches a
   bounded cancelled state (or explicit `CANCELLATION_PENDING`) without resuming the old attempt.
5. Reauthorization always creates a new record; original evidence stays byte-identical.
6. Direct assignment against both current invalid `CONSENSUS_LOCKED` manifests is denied.
7. Corrupt detection → quarantine → dry-run reconstruction → owner acceptance → fresh review → new
   authorization recovers service while preserving the corrupt original.

`VERDICT: REQUEST_REVISION — the state machine and safe defaults are now explicit, but owner acceptance
of authorization/quorum policy and independent review of the final package root remain mandatory.`
