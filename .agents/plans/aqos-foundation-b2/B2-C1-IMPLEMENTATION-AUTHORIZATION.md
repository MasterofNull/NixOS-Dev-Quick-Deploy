# Foundation B2-C1 pure-contract implementation authorization

**Authorization ID:** `auth-aqos-foundation-b2-c1-20260718`  
**Idempotency key:** `aqos-foundation-b2:b2-c1:pure-contracts:v1:20260718`  
**Status:** **PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED**  
**Owner basis:** Q1/Q2 ratification at commit
`cf3e81d7a09205ad808c1b5db8a113ba297eff0d` authorizes preparation and independent review of this
record only.  
**Activation rule:** this record remains `PREPARED_ONLY` after an independent authorization `PASS`.
Implementation requires a later, explicit owner activation naming this authorization's exact hash and
an expiry no longer than 24 hours. Silence, broad preauthorization, design acceptance, or a review
`PASS` does not activate it.  
**Single use:** a later activation is consumed by the first complete exact eight-file candidate report.
An interrupted attempt without a complete candidate does not consume it, but resumption must use the
same implementer and reverify every predecessor.

## 1. Bound authority and design chain

The following current projections and historical design subjects are immutable inputs to this
authorization. Any mismatch is a hard stop and requires a new authorization subject and independent
review.

| Subject | SHA-256 |
|---|---|
| `.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md` | `67796d15a03f3712eef21f4f77407bce6067c7faba672892a7a91ceeb4f6ea12` |
| `.agents/plans/UNIFIED-PROGRAM-PLAN.md` | `285bda20b4bb3b43cafbc3a46b90c905b203996448f2f5cfda62a0d950bea62e` |
| `.agents/plans/unified-program/OWNER-DECISION-SHEET.md` | `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1` |
| `.agents/plans/unified-program/Q1-Q2-OWNER-RATIFICATION-20260718.md` | `f3894924e0253087a0db044792d684a0c4874dea3dbd4e64de271495af35d759` |
| `.agents/plans/unified-program/Q1-Q2-OWNER-RATIFICATION-REVIEW-20260718.md` | `48f325cc95c9899663c7b201123ed28ee65b5a4d312b3f1c57ba5e056e0664ce` |
| `.agents/plans/aqos-foundation-b2/WORKFLOW-SHADOW-ADR.md` | `1bf65352993d5496ca5f3f6d8d1aea9078ac9f21427464cda6a6360523ee02bb` |
| `.agents/plans/aqos-foundation-b2/WORKFLOW-SHADOW-PRD.md` | `b40b96420e03d84e75b848b5535cd6b16e46818e3a74d7dbb526369e8b71d7d5` |
| `.agents/plans/aqos-foundation-b2/B2-D0-DESIGN-PACKET.md` | `d8a0f368ea45bae47180aa73ba654af846941da8e98a682155729f94cd839d81` |
| `.agents/plans/aqos-foundation-b2/B2-D0-DESIGN-REVIEW.md` | `6b97c09bfa1a79a928999533f779a3a4dfa59733b379ae318a47696bc781ec7e` |

This grant implements only B2-C1's pure contract oracle. It does not move authority: legacy
`workflow-sessions.json` remains authoritative and Postgres remains an unimplemented shadow
hypothesis.

## 2. Exact eight-file implementation ceiling

One bounded implementer must own all eight files. New files must be absent and modified files must
match their frozen predecessors before the first edit.

| # | Operation | Path | Frozen predecessor |
|---:|---|---|---|
| 1 | NEW | `config/schemas/workflow-shadow-contracts.schema.json` | must be absent |
| 2 | NEW | `config/workflow-shadow-phase-tokens.json` | must be absent |
| 3 | NEW | `scripts/ai/lib/workflow_shadow_contract.py` | must be absent |
| 4 | NEW | `scripts/testing/fixtures/workflow-shadow-contract-v1-golden.json` | must be absent |
| 5 | NEW | `scripts/testing/test-workflow-shadow-contract.py` | must be absent |
| 6 | MODIFY | `scripts/testing/harness_qa/phases/phase0.py` | `ccee6268b0980f1d2fed1db6919107e1b4809447d9195461994ffb420f1f9a96` |
| 7 | MODIFY | `scripts/ai/_aq-qa-bash` | `a49a43fdf78f0218e63e8bc574895f285d5e19506f4ae9d687a86d5a4b71f7ca` |
| 8 | MODIFY | `config/validation-check-registry.json` | `9c6317a87f6187fdbf193e25d3a7045ed59b416f54c9d90a2493de1920c956be` |

Read-only source material: `config/workflow-blueprints.json` at
`12ba465a5ede653579ac52752558ed9068fe0bbfd407dbc44cb2b80b70c72374`. The implementer may read but
must not modify it. A ninth changed implementation file is a hard stop.

## 3. Exact grant

### 3.1 Five independently versioned closed contracts

File 1 must provide Draft 2020-12 schemas for exactly five independently versioned variants:

