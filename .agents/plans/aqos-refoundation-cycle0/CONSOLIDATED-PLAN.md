# AQ-OS Refoundation Cycle 0 — Consolidated Execution Plan

**Status:** `REQUEST_REVISION`; not ratified; implementation not authorized  
**PRD:** `.agent/PROJECT-AQOS-CYCLE0-TRUTH-PRD.md`; state/evidence contracts:
`STATE-CONTRACT.md` and `EVIDENCE-ALGEBRA.md`  
**Owner brief:** `.agents/prompts/AQOS_OWNER_NEXT_CYCLE_META_PROMPT.md`  
**Review condition:** pending genuine local/Qwen and Antigravity/Gemini disposition plus independent
review of the exact amended hashes.

## Authorization contract

| Decision | Meaning | Minimum evidence |
|---|---|---|
| `direction_ratified` | Product trajectory and Cycle 0 ordering accepted | Eligible model-diverse proposals, no critical objection, hashed aggregate |
| `plan_ratified` | Exact scope, contracts, tests, budgets, rollback and stop conditions accepted | Explicit reviews of the exact package-root hash and acknowledged inter-slice contracts |
| `implementation_authorized` | Declared surfaces may be modified | Ratified direction/plan, owner action, no overlapping work, Intent Lock and isolated-test preflight |

No earlier state enables `ASSIGNED` or `IMPLEMENTING`. Only an explicit authorization record does.

## Sequence

```text
C0.1 decision/evidence vocabulary ──► C0.2 score/evidence semantics
          │                                      │
          └──────────────► C0.3 authority and retirement ledger
                                                 │
                                                 ▼
                                      Cycle 1 decision package
```

C0.2 may begin after the C0.1 evidence/reason-code contract is reviewed. C0.3 may perform discovery
in parallel, but its authority decisions cannot be ratified until both preceding contracts are stable.

## C0.1 — Evidence-bound decision and round truth

**Objective:** prevent round, contribution, aggregate, review and implementation authority from
disagreeing.

### Scoped discovery and edit surfaces

Discovery:

- `scripts/ai/lib/round_state.py`
- `scripts/ai/lib/round_contribution.py`
- `scripts/ai/lib/round_aggregate.py`
- `scripts/ai/aq-collab-round`
- `scripts/testing/test-round-state-machine.py`
- `scripts/testing/test-round-contribution.py`
- `scripts/testing/test-round-aggregate.py`
- `scripts/testing/test-round-golden.py`
- `.agents/plans/aqos-v1/round.json`
- `.agents/plans/aqos-refoundation-cycle0/round.json`
- collaboration operator documentation and activation audit

Permitted edits are the four implementation files, their four focused test files,
`scripts/testing/test-round-decision-authorization.py`, collaboration operator documentation, Phase-0
registration, and the existing collaboration projection only:
`dashboard/backend/api/routes/collaboration.py`, `dashboard.html`, and `assets/dashboard.js`. No Redis,
Postgres, Qdrant, coordinator service, new route, new broker or new service.

### Contract

- Exact artifact bytes use SHA-256. Structured records use the exact dependency-free
  `aq-canonical-json-v1` contract in `STATE-CONTRACT.md`; RFC 8785 is not the Cycle 0 algorithm.
- A hash proves integrity only. Producer identity, authorization and attribution assurance are separate.
- Every contribution binds lane/dispatch, producer/model lineage, subject revision/hash, artifact path
  and hash, verdict, landing time, parser/source class, rationale, evidence anchors, risks and tests.
- Prose fallback remains evidence but cannot approve. `ABSTAIN`, unavailable, failed, timed-out,
  unparsed, proxy and self-review lanes contribute zero approval weight.
- Proposed quorum policy requires both two independent model-family lineages and two independent
  execution principals/trust domains, assurance ≥`ORCHESTRATOR_ATTESTED`, all required lanes terminal,
  and no eligible reject. Owner waiver supplies no vote and cannot reduce diversity. Proxy and proxied
  lanes share one lineage. This policy remains an owner-ratification blocker.
