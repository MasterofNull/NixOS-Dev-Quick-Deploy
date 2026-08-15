---
doc_type: design-packet
id: herdr-h2a-implementation-inventory-20260808
title: HERDR H2A split pure-projection implementation inventory
status: draft
owner: codex
date: 2026-08-09
parent_prd: herdr-agent-operations
contract_zero_sha256: 716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48
implementation_authority: true
runtime_authority: false
frozen_input:
  H1-accepted-hash: 3f68911f87115973febed0dbccf2881da8c6fb51
  H1-independent-receipt: .agents/plans/herdr-agent-operations/H1-CORRECTION-INDEPENDENT-REVIEW-20260815.md
  H1-independent-receipt-sha256: 5b62525779871e57c7d842a9e55e80d6c5645f37e6ab32a787bb0569bc252ab0
---

# HERDR H2A split pure-projection implementation inventory

## Authority, prerequisite, and revision result

This design packet closes Codex self-review findings B1-B7 and the independent orchestrator
concurrence. It prepares two future slices that are independently closed, independently digestible,
and independently reviewable:

1. **H2A-P0** projects canonical AQ work facts as `aq.operator-context.v1`.
2. **H2A-P0B** projects HERDR presentation observations as `aq.herdr.presentation.v1`.

The owner-ratified semantic authority is contract-zero,
`.agent/collaboration/integration-contracts/herdr-h2-canonical-aq--operator-context.md`, SHA-256
`716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48` (the exact current bytes of
2026-08-09). The former `12c9…9b90` value was a stale pre-revision digest and is explicitly superseded;
it is not an accepted basis for this packet. The two projections do not
share a schema, resolver, revision, digest, source ledger, or authority. Neither projection is a
writer, action surface, observation adapter, consumer, service, or runtime integration.

H1 is accepted by atomic correction commit `3f68911f87115973febed0dbccf2881da8c6fb51`, with final
independent `PASS` receipt
`.agents/plans/herdr-agent-operations/H1-CORRECTION-INDEPENDENT-REVIEW-20260815.md`, SHA-256
`5b62525779871e57c7d842a9e55e80d6c5645f37e6ab32a787bb0569bc252ab0`. Its frozen behavior files remain
byte-bound: `flake.nix` `58e145a0bcd73caf786cbe905d3cc1b07948a77ddb149c4ec83d2a43171141c8`,
`nix/pkgs/herdr.nix` `7927d39a3c1447e3cacf9d87b42fdee228bd7d018d8fc4eede2bfe0d6bd8266d`,
`nix/home/herdr.nix` `5798f1ac644515a17d3cbfd352d165dbd850c07ee844e6edac35fdc5f3c9793d`,
`scripts/ai/aq-herdr` `c8c452923d9058bbc90fad320ec36ad861437ceb3be5603566737c855c84632a`,
and `docs/operations/herdr-agent-operations.md` `b2b38501a891d476221de3ed4d45d1bb2a5ea471742b86d797af951fb8eac54b`.
The accepted correction is its eight-path manifest: correction PRD/design; final and revision-1 independent
review receipts; supply-chain report; deterministic SPDX SBOM; tracker; and H1 contract test. Evidence binds
the no-link package target `/nix/store/cjshi0cjx9p1m0plka95b9xpssyranzj-herdr-0.7.5`, version `0.7.5`, real
Home Manager evaluation `PASS`, and deterministic SBOM SHA-256
`cfa9a5904c50fdc01ed839bd5f3f827dc6c57ec36e4191e61879900938da715c`.

The owner repeatedly directed “resume all previous operations” and authorized safe repo-local progression.
Accordingly, implementation authority is now granted **only** for the ten exact `NEW` pure-projection paths
in the two five-file ceilings below. Before any path creation, the implementer must record a fresh collision
scan and active-writer/lease result. Each pure slice still requires a fresh independent hash-bound `PASS`
before it can be frozen, staged, or committed. This amendment does not authorize any extra file, adapter,
consumer, runtime, control, deployment, or activation work.

## H2A-P0 — `aq.operator-context.v1` only

### Boundary

H2A-P0 answers only: **what does canonical AQ authority say about the work?** It has no HERDR import,
library, binary, config, socket, process, pane, session, layout, package, service, network, clock,
environment, filesystem, or runtime dependency. The resolver accepts only closed, bounded,
already-sanitized value envelopes and performs no I/O or mutation.