1. `event` — `aq.workflow-shadow-event.v1`;
2. `snapshot` — `aq.workflow-shadow-snapshot.v1`;
3. `immutable_outbox` — `aq.workflow-shadow-outbox.v1`;
4. `delivery_control` — `aq.workflow-shadow-delivery-control.v1`; and
5. `health` — `aq.workflow-shadow-health.v1`.

Every object boundary must be closed (`additionalProperties: false` or the Draft-2020-12 equivalent),
and each variant must reject an unknown or cross-variant version. Fields and enums must realize PRD
section 6 without extension bags. Numeric values are bounded JSON integers only: booleans do not count
as integers and floats, `NaN`, infinities, numeric strings, and negative revisions are rejected.

Canonical serialization must be one documented pure rule: UTF-8 JSON, Unicode NFC normalization,
lexicographically sorted object keys, no insignificant whitespace, no floats, and deterministic bytes
and digests across process runs and input key order. An accepted canonical event must be at most 2 KiB.

### 3.2 Opaque phase-token registry

File 2 must be a closed, versioned registry derived from the read-only blueprint predecessor. It must
cover exactly the 14 fixed unique blueprint phase identifiers present in that predecessor and map each
to a stable, domain-separated opaque token. The mapper may accept only a registry key from that fixed
allowlist and emit only the opaque token plus a bounded phase index. It must reject missing, duplicate,
colliding, unknown, raw/model-derived, or free-form phase values.

Raw blueprint phase identifiers may appear only as reviewed input keys in this registry and test
inputs required to prove the mapping. They must never appear in mapped events, snapshots, outbox
payloads, health objects, canonical bytes, digests, errors, logs, metric labels, or fixture outputs.
The test must prove all 14 tokens are unique and stable and must fail on a phase-ID/token collision.

### 3.3 Pure mapper and complete decision oracle

File 3 must be import-side-effect-free and standard-library-only. It must expose pure functions for:

- empty-object allowlist mapping from a privacy-safe receipt to the five contract variants;
- strict schema/version/enum/integer/string/event-size checks;
- NFC canonical JSON bytes and deterministic domain-separated identities/digests;
- fixed phase identifier to opaque-token lookup;
- receipt-order validation with `revision = expected_revision + 1` and queue ceiling 64; and
- an exact total decision model for every PRD FR-4 branch.

The decision model must distinguish exactly:

1. absent row plus `expected_revision=0` and `revision=1` -> insert;
2. stored revision equals expected revision -> advance;
3. stored revision and event identity/digest equal the receipt -> exact replay, idempotent success with
   no new event or delivery record;
4. stored revision below expected revision -> gap and park;
5. stored revision above expected revision -> stale and park;
6. equal receipt revision with different event identity or digest -> collision and park; and
7. any nonidentical post-terminal receipt -> terminal conflict and park.

No branch may infer, renumber, synthesize, repair, persist, enqueue, deliver, sleep, retry, or perform
I/O. The queue model is a pure capacity/ordering oracle only; it must return `parked` at more than 64
pending receipts and may not create a queue, worker, thread, or task.

### 3.4 Golden and adversarial evidence

File 4 must contain deterministic valid and adversarial vectors for all five variants, canonical byte
and digest stability, all 14 phase-token mappings, every decision branch, event-size boundaries, queue
capacities 0/64/65, terminal uniqueness, and independently versioned rejection.

Privacy canaries must cover, at minimum: objective/query/prompt, phase note, output, tool input/result,
agent message, secret, path, environment, isolation detail, lesson reference, arbitrary extension,
raw phase ID, model-generated phase name/description, and a hash or encoded form of forbidden phase
text. Tests must prove each canary is rejected before serialization and absent from all accepted bytes,
digests, exception text, health output, and fixture expected outputs.

File 5 must consume the golden file rather than duplicate its values inline, verify Draft-2020-12
closure and semantic constraints, and scan the implementation and fixtures for prohibited imports and
side effects. Tests must be deterministic, offline, and process-independent.

### 3.5 Fixture-only Phase-0 contract health

Files 6–8 may register and execute only a fixture-backed B2-C1 contract check. The machine-readable
result must truthfully report:

```json
{
  "authority": "legacy_json_authoritative",
  "coverage": {
    "aq_qa": "ready",
    "web_dashboard": "not_wired"
  }
}
```

The check may load the schema, token registry, module, and fixture and execute the pure focused oracle.
It must not inspect a service, database, socket, port, process, network route, environment activation,
or dashboard. A passing B2-C1 result means only that the fixture contract is ready. Operational health,
service coverage, dashboard parity, and any claim of `observing` remain blocked until B2-O1.

No dashboard, dashboard backend, JavaScript, HTML, API, or service file may be edited in B2-C1.

## 4. Frozen budgets and authority constraints

The complete PRD section 9 envelope is frozen by Q2. B2-C1 must encode the applicable ceilings,
including at most 2 KiB canonical event bytes and at most 64 pending receipts. It may tighten but must
not relax a ceiling. The schema and pure oracle must not claim to implement the future 100 ms/250 ms
deadlines, connection pools, RSS, disk, retention, lag, parity trial, or workflow/event trial limits;
those remain immutable future-slice requirements and must not be represented as measured health.