- `APPROVE_WITH_CHANGES` never approves or counts for its subject. After typed changes create a new
  subject revision, only fresh `APPROVE` reviews of that exact hash can ratify it. An eligible `REJECT`
  requires adjudication or a new revision.
- Aggregate path/hash, contribution hashes, verdict tally, unresolved conflicts, policy revision,
  decision stage and transition history commit under the lock/fsync/compare-and-swap protocol in
  `STATE-CONTRACT.md` before ratification.
- Assignment checks a separate explicit implementation-authorization record.

### Operator controls

- `audit`: read-only invariant check; stable reason codes; `0=valid`, `2=invalid`.
- `reopen`: append-only return to collection that preserves the invalid/provisional revision.
- `abort`: explicit attributed owner action with reason.
- Recovery may reconstruct only from verified preserved evidence, first in dry-run; it cannot fabricate
  missing evidence or silently rewrite history.

### Validation

- Unit fixtures: empty extraction, all reject, all abstain, malformed sidecar, prose fallback, duplicate,
  self-review, missing aggregate, hash mismatch, proxy quorum, required-lane absence, unresolved change,
  late concurrence and late conflict.
- Replay copies of both false-locked AQ-OS manifests in a temporary root. Expected: corrupt decision
  evidence and blocked assignment; these are two distinct facts, not one ambiguous state.
- Run the positive/cascade/recovery fixture from `STATE-CONTRACT.md`; the suite must prove one valid
  authorization path rather than pass by rejecting everything.
- Open/collect/audit a bounded fixture round under `/tmp`; two replays produce identical state/hashes.
- Assert tests cannot write live PULSE, RESUME, registry, production round directories or QA `latest`.
- `py_compile`, `bash -n`, focused tests, integration-path AQ check, dashboard/report visibility, Tier 0.

### Budgets

| Resource | Limit |
|---|---:|
| Model/APU/GPU calls in validation | 0 |
| Unit suite / isolated CLI replay | target ≤10 s / ≤60 s |
| Incremental peak RSS | ≤128 MiB |
| Lanes / changes / anchors / amendments | 16 / 128 / 256 / 8 |
| Contribution sidecar / manifest | ≤256 KiB / ≤1 MiB |
| Implementation prompt / local review | ≤1,500 input tokens / ≤180 output tokens, one retry |
| Metric labels | fixed state/reason vocabulary; never IDs, paths, prompts or errors |

### Rollback, retirement and stop

Deploy compatible readers/auditor before writers; preserve v1 evidence byte-for-byte. On migration
failure, mutation is disabled and legacy state is displayed as `invalid_legacy_evidence`, never approved.
Retire lane-status authorization, prose-derived approval, and unhashed Markdown authorization in this
slice. Stop if a non-approving fixture ratifies, machine/human verdicts differ, a live file is touched,
or scope requires a service/store/broker change.

## C0.2 — Truthful evidence, effectiveness and immutable QA provenance

**Objective:** state what each signal proves and prevent missing, malformed, stale, conflicting,
unauthorized or low-sample evidence from becoming a pass.

### Scoped discovery and edit surfaces

Discovery:

- `scripts/ai/aq-report`
- `scripts/ai/lib/agent_run_events.py`
- `config/schemas/maeah/agent-run-event.schema.json`
- `scripts/testing/harness_qa/main.py`, `scripts/ai/_aq-qa-bash`, `scripts/ai/aq-auto-remediate.py`
- `dashboard/backend/api/routes/aistack.py`
- focused report, event, useful-token, dashboard and contract tests
- the frozen reader/writer inventory in `C0.2-SURFACE-INVENTORY.md`

Permitted production edits are exactly the files in `C0.2-SURFACE-INVENTORY.md`; focused test filenames
are frozen in the Intent Lock before editing. A new consumer triggers plan amendment and re-review,
never silent expansion. No new dashboard view, service, database, broker or framework.