`aq.operator-context.v1` has no presentation input in H2A-P0. Its contract-zero `presentation_observation`
and `drift` leaves are deterministically `unknown` with reason `comparison_not_materialized`; no
presentation value, digest, or observation enters this resolver. Contract #5 owns the sole typed comparator
specified below. Its absence cannot degrade or change canonical AQ facts.

### Exact five-file ceiling

| action | exact future path | bounded responsibility |
|---|---|---|
| NEW | `config/schemas/operator-context.schema.json` | Closed JSON Schema for exactly `aq.operator-context.v1`; `additionalProperties: false` at every object and array-item boundary; bounded enums, strings, arrays, counts, reference tokens, revisions, digests, and age buckets. |
| NEW | `config/operator-context-source-to-field-ledger.v1.json` | Machine-checkable row for every schema leaf: canonical adapter or pure derived rule, unknown propagation, bounds/redaction, evidence semantics, and authority. No unledgered field may serialize. |
| NEW | `scripts/ai/lib/operator_context_projection.py` | Pure deterministic resolver over normalized values; canonical serialization and SHA-256; no adapter imports, I/O, clock, environment, network, process, HERDR, or writer dependency. |
| NEW | `scripts/testing/fixtures/operator-context-golden.json` | Closed replay corpus containing normalized inputs, exact canonical bytes/digests, unknown/conflict cases, R1-R7 human-comprehension vectors, and privacy/redaction vectors. |
| NEW | `scripts/testing/test-operator-context-projection.py` | Hermetic schema/ledger completeness, determinism, parity, privacy, bounding, reference, unknown-preservation, canonical-state isolation, and golden-vector tests. |

Any sixth file, adapter change, consumer edit, schema alias, environment variable, port, URL, or runtime
dependency is an undeclared dependency and stops H2A-P0 for inventory amendment and re-review.

### Frozen operator-context shape and R1-R7 semantics

Canonical serialization order is exactly:

```text
schema_version
projection_revision
generated_at
freshness
source_health
source_digests
mission
work
attention
evidence
learning
coverage
policy
```

All objects and enums are closed. Unavailable or unsafe facts use explicit `unknown`, `unavailable`,
`stale`, `degraded`, or `mismatch` states plus bounded reason/evidence tokens. They never become `0`,
`false`, `healthy`, `complete`, `accepted`, or blank `--`.

- `mission` carries a bounded objective or `unknown`, canonical workflow phase, definition-of-done
  total/satisfied/unknown counts, next gate, blocker, drill-in reference, and evidence freshness.
- `work[]` carries bounded work/parent references, child count, role/lane/slice categories, canonical
  state and record revision, `interaction_mode`, steerability reason, parent drill-in, deterministic
  `unknown` presentation observation/drift until the contract-#5 comparator is materialized, progress age,
  blocker, next gate, and allowed-control
  categories. Parent-controlled child work is `through_parent`; it is not misreported as failed input.
- `attention[]` carries bounded reason/evidence references, recommendation category, required authority,
  action availability, deterministic rank, and stable cognitive-load group. Recommendations contain no
  command, endpoint, argv, mutation payload, or inferred authority.
- `evidence[]` carries opaque bounded references, source authority, subject/revision digest, freshness,
  and availability; never raw receipt, content, path, prompt, output, reasoning, or identity.
- `learning` carries accepted lesson/pattern counts, improvement candidates by bounded state,
  regression/repeated-failure counts, last verified improvement age, source health, and evidence refs.
- `coverage` distinguishes known from unknown sources/fields and records visible-item budgets and
  overflow counts. Unknown counts are never healthy zero.
- `policy` freezes schema/profile revision, redaction and bounds profiles, priority order, canonical
  serializer, digest algorithm, tri-state policy fields, and reference grammar; it has no controls.

### Named value-envelope sources and complete ledger

The resolver accepts these names only; each envelope is a value, not an adapter or source lookup:

