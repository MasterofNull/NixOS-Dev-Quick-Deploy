---
title: "Local Inference L3-P0: Provenance and Shadow-Observation Kernel"
slice: "L3-P0"
status: "PREPARED_ONLY"
kind: "design-only"
implementation_authorization: "NONE"
activation_authorization: "NONE"
base_head: "17f899bf838973c755ab7a3e6095ec04a2e74220"
predecessors:
  - "L3-G0 adoption-boundary design sha256 ea47d4a274312f85790a556f744ed30a5af559e42f80086da60f96b616db52ee"
  - "L3-G0 independent review sha256 cf96e38c1322ce0d9ecb6a027ee665fb5f63f98d2d89942e864b1545fcb32784"
successors:
  - "L3-A authenticated delegation shadow-admission and Service Coverage seam"
  - "L3-B separately authorized live adoption"
  - "L4 aq-chat producer/client adoption"
---

# L3-P0 — Pure Provenance and Shadow-Observation Kernel

## 1. Decision and boundary

L3-P0 is the smallest prerequisite to L3-A: a pure, deterministic contract
kernel that can represent a resolved local-inference shadow observation only
when every required fact is supplied by a named, immutable producer revision.
It produces values or typed, redacted failures. It performs no I/O, process
launch, provider call, queue/lifecycle mutation, telemetry emission, storage,
network, clock read, environment read, or runtime adoption.

This is deliberately not a `delegate-to-local` integration. It does not accept
caller headers, CLI arguments, task documents, provider output, environment,
PID, heartbeat, or model text as authority. Those can be untrusted source data in
a later adapter, but they cannot become L3-P0 trusted facts.

## 2. Closed contracts

### 2.1 Trusted fact envelope

Each required fact is an object with exactly `fact_type`, `value_digest`,
`producer`, `producer_revision`, `evidence_ref`, and `status`. `status` is
exactly `available` or `unavailable`; unknown fields and types are rejected.
`producer` is a bounded named identity and `producer_revision` is a non-empty
immutable digest/version—not `current`, a mutable config name, or a caller
assertion. `value_digest` and `evidence_ref` are opaque fixed-format references;
raw identity, paths, prompts, commands, credentials, and provider output are
not accepted as kernel output.

The resolver requires these fact types: `authenticated_principal`,
`effective_role_clearance`, `approval_descriptor_lease`, `profile_model_mapping`,
`task_eligibility_effect_ceiling`, `budget_policy`, `repository_path_scope`, and
`clock_ordering`. Each expected fact type has one exact producer identity and
revision supplied in an immutable `ProducerRevisionSet` argument. Duplicate,
missing, unavailable, unknown, contradictory, mismatched-revision, or
noncanonical values fail closed; the resolver never chooses a best candidate.

All authority-bearing boundaries are Draft 2020-12 closed JSON contracts, with
`additionalProperties: false` recursively at every object boundary. The future
candidate must supply these seven contracts: `trusted-fact-envelope`,
`producer-revision-set`, `shadow-request-projection`, `resolved-shadow-plan`,
`shadow-observation-metadata`, `shadow-observation`, and
`trusted-fact-unavailable`. Each schema fixes string
lengths and digest syntax, finite integer bounds, required fields, enums, and
maximum collection sizes; it rejects duplicate logical keys, aliases, nulls
outside explicitly optional fields, non-finite numbers, unbounded nested
objects, and unknown fields. `value` is never carried: each fact conveys only a
SHA-256 `value_digest` and an opaque, redacted `evidence_ref`.

The canonical representation is UTF-8 JSON emitted from recursively sorted
object keys, no insignificant whitespace, integers only where numbers are
allowed, NFC-normalized strings, and a fixed field order defined by each schema.
The parser rejects duplicate source keys before materialization. A digest is
`sha256(canonical_utf8(document))`; implementations must not substitute Python
object representation, locale, timestamps, random values, environment, or
mapping iteration order. `resolve_shadow_plan` returns exactly one closed tagged
sum: `{kind:"resolved", plan:<resolved-shadow-plan>}` or
`{kind:"unavailable", result:<trusted-fact-unavailable>}`. It never returns a
partial plan, and only `kind:"resolved"` may be passed to the observation
builder.

`shadow-request-projection` is limited to digested/opaque request and trace
references plus the declared non-authority comparison inputs. It carries no
role, tool, path, grant, route, provider, raw task, header, CLI, environment,
or caller-selected producer claim. `resolved-shadow-plan` carries the canonical
request-projection digest, ordered provenance-vector digest, compatibility
adapter identifier, decision, and immutable divergence findings; it contains no
execution instruction or authority.

### 2.2 Shadow observation and unavailable result