### Contract

- Use the PRD's orthogonal `EvidenceCondition`, `ClaimAssessment`, and `GateOutcome` algebra.
- Every metric records claim class, numerator, denominator, sample size, producer/source, artifact/run
  ID, generated/observed times, freshness window, environment limitations and threshold policy.
- Operator trust cannot pass when required trace, review, validation or intent evidence is unknown.
- Hint adoption, locality and other proxies remain named inputs until proven outcome-linked.
- Each QA invocation writes immutable canonical payload bytes containing run ID, monotonic start
  sequence, times, commit/dirty state, phase/results and bounded environment fingerprint. Its SHA-256
  is stored in the pointer/sidecar, never recursively inside the hashed payload.
- `latest-qa-results.json` becomes a versioned atomic pointer containing run ID, start sequence, path,
  byte length, hash and completion time. Under the same exclusive writer lock, compare-and-swap selects
  the highest lock-protected sequence allocated by the QA evidence producer at invocation start; a slow
  older run cannot displace a newer invocation and no coordinator dependency is introduced.
  Pointer write uses temp file, `fsync`, atomic replace and parent-directory `fsync`.
- Consumers verify pointer and artifact hash. No secrets, prompts or unbounded logs enter artifacts.
- Proposed retention owner is the QA evidence producer. Privacy defaults to `internal`; producer-side
  allowlist/redaction/secret scan precedes persistence; files are owner-read/write only; symlinks and
  path traversal are rejected; suspicious artifacts are quarantined and automation blocks.
- Initial soft targets are seven days and 64 artifacts; 64 MiB is a hard cap. Prune oldest unreferenced,
  expired artifacts first, recording deletion evidence. Never prune the pointer target. If only the
  referenced artifact violates the hard cap, pointer publication fails `ARTIFACT_TOO_LARGE`, the
  artifact is quarantined, and the previous verified pointer remains.
- `aq-report --machine` is the canonical serialized calculation. Dashboard synthesis is retired; it
  displays the same status, dimensions, reasons, provenance, age and hash-verification state.

### Operator controls and validation

- Automation receives explicit `automation_allowed` and blocking reasons.
- Recovery is rerun, inspect immutable evidence, or select a prior verified run—never edit the score.
- Golden fixtures: all-valid, missing, malformed, stale, insufficient sample, failed validation,
  missing review, conflicting evidence and rejected producer.
- Two concurrent QA writers use an isolated telemetry root; both artifacts survive and pointer selects
  the highest start sequence. The live Phase-0 run must acquire this same exclusive writer lock; a
  failed lock acquisition leaves live validation incomplete rather than inferring exclusivity.
- Corrupt pointer/artifact, interrupted write, retention and GC fixtures.
- CLI and dashboard/API consume identical injected fixture results.
- Live validation reads real report/dashboard, then performs one bounded Phase-0 run only after proving
  no other writer is active. It never runs destructive concurrency against production telemetry.

### Budgets

| Resource | Limit |
|---|---:|
| Model/APU/GPU calls | 0 |
| `aq-report` runtime | ≤10% regression and absolute ≤60 s |
| Scorecard endpoint | local artifact p95 target ≤250 ms |
| Incremental RSS | ≤64 MiB |
| QA artifact / pointer / retained total | ≤2 MiB / ≤4 KiB / ≤64 MiB |
| Dimensions / stable reason codes | ≤8 / ≤64 |
| Metric cardinality | no IDs, paths, prompts or free-form errors as label values |

### Rollback, retirement and stop

Add versioned fields before retiring legacy fields; legacy reads are marked `legacy_untrusted=true`.
Rollback can regenerate a legacy view from a verified immutable artifact but cannot restore concurrent
direct writes. Retire mutable shared result content, dashboard-local score calculation, invalid-event
silent exclusion and empty blockers on non-pass required claims. Stop if required unknown can pass,
CLI/dashboard disagree, concurrent evidence is lost/unverifiable, GC can delete the pointer target,
or live state is clobbered.