| envelope | canonical authority | allowed facts | prohibited content/effect |
|---|---|---|---|
| `program_workflow_facts` | future read-only normalizer over `scripts/ai/lib/task_registry.py` | current safe facts only: `task_ref`, lane, role, state, record_revision; mission, parent/child, acceptance, gate, and blocker remain `unknown` | writes, raw prompt fallback, provider/session identity |
| `exclusive_lease_facts` | future read-only normalizer over `scripts/ai/lib/capability_lease.py` | source availability only; no owner or authority claim until an exact lease-reader contract is accepted | issue, revoke, renew, role-label authority inference |
| `independent_review_facts` | future receipt reader over `scripts/ai/lib/review_feedback_contract.py` | `unavailable|unknown` only: current module defines receipt models, not a receipt reader | raw body, self-review acceptance, synthesized verdict |
| `agent_progress_facts` | future event normalizer over `scripts/ai/lib/agent_run_events.py` | `unavailable|unknown` only: current event records expose IDs/payloads, not an approved safe progress fact | transcript, reasoning, tool payload, terminal, argv, environment |
| `canonical_attention_facts` | future normalizer over `scripts/ai/lib/attention_queue.py` | `unavailable|unknown` only: current reads include raw detail/action/payload/executor | executing advice, raw details, caller rank |
| `learning_facts` | future aggregate adapter over `config/lessons/agentic-slice-lessons.json` and `config/improvement-sources.json` | closed aggregate count/state leaves only after a separate source contract; otherwise `unknown` | promotion, mutation, activity-volume scoring |
| `projection_meta_facts` | normalized metadata bound into input digest | schema constant, projection revision, generation instant, adapter revisions/digests | resolver clock call or unbound metadata |

The ledger is a test oracle: schema leaf set minus ledger leaf set and ledger leaf set minus schema leaf
set must both be empty. Every row names one envelope above or a versioned pure rule, defines unknown and
conflict behavior, and declares its redaction/bound. Conflicting canonical facts fail closed; no source
wins by convenience. These are availability boundaries, not authority to implement adapters in H2A-P0:
only its five named paths may be created. A future adapter slice must name exact files, source preimages,
sanitized envelope schema, read permission, sampling discipline, and independent review before a currently
unknown leaf becomes known.

Opaque references use a versioned `aqref:` grammar with at least 128 bits of collision-resistant random
or digest-derived material. References are non-authoritative capabilities to drill in only through an
audited resolver. Superseded/revoked references resolve to a bounded unavailable state and replacement
reference when policy allows; they never silently retarget or reveal raw identifiers.

### Collision, sampling, and token evidence contract

This design revision has **no `EDIT` paths**: both pure slices name only `NEW` files, all ten listed
future paths are absent from the worktree, and the five reviewed design subjects are untracked/unstaged.
Therefore there is no truthful source preimage hash or active writer/lease result to claim. Before any
future authorization, the implementer must record a hash for every path that has appeared, `git status`
and active-writer/lease evidence for every future path, plus a fresh collision scan; a non-absent or
leased path stops the slice for amendment.

Each normalized envelope must contain `sample_id`, `sampled_at_bucket`, adapter revision, and source digest.
The pure resolver accepts a set only when all required envelopes share one `sample_id`, their digest/revision
pair is unique per adapter, their sampling buckets are within the policy's closed skew bucket, and no envelope
is superseded/revoked. Otherwise all dependent leaves are `unknown|conflict` and the projection includes a
bounded `incoherent_sample` source-health reason. No wall-clock read occurs in the resolver.

`aqref:v1:<kind>:<128-bit-or-longer-token>` is unique only within `(kind, issuer_revision)`. The authoritative
drill-in resolver must reject duplicate active bindings, a token bound to a different subject digest, unknown
issuer revision, expired token, and a supersession cycle. A superseded token returns `unavailable` plus an
optional replacement token only when the authoritative receipt explicitly binds both subject digests; it must
never retarget by display name, task ID, or latest-record lookup. Golden vectors must cover collision,
revocation, expiry, and supersession-cycle rejection.

### H2A-P0 golden, privacy, and comprehension acceptance

The parent/child, recent-progress, and `through_parent` vectors are permitted only as **synthetic,
schema-valid normalized envelopes** in hermetic resolver fixtures. They test transformation and unknown
propagation, never prove that a current adapter can supply those facts, and do not authorize an adapter.
Each such vector must be paired with a source-unavailable vector; live envelopes use the documented
`unknown|unavailable` leaves until a separately reviewed adapter contract exists.

The fixture and test must prove:

1. identical normalized facts produce byte-identical canonical JSON and SHA-256;
2. every schema leaf has exactly one ledger rule and every output digest binds all normalized inputs,
   schema version, projection revision, serializer revision, and policy revision;