The closed `aq.local-inference-shadow-observation/1.0` schema permits only:
`schema_id`, `observation_id`, `request_ref`, `trace_ref`, `shadow_sequence`,
`observed_at`, `producer`, `producer_revision`, `resolved_plan_digest`,
`legacy_observation_digest`, `compatibility_adapter`, `decision`,
`typed_error`, `divergence_findings`, `provenance_refs`, `shadow`,
`non_authoritative`, and `no_live_cutover`.

`shadow`, `non_authoritative`, and `no_live_cutover` are constant true. It
explicitly rejects run IDs, lifecycle sequence, terminal/result, cancellation,
retry, provider receipt, writer revision, raw task content, and unbounded extra
properties. `shadow_sequence` is local observation order only.

The companion closed `aq.local-inference-trusted-fact-unavailable/1.0` result
contains a stable `typed_error="trusted_fact_unavailable"`, bounded failing fact
type/category, opaque evidence reference, and the three constant non-authority
flags. It contains no raw diagnostic. Resolver failures return this contract and
must not produce an admissible shadow observation.

`shadow-observation-metadata` is a separate closed input contract with exactly
`observation_id`, `shadow_sequence`, `observed_at`, and
`legacy_observation_digest`. All are bounded opaque/canonical fields:
`observation_id` and `legacy_observation_digest` have fixed digest/reference
syntax, `shadow_sequence` is a finite non-negative integer, and `observed_at`
is canonical RFC 3339 UTC text supplied by the already-validated
`clock_ordering` fact, not read by the kernel. The builder derives request and
trace references, producer identity/revision, plan digest, decision, adapter,
divergences, and provenance only from `resolved`; it rejects those keys and any
authority field in metadata. Metadata is a validated redacted observation
envelope and deliberately does **not** participate in `resolved_plan_digest`:
changing observation identity/order/time must not change an admitted plan. It
does participate in canonical serialization and schema validation of the final
observation, and no output is emitted without the exact metadata contract.

`provenance_refs` is a required, sorted vector with exactly one member for each
expected fact type. Every member has only `fact_type`, `producer`,
`producer_revision`, `value_digest`, and `evidence_ref`; it is sorted by the
schema's fixed `fact_type` order. The resolver rejects a missing, extra,
duplicate, unsorted, mismatched, or unavailable member. It computes
`provenance_vector_digest = sha256(canonical_utf8(provenance_refs))` and binds
that digest, the canonical request-projection digest, expected
ProducerRevisionSet digest, decision, compatibility-adapter identifier, and
ordered divergence findings into `resolved_plan_digest`. The observation schema
requires that its visible redacted vector and `resolved_plan_digest` verify this
same construction. The unavailable schema carries the single bounded failing
fact type/category and opaque evidence reference only; it cannot carry or imply
a partial provenance vector.

## 3. Pure API and deterministic rules

The future `local_inference_provenance.py` exports only pure functions:

- `validate_producer_revision_set(expected)`;
- `resolve_shadow_plan(request_projection, facts, expected)`;
- `build_shadow_observation(resolved, observation_metadata)`.

Inputs are copied, canonicalized deterministically, and never mutated. A valid
resolution yields only a plan digest and redacted provenance references; it is not
a route selection, grant, provider request, or permission to execute. The
observation builder accepts only a previously valid resolved result and the
closed metadata contract, and rejects caller-selected authority fields. The
unavailable-result constructor is private to the module and is invoked only by
the resolver from its internally validated failure enum, expected fact type, and
already-present opaque evidence reference; it is not public and accepts no
caller `failure` object. No function generates identifiers using time,
randomness, or process state; callers supply already-redacted opaque references.

## 4. Proposed implementation inventory

At the base HEAD the following future implementation paths are absent and are
reserved for a separately reviewed L3-P0 candidate:

| Operation | Path | Purpose |
|---|---|---|
| NEW | `scripts/ai/lib/local_inference_provenance.py` | Pure producer-revision validation, resolution, and observation/error construction. |
| NEW | `config/schemas/local-inference-trusted-fact-envelope-v1.schema.json` | Closed trusted fact with digest-only value and opaque evidence reference. |
| NEW | `config/schemas/local-inference-producer-revision-set-v1.schema.json` | Closed expected fact-type-to-producer/revision authority map. |
| NEW | `config/schemas/local-inference-shadow-request-projection-v1.schema.json` | Closed non-authoritative request projection. |
| NEW | `config/schemas/local-inference-resolved-shadow-plan-v1.schema.json` | Closed tagged-success plan and canonical digest inputs. |
| NEW | `config/schemas/local-inference-shadow-observation-metadata-v1.schema.json` | Closed redacted observation identity/order/time envelope. |
| NEW | `config/schemas/local-inference-shadow-observation-v1.schema.json` | Closed shadow-observation schema with ordered provenance vector. |
| NEW | `config/schemas/local-inference-trusted-fact-unavailable-v1.schema.json` | Closed typed-unavailable result schema. |
| NEW | `scripts/testing/fixtures/local-inference-l3-p0-golden.json` | Canonical valid, parity, provenance, and negative vectors. |
| NEW | `scripts/testing/test-local-inference-l3-p0.py` | Offline schema and pure-function oracle. |