## C0.3 — Authority, projection, bypass and retirement ledger

**Objective:** name one current owner and one target disposition for every critical state before Cycle 1
moves durable truth.

### Outputs and permitted surfaces

Inventory run, task, event, review, artifact, capability, lease, eval, memory, config, telemetry and
planning decisions across JSONL, Markdown, Redis, Postgres, Qdrant, dashboard caches, sidecars,
registries, PULSE/RESUME, direct model callers and legacy CLIs.

Permitted additions/edits:

- `config/system-state-authorities.yaml` — proposed registry SSOT
- `config/schemas/system-state-authorities.schema.json`
- `scripts/governance/check-state-authorities.py` — bounded read-only checker
- `scripts/testing/test-state-authorities.py`,
  `scripts/testing/test-dashboard-governance-projection.py`, and
  `config/validation-check-registry.json`
- canonical architecture and AQ-OS decision documents as projections
- existing read-only audit projection only: `dashboard/backend/api/routes/audit.py`, `dashboard.html`,
  and `assets/dashboard.js`

No runtime writer, service, new route, store or database migration.

Each registry row separately records `observed_authority_claims[]`, `observed_writers[]`,
`current_condition = SINGLE | SPLIT_BRAIN | UNKNOWN | UNOWNED`, selected target authority,
projections/readers, ordering/revision, provenance/freshness, bypasses, adjudicator/recovery owner,
target hypothesis, migration and rollback owner, resolution/deletion deadline, usage/divergence metric,
exception owner and expiry. Discovery never invents one authority to make validation pass. A clean cycle means no
divergence, no fallback write, successful replay/restore and verified zero legacy writes. Compatibility
expires after two clean release cycles or 90 days, whichever occurs first; exceptions are explicit,
evidence-backed, owned and expiring.

### Validation and budgets

- Schema validation requires truthful observed claims. `SPLIT_BRAIN`, `UNKNOWN` and `UNOWNED` are valid
  discovery values but block C0.3 ratification until an adjudicated target disposition and deadline exist.
- Bounded scan of ≤5,000 files with explicit truncation and JSON `{meta, findings}` output.
- Undeclared-writer fixture fails; test/example/generated paths do not create production debt.
- Every projection has rebuild source; every shim has use/divergence telemetry and deadline.
- Generate one evidence graph each for the invalid round and a failed QA/report run. Write the Cycle 1
  storage ADR to `docs/architecture/aqos-cycle1-state-spine-adr.md` and project reviewed authority
  summaries into `docs/architecture/canonical-kernel-declaration.md` only.
- Checker ≤15 s, incremental check ≤10 s, peak RSS ≤256 MiB, output ≤5 MiB, registry ≤128 objects and
  ≤32 projections per object, zero inference/APU/GPU work.
- Operator commands: `--machine`, `--explain <object>`, and `--changed`; checker remains read-only.

If checker registration is noisy, rollback only the CI registration while retaining reviewed findings.
Incorrect registry declarations are corrected by reviewed new registry revisions or reverted as source;
the C0 registry/checker cannot enforce runtime behavior.
Retire free-form prose as authority and explicitly demote caches, sidecars and semantic stores where
appropriate. Stop ratification—not discovery—on split-brain/unknown/unowned authority; stop execution on unbounded scans, undocumented new surfaces, missing
shim owner/telemetry/deadline, or any implication that Cycle 1 storage is already authorized.

## Integration visibility and deployment order