3. missing, malformed, stale, conflicting, or unreadable facts remain visible unknown/degraded;
4. terminal `done` without an independent receipt remains `needs_review` or explicit drift;
5. recent canonical step progress prevents wall-time-only stale classification;
6. parent-controlled child work renders `through_parent` with a bounded parent reference;
7. advice preserves reason, evidence, required authority, and availability without becoming executable;
8. prompt/output/secret/path/identity/reasoning/terminal/argv/environment/provider/session injection is
   rejected or reduced to bounded categories at every envelope and declared consumer boundary;
9. web/TUI/HERDR expectations preserve operator schema version, revision, digest, priority order, and
   work/evidence reference semantics without consumer-specific reinterpretation;
10. keyboard-only, narrow-terminal, reduced-motion, screen-reader, and global-ribbon summaries preserve
    mission, highest attention, freshness, authority, unknown, drift, and overflow truth.

Privacy cases include oversized values, malformed Unicode/control characters, delimiter/JSON-key
injection, traversal strings, shell fragments, credential-shaped values, and high-cardinality identifiers.
Tests assert both absence of injected bytes and presence of a bounded rejection/degraded reason.

## H2A-P0B — `aq.herdr.presentation.v1` only

### Boundary

H2A-P0B answers only: **what presentation state has an authorized HERDR observation source actually
observed?** It cannot declare canonical work state, task authority, acceptance, review, lease, or allowed
actions. Its resolver is pure and consumes only a closed normalized observation value envelope.

No observation adapter is authorized by this packet. Until one is separately inventoried, reviewed, and
authorized, `source_health.authorization` is `unauthorized|unknown` and each dependent field uses contract
#5's explicit `unknown|unavailable` state with its permitted null token/value. It is never inferred from
static H1 package/config facts, desired layout, declared service configuration, package presence, or a
successful schema test. Static facts may populate only contract-#5's explicit `expected`, `expected_count`,
`expected_state`, `expected_revision`, and `expected_digest` leaves; they must never
populate an observed field, source health, freshness, or presentation health.

### Exact five-file ceiling

| action | exact future path | bounded responsibility |
|---|---|---|
| NEW | `config/schemas/herdr-presentation.schema.json` | Closed JSON Schema for exactly the contract-#5 `aq.herdr.presentation.v1` normative profile; observation revision, source health/digests, bounded observation states, and canonical SHA-256 digest. |
| NEW | `config/herdr-presentation-source-to-field-ledger.v1.json` | Machine-checkable row for every contract-#5 presentation leaf, separating static expected provenance from authorized observation facts and freezing unavailable/unknown propagation. |
| NEW | `scripts/ai/lib/herdr_presentation_projection.py` | Pure deterministic resolver over normalized observation values; no HERDR import, binary, config, socket, process, pane, session, layout reconciliation, package, filesystem, clock, environment, network, or writer access. |
| NEW | `scripts/testing/fixtures/herdr-presentation-golden.json` | Closed replay corpus with no-adapter defaults, authorized/unauthorized envelopes, source failures, stale/conflict cases, exact bytes/digests, parity cases, and privacy/redaction vectors. |
| NEW | `scripts/testing/test-herdr-presentation-projection.py` | Hermetic schema/ledger completeness, determinism, privacy, static-versus-observed truth, authorization/null, bounding, replay, digest, and parity tests; no live HERDR access. |

Any sixth file, observation adapter, socket/CLI call, HERDR import, consumer edit, environment variable,
port, URL, service, or runtime check is an undeclared dependency and stops H2A-P0B for amendment and
independent re-review.

### Frozen presentation shape and truth rules