All contract outputs must state or imply only `legacy_json_authoritative`. Nothing in this slice may
label Postgres, an outbox, a snapshot, a projector, or a health fixture as live or authoritative.

## 5. Mandatory stop conditions

Stop without workaround, additional edits, or partial candidate handoff if any of the following is
needed or observed:

- any database, Postgres, SQL, ORM, database client, connection, pool, DDL, query, migration, grant,
  credential, database read, database write, or storage implementation;
- any filesystem or state write by the module, runtime import, runtime handler/hook, live workflow
  mutation, live receipt allocation, enqueue, delivery, retry, background task, service, daemon, Nix,
  environment variable or env-contract change, port, socket, network, subprocess, thread, worker,
  traffic, activation, deployment, cutover, cleanup, rollback, or store integration;
- any dashboard/backend/JavaScript/HTML/API edit or operational/dashboard-health claim;
- any raw or model-derived phase text in a produced contract, canonical bytes, digest, output, error,
  log, metric label, or health result;
- any extension dictionary/bag, unknown-field acceptance, float, nondeterministic canonical form,
  resource-envelope relaxation, phase-ID/token collision, or fabricated replay/repair branch;
- any mismatch to a bound predecessor, appearance of a new file that this record requires absent,
  edit to the read-only blueprint, shared-file conflict with another agent, or ninth implementation
  file.

A stop requires a narrow finding and a new independently reviewed amendment. The implementer must not
expand scope or infer transitive owner authority.

## 6. Implementer, review, and integration contract

- Exactly one bounded implementer owns all eight files. The implementer may not delegate, split file
  ownership, stage, commit, deploy, activate, or self-review.
- Before editing, the implementer must record its identity and reverify every predecessor hash and
  required absence. It must preserve unrelated dirty work.
- The complete candidate must report exact hashes for all eight files, a concise root-cause/objective
  and reasoning summary, the exact validation commands/results, and explicit exclusions.
- An independent reviewer from a different agent/session must review the exact eight-file candidate,
  identify role/model and subject hashes, challenge every mandatory stop condition and decision branch,
  verify privacy canaries and Phase-0 truthfulness, and issue one final
  `VERDICT: PASS|FAIL|REQUEST_REVISION`.
- A reviewer that edits any candidate byte becomes a material rewriter and is recused from accepting
  the new subject. Any changed candidate hash requires a fresh independent review.
- Only the orchestrator may stage and commit, and only after exact-hash independent `PASS`, focused
  tests, syntax/schema checks, `aq-qa 0 --machine`, and
  `scripts/governance/tier0-validation-gate.sh --pre-commit` pass.
- No commit, review, or test result activates any runtime or later slice. B2-M1, B2-W1, B2-P1, B2-O1,
  and B2-T1 each require their own exact authorization and gates.

## 7. Required candidate acceptance evidence

An independent reviewer may issue `PASS` only if all are true:

1. The subject is exactly the eight-file inventory and every predecessor/absence check passed.
2. All five contract variants are independently versioned, Draft-2020-12, and closed at every object.
3. Canonicalization is NFC, integer-only, float-rejecting, deterministic, and enforces 2 KiB/event.
4. Exactly 14 fixed blueprint phase identifiers map collision-free to opaque stable tokens, and no raw
   or model-derived phase text reaches an output surface.
5. The mapper begins from an empty object, rejects every forbidden canary and extension, and has no I/O
   or import side effect.
6. All seven exact decision branches, receipt monotonicity, exact replay, terminal uniqueness, and
   queue capacities 0/64/65 are covered by golden vectors and pure tests.
7. The Phase-0 result is fixture-only and reports exactly `authority=legacy_json_authoritative`,
   `coverage.aq_qa=ready`, and `coverage.web_dashboard=not_wired`.
8. Prohibited import/static scans and explicit runtime checks show no DB, SQL, client, connection,
   write, network, subprocess, thread, worker, service, Nix, env, port, dashboard, traffic, cutover,
   store, raw-phase, extension, or resource-relaxation path.
9. Focused tests, Python compilation, JSON parsing/schema validation, `aq-qa 0 --machine`, and Tier-0
   all pass without a live database, service, network, or dashboard dependency.
10. The candidate and evidence make no operational-health, writer-convergence, Postgres-authority,
    migration, runtime, deployment, traffic, cutover, cleanup, or rollback claim.

## 8. Activation and consumption record

Current activation state: **NOT ACTIVATED**.

After an independent authorization review passes this exact document, the owner may activate it only
by explicitly naming:

- this authorization's exact SHA-256;
- the one implementer identity;
- an activation timestamp and expiry no more than 24 hours later; and
- confirmation that the exact eight-file ceiling and all stop conditions remain unchanged.

Until that explicit record exists, no file in section 2 may be created or modified under this grant.

`RECORD: PREPARED_ONLY. B2-C1 implementation, DDL, connections, writes, runtime hooks, services,
deployment, traffic, cutover, later slices, cleanup, and rollback remain unauthorized.`