| Slice | Phase-0 integration check | Existing visible surface | Alert/operator action |
|---|---|---|---|
| C0.1 | `0.10.27` validates positive/negative/cascade assignment invariants | Existing `#section-collaboration`, `/api/collaboration/metrics/summary`, `dashboard/backend/api/routes/collaboration.py`, `dashboard.html`, and `assets/dashboard.js` gain decision stage, evidence condition and block reason | Invalid/corrupt decision blocks assignment; operator audits, reopens or aborts |
| C0.2 | `0.10.28` validates isolated concurrent writers and required-unknown blocking | Existing `#section-effectiveness-scorecard` and `/api/aistack/effectiveness/scorecard` gain run/hash/age/reasons | Spider alerts invalid provenance; operator reruns, inspects or selects verified evidence |
| C0.3 | `0.10.29` runs bounded authority checker and reports contested/unowned count | Existing `#section-audit-integrity`, `/api/audit/operator/integrity`, `dashboard/backend/api/routes/audit.py`, `dashboard.html`, and `assets/dashboard.js` gain last check, age and blocker count; dated exemption from a new panel | Operator explains object, adjudicates registry revision or records expiring exception |

Checks are registered in `scripts/testing/harness_qa/phases/phase0.py` and `ALL_PHASES` through the
existing Phase-0 mechanism. C0.3 is a build-time checker and receives a 2026-07-10 exemption from a new
dedicated dashboard panel; its result is appended to the existing operator-audit source and projected
by the existing audit route/card. It does not add a runtime authority or new route.

C0.2 deployment order is producer-first additive schema/artifacts → compatible report consumers →
dashboard backend restart and live endpoint test → frontend projection → retirement of old synthesis.
Rollback reverses consumer order while retaining immutable artifacts and a version-compatible reader;
the dashboard backend is restarted and the route plus card are live-tested before rollback closes.

Resource baselines are recorded before edits with five cold and twenty warm samples in an idle state,
then repeated under one representative local-inference request. Runtime uses p50/p95 monotonic duration;
RSS uses `/usr/bin/time -v` maximum resident set. Missing measurement telemetry fails the budget gate.

## Inter-slice contracts

| Producer | Consumer | Required contract |
|---|---|---|
| C0.1 | C0.2 | Stable evidence IDs, raw-byte hashes, producer assurance, timestamps, freshness and reason codes; hashes are not identity |
| C0.1 | C0.3 | Round decision, review, aggregate, contribution and authorization receive distinct authority rows |
| C0.2 | C0.3 | One QA artifact is invocation evidence; pointer/dashboard are projections; report scorecard producer is declared |
| C0.3 | Cycle 1 | Reviewed authority/retirement registry and storage ADR evidence; no implicit implementation authority |

Each contract needs implementer plus independent reviewer `AGREED` against exact hashes before the
consumer changes shared surfaces.

## Cycle-level stop conditions

Stop if a pending/unavailable lane becomes agreement; model diversity is below policy; active work
overlaps; an isolated test touches production collaboration/telemetry/registry/database state; a new
service/broker/dependency/UI/storage migration enters scope; Tier 0, live validation, security or resource
budgets fail; a compatibility surface lacks same-cycle retirement bounds; or machine and human state
disagree.

## Unresolved questions blocking plan ratification

1. Is implementation authorization owner-only, or delegable under a signed policy?
2. What exact required-lane roster and model-family minimum applies during provider unavailability?
3. May a proxy satisfy procedural review while explicitly contributing no diversity?
4. Does plan ratification require unanimity, or unanimity of a formally closed roster plus owner waiver?
5. What deployed/dev telemetry roots, environment fingerprint and retention owner apply to QA evidence?
6. What are the measured runtime/RSS baselines for report, round audit and Phase 0?
7. Is the unreadable Codex state database a failure, observer limitation, or degraded-confidence skip?
8. Which writers currently own review completion, useful-token events and delegation completion?
9. Which C0 surfaces are presently owned by concurrent work and require handoff?

`VERDICT: REQUEST_REVISION — the plan is executable in shape, but pending model-diverse review,
authorization-policy choices and unsigned inter-slice contracts block ratification and implementation.`