Canonical serialization order is exactly (this is the same normative root profile as contract #5 and the
contract-#3 embedded `herdr_presentation.payload`):

```text
schema_version
observation_revision
generated_at
freshness
source_health
source_digests
configured
runtime
socket
session
version
protocol
panes
layout
counts
reconciliation
coverage
policy
```

- `source_health` and `source_digests` contain per-observer authorization, validity, revision, and digest
  state; an unauthorized observer makes dependent facts `unknown|unavailable`, never healthy.
- `configured`, `runtime`, `socket`, `session`, `version`, `protocol`, `panes`, `layout`, `counts`, and
  `reconciliation` use exactly contract #5's nesting and closed enums. This version has no root
  `projection_revision`, singular `source_digest`, `observation_authorization`, `expected`, or `observed`
  wrapper.
- `coverage` reports known, unknown, unavailable, and overflow counts separately. No absent fact is zero or
  healthy. Every contract-#5 count object, including `session.expected_count`, `session.observed_count`, and
  each `counts.*` member, uses `count_state: known|unknown|unavailable` only; `policy` freezes schema,
  redaction, bounds, serializer, digest, and state rules only.

The source-to-field ledger has distinct authorities for expected provenance and observed facts. It
rejects any mapping from H1 package/config/desired-layout input to `observed.*`. Schema leaf-set parity,
closed enums/objects, exact null/state pairing, bounded references, collision behavior, and
revocation/supersession behavior are test oracles.

### H2A-P0B golden and privacy acceptance

The fixture and test must prove:

1. identical normalized envelopes produce byte-identical canonical JSON and SHA-256;
2. no authorized adapter yields a known observation when its source-health authorization is unavailable;
3. static package/config/desired-layout facts cannot populate or improve observation fields, freshness, source
   health, coverage, or presentation health;
4. authorized but missing, malformed, stale, conflicting, or unreadable observation facts remain explicit;
5. every leaf has exactly one ledger rule; both set differences between schema and ledger leaves are empty;
6. output digest binds the complete input, schema version, observation revision, serializer, and policy;
7. prompt/output/secret/path/identity/reasoning/terminal/argv/environment/provider/session injection and
   oversized/control/traversal/shell/credential-shaped values cannot cross the resolver or consumers;
8. HERDR/TUI/web fixtures preserve the presentation schema version, revision, digest, freshness, null/state
   semantics, and reference grammar without treating presentation as canonical work authority.

## Direction, comparison, and optional transport envelope

The only permitted direction is:

```text
canonical AQ facts -> aq.operator-context.v1 -> desired human/agent work presentation
authorized HERDR observation -> aq.herdr.presentation.v1 -> presentation health
operator-context + herdr-presentation -> contract-#5 `compare_operator_context_to_presentation_v1` -> `aq.herdr.comparison.v1`
```

HERDR observation never changes canonical AQ state. Contract #5 is the sole owner of the pure named
comparator and of `aq.herdr.comparison.v1`; neither projection computes a join. Until a separately
authorized comparison slice exists, `aq.operator-context.v1` comparison leaves remain `unknown` and
`aq.herdr.presentation.v1` contains only observation facts. The comparator takes exact projection bytes
and requires both schema versions/revisions/digests; it emits only `{comparison_schema_version:
"aq.herdr.comparison.v1", comparison_revision:token, operator_context_digest:sha256,
presentation_digest:sha256, join_state:"match|mismatch|unknown", typed_mismatches:[{operator_path:
bounded_path,presentation_path:bounded_path,reason:"missing|stale|conflict|incompatible|unauthorized|unavailable",
evidence_refs:[aqref]}], digest:sha256}`. Each path/reference is bounded and the array maximum is 64. It
never selects a winner or writes back.

A later separately authorized API/TUI response may carry both complete projections in a closed envelope:

```text
transport_schema_version
transport_revision
operator_context { complete schema_version, projection_revision, digest, payload }
herdr_presentation { complete schema_version, observation_revision, digest, payload }
comparison { comparison_schema_version, comparison_revision, operator_context_digest, presentation_digest, join_state, typed_mismatches, digest }
```

The envelope is a transport view, not a third authority, merged projection, compatibility schema, or
permission to omit either complete identity/revision/digest. Version mismatch is visible degraded/unknown;
consumers do not synthesize defaults or a single combined projection digest.

## Service Coverage parity and activation separation

H2A-P0 and H2A-P0B contain only the ten pure-projection files above. They do not edit Phase-0, HERDR,
`aq-tui-dashboard`, the web command center, dashboard assets, or global-ribbon consumers.

Before any later integration can be complete, a separately inventoried and authorized consumer slice must
ship together:

- a Phase-0 integration-path `CheckResult` that validates both complete schema identities, revisions,
  digests, freshness values, and comparison join health rather than file existence or `/health`;
- `aq-tui-dashboard` operator-context monitoring with adjacent subordinate HERDR presentation health;
- web command-center operator context as the human work experience plus a subordinate presentation-health
  card; and
- the global ribbon as an independent harmless operator-context monitor, not coupled to HERDR tab/runtime
  availability.

All consumers must show both projection identities/revisions/digests/freshness and typed join health. A
single `aq.herdr.projection.v1`, shared revision/digest, static stub, blank `--`, or inferred healthy state
fails parity. The future consumer file ceiling requires a fresh collision scan and zero-active-writer check;
no consumer path is authorized or inventoried by this packet.

Runtime observation, adapter wiring, sockets, HERDR process/session/pane inspection, layout reconciliation,
consumer integration, deploy, rebuild, and activation are later authorities and cannot be bundled with
either pure-projection implementation or inferred from green hermetic tests.

## Dynamic role assignment and review separation

No agent identity is predetermined. At authorization time the canonical router selects the cheapest
healthy eligible lane by capability and current constraints:

- implementation owner: `eligible independent implementer`;
- acceptance owner: `independent flagship reviewer` who did not author the candidate;
- integration/freeze owner: authorized orchestrator after an exact hash-bound PASS.

Self-review cannot satisfy acceptance. Unavailable, timed-out, abstaining, or non-reviewing agents receive
no reviewer credit. Each slice has its own authorization, exact subject/file ceiling, validation evidence,
independent verdict, digest, and stop boundary.

## Owner-ratification record and gates

Durable scoped record for this design packet:

| field | recorded value |
|---|---|
| ratifying authority | Owner directive relayed 2026-08-08 and recorded in owner-ratified contract-zero |
| authorized scope | Safe repo-local implementation of only the ten exact `NEW` pure-projection paths in the two five-file ceilings; fresh collision/active-writer/lease evidence, hermetic validation, and fresh independent review are mandatory |
| explicitly unauthorized | Any eleventh file; adapter, consumer, comparison, control, API/UI, HERDR import/runtime/socket/pane/process/session/attach/layout action; deploy/rebuild/activation; H1 alteration; H3 execution. Contract #4's human-control allowlist remains empty. |
| validity | Scoped implementation authority survives only while contract-zero, accepted-H1 evidence, file ceilings, and collision/lease evidence remain exact; it does not survive subject drift or scope expansion |
| expiry / next gate | Stop on subject drift, contract-zero drift, file-ceiling expansion, collision/active writer/lease, or excluded authority need; next gate is a fresh independent hash-bound PASS for each completed pure slice, then authorized freeze/staging/commit only for that exact reviewed subject |

This record is evidence of the narrow ten-path implementation authority only. Conversational wording, a
self-review, a green hermetic test, static H1 facts, or this inventory cannot expand it into adapter,
consumer, control, runtime, or activation authority.

## Future validation contracts (not authorized commands)

Under this exact scoped authority, each pure slice must pass its own hermetic validation and fresh independent
hash-bound review before freeze, staging, or commit. Only after both slices close independently may the separately inventoried
Service Coverage integration validate both projections and the comparison view. The minimum future gates are:

```text
H2A-P0: schema + ledger bidirectional completeness + golden/privacy suite + canonical byte/digest replay
H2A-P0B: schema + ledger bidirectional completeness + no-adapter/static-truth + golden/privacy byte/digest replay
integration: Phase-0 --machine + HERDR/TUI/web/global-ribbon parity + typed join health
repository: tier0 pre-commit gate under the eventual authorized integration owner
```

No runtime command is authorized as implementation evidence. This amendment itself stages or commits no file;
a later implementer may stage/commit only an exact reviewed pure-slice subject after its required PASS.

## Explicit exclusions and stop conditions

Excluded beyond the ten named pure-slice paths: adapter, QA-phase registration, TUI, web, dashboard, HERDR,
transport, comparison, configuration outside those paths, runtime, socket, process, pane, session, attach,
layout, package, service, deploy, rebuild, activation, H1, H3, and all control implementation. The
human-control allowlist remains empty.

Stop and amend under fresh independent review on: missing/changed accepted H1 evidence; contract-zero drift;
any sixth file in either pure slice; shared file or active-writer collision; adapter/consumer/env/port/URL
need; inability to close schema/ledger sets; consumer semantic fork; merged authority/digest; observation
changing canonical state; static facts presented as runtime truth; unknown collapsing to healthy zero; action
payload in either projection; self-review; or implementation/runtime activity without separate authorization.

SCOPED_IMPLEMENTATION_AUTHORITY: exactly ten named pure `NEW` paths only; collision/lease checks and fresh
independent PASS are mandatory; runtime authority remains false.