The final candidate freeze must recheck those absences and bind their candidate
hashes. No central schema registry is used by the existing local-inference
schemas; the test imports these six paths directly, so no registry/configuration
edit is authorized. It must also bind the following no-edit anchors:

| No-edit path | Current SHA-256 |
|---|---|
| `scripts/ai/lib/local_inference_transport.py` | `e42fb5480385f791a8cd43bb94802499eddb5ef335ef0228d749a828d7130405` |
| `scripts/testing/test-local-inference-l2b.py` | `79425baf3c58cf764c75a32fc597755618ac69377032d52d99d41295c69b4e82` |
| `dashboard/backend/api/routes/aistack.py` | `5e736402eb51bf7522902fd4803cd9dac099ce197ec15df4bfec6ec5a1e6d2fd` |
| `assets/dashboard.js` | `ea88c43e2509fd9d5a1c1dbf408c87a48538cd96a33fee2c42ad79f1c347c0be` |
| `scripts/testing/harness_qa/phases/phase0.py` | `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1` |

## 5. Golden vectors and offline validation

The fixture must prove:

1. an all-present producer/revision set yields a deterministic plan digest and
   closed observation;
2. reordered JSON/facts produces identical canonical output;
3. every required fact independently yields `trusted_fact_unavailable` when
   missing, unavailable, unknown, duplicated, contradictory, or revision-mismatched;
4. caller-supplied `current`, environment, raw header/CLI, task, provider, PID,
   or model-text producer claims are rejected;
5. unknown top-level/nested schema fields and prohibited lifecycle/provider fields
   are rejected;
6. all eight known B1 divergent pair statuses and all 24 field obligations remain
   represented as immutable divergence findings, not silently collapsed to pass;
7. raw secrets, prompts, commands, absolute paths, and high-cardinality identity
   values cannot enter any result; and
8. inputs remain byte-equivalent after every pure operation.
9. every authority-bearing input, including observation metadata, and both
   tagged result alternatives validate
   against their named closed schema; every unknown/duplicate/alias field,
   noncanonical Unicode form, non-finite/overflow number, overlong value, and
   unsorted provenance vector fails before any digest is emitted;
10. a valid result has exactly one provenance entry for every expected fact,
    and changing any fact producer, revision, value digest, evidence reference,
    request-projection input, decision, adapter, or divergence finding changes
    the required canonical digest or fails validation; and
11. hermetic purity is enforced by importing the module under forbidden
    `open`, `socket`, subprocess, environment, clock, randomness, UUID, and
    network hooks, then exercising every public function. Any invocation of a
    forbidden capability fails the test. The module dependency list is also
    asserted to exclude transport, provider, filesystem, process, registry,
    persistence, and telemetry modules.
12. malformed observation metadata (including caller-provided producer, plan,
    provenance, request, trace, or authority fields) is rejected; valid metadata
    changes only the final observation envelope, never `resolved_plan_digest`;
    and the unavailable constructor is absent from the public module surface.

The sole validation command is:

```bash
python3 scripts/testing/test-local-inference-l3-p0.py
```

It is offline and hermetic. A later candidate may additionally run syntax and
schema parsing checks, but must not run `aq-qa`, a dashboard, service, provider,
socket, DNS, curl, deployment, or a live `delegate-to-local` command.

## 6. Explicit exclusions and later Service Coverage

L3-P0 must not touch `scripts/ai/delegate-to-local`, `dispatch.py`,
`TaskRegistry`, `aq-chat`, L2B transport/fixtures/schema, aistack API,
dashboard.js, Phase 0, Nix, services, queues, stores, providers, or telemetry
emitters. It does not persist an observation and has no dashboard/AQ-QA Service
Coverage claim.

L3-A is the separate seam that must name concrete authenticated producers,
call this kernel from a delegation-only adapter, persist bounded observations,
and ship the service implementation, integration-level AQ-QA check, and
live-backed dashboard projection together. L4 alone owns aq-chat producer/client
adoption. L3-B alone may propose live adoption after its separate prerequisites.

## 7. Remaining blockers and authority

Before L3-A can freeze, the project must identify and hash-bind: the authenticated
ingress identity mapper; role, approval/lease, profile, eligibility, budget, path,
and clock producer revisions; a non-authoritative delegation adapter seam; a
durable redacted observation owner; and a collision-free Service Coverage path.
Those are not supplied by L3-P0 and may not be inferred from this design.

L3-P0 itself requires an independent review, hash-bound implementation
authorization, and a fresh owner activation before any code is created. This
packet grants none.

**RECORD: PREPARED_ONLY. No implementation, activation, runtime adoption,
provider traffic, staging, commit, deployment, restart, or network action is
authorized.**
