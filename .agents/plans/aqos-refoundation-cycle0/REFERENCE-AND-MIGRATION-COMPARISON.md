# AQ-OS Reference, Build/Adopt, Migration and Consolidation Comparison

**Status:** source-backed planning comparison; repository counts and exact retirement candidates remain
C0.3 discovery outputs. External systems are patterns, not feature-count targets.

## Reference patterns

| Reference | Pattern to adopt | Pattern not implied | AQ-OS disposition |
|---|---|---|---|
| [CloudEvents specification](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md) | Versioned event context, required ID/source/type/spec version, source+ID duplicate identity, transport-independent envelope | CloudEvents does not provide durable storage, ordering, authentication or idempotent effects | Adopt compatible envelope fields in Cycle 1; add aggregate revision, producer assurance, causation, policy and payload hash |
| [OpenTelemetry trace semantic conventions](https://opentelemetry.io/docs/specs/semconv/general/trace/) | Stable names/meaning and one trace context across components | Telemetry is not workflow/evidence authority and high-cardinality IDs should not become metric labels | Adopt trace/span conventions and resource identity; keep authoritative outcomes in durable records |
| [SPIFFE Workload API](https://spiffe.io/docs/latest/spiffe-specs/spiffe_workload_api/) | Short-lived workload identity, caller attestation and continuously refreshed credentials | SPIRE deployment is not automatically justified for one host; identity does not itself authorize actions | Use `ORCHESTRATOR_ATTESTED` honestly in C0; compare Unix-credential identity vs SPIRE in Cycle 2 |
| [PostgreSQL transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html) and [WAL](https://www.postgresql.org/docs/current/wal-intro.html) | Atomic related state/outbox commit, crash durability and recovery foundation | Database durability does not create exactly-once delivery or correct application invariants | Leading Cycle 1 authority because Postgres already runs; require idempotent consumer and restore drill |
| RFC 8785 JSON Canonicalization Scheme | Interoperable canonical JSON hashes | A hash is not authorship or authorization; current Nix package availability was not verified | Use restricted dependency-free `aq-canonical-json-v1` for C0; reconsider RFC 8785 in Cycle 1 |
| Durable workflow engines | Persist transitions, retries, timers, idempotency and replay as explicit workflow semantics | Adopting Temporal/another service before proving need would increase operational surface | First implement a modular Postgres-backed workflow kernel; benchmark adopt-vs-build only if semantics/scale exceed it |
| Object-capability security | Grant narrow, explicit, revocable authority rather than ambient tool access | A lease checked only by the orchestrator is not enforcement | Model capability/lease now; enforce at orchestration and tool execution in Cycle 2 |
| Local inference schedulers | Admission, priority, preemption/cancellation and memory/thermal budgets | A small resident model or multi-model pool is not beneficial without measured fit | Activate/tune F2.5 from measured contention in Cycle 3; protect interactive work first |

## Build versus adopt decisions

| Capability | Build/adopt hypothesis | Nix/security/resource/migration considerations | Exit strategy |
|---|---|---|---|
| Durable state/outbox | Adopt existing Postgres; build AQ-specific schema, invariants and workers | Existing service reduces new RAM/service cost; require least-privilege role, migrations, backup, WAL/disk baseline | Export canonical events/artifacts; keep schema/API versioned |
| Ephemeral delivery | Keep Redis only if latency measurements justify it | Existing Redis has cost and failure modes; loss must be recoverable from outbox | Workers may poll Postgres; Redis can be disabled/rebuilt |
| Semantic memory | Keep Qdrant/AIDB as projection | Existing investment; require privacy domains, lineage, freshness and deterministic reindex | Rebuild from durable sources or disable optional profile |
| Artifact CAS | Build minimal local filesystem CAS before adopting a daemon/object store | Zero service cost; enforce permissions, traversal/symlink defense, privacy domains, retention and fsync | URI/hash contract permits later S3-compatible adapter |
| Canonical JSON | Build restricted C0 encoder with cross-language vectors | No verified `python313Packages.jcs`; avoids dependency and forbids unstable floats | Version algorithm; migrate through new subject revisions only |
| Event envelope | Adopt CloudEvents-compatible core fields; build AQ extensions | SDK is optional; schema generation and producer validation matter more than library | Preserve standard fields when transport/store changes |
| Tracing | Adopt OpenTelemetry SDK/conventions where existing packaging supports it | Bound sampling/cardinality/export; trace is evidence link, not authority | OTLP export can be disabled without losing workflow state |
| Workload identity | Build minimal single-host OS-principal attestation first; assess SPIFFE/SPIRE | SPIRE adds services, keys and policy operations; Unix sockets/credentials may fit one host | Identity interface allows stronger provider later |
| Workflow engine | Build bounded modular kernel on state/outbox before adopting external engine | Avoid another control plane; require crash/retry/timer tests and dependency boundaries | Event/API contracts allow later Temporal-style adapter |
| Scheduler | Keep/refactor existing F2.5 and switchboard admission | Zero new service; benchmark memory, thermal, cancellation and starvation | Disable policy module and retain serial safe mode |

## Strangler migration program

| Cycle | Add/strengthen | Dual-path evidence | Retirement effect | Rollback |
|---|---|---|---|---|
| 0 | Decision truth, evidence algebra, authority registry | Compare old machine state with invariant/audit result | Status/prose/mutable-latest cease authorizing | Compatible readers preserve old bytes as untrusted projections |
| 1 | Modular state/event/outbox authority | Shadow-write/compare selected objects; replay and restore | JSONL/Markdown/Redis lifecycle writers become projections | Stop new writer; replay last verified legacy snapshot; preserve new log |
| 2 | Principal identity, leases and effect enforcement | Observe-only policy then deny/canary by risk class | Ambient/direct tool authority and shared signer paths retire | Revoke new leases; return to explicitly constrained safe mode, not ambient bypass |
| 3 | Scheduler and learning industrialization | Shadow routes/promotions and compare outcomes/resources | Dormant scheduler paths, uncertified promotion and unbounded producers retire | Serial local safe mode and last admitted model/scorer |
| 4 | One API/CLI/console | Shim use/divergence telemetry; contract parity | Direct CLIs/routes/dashboard synthesis retire by threshold | Re-enable read-only compatibility adapter within expiry |
| 5 | Releases, restore and second hardware target | Clean install/upgrade/rollback/benchmark evidence | Unsupported portability and archaeological docs/tests retire | Versioned Nix rollback and data migration reversal |

No dual path may exceed two clean release cycles or 90 days without an owned, expiring exception.

## Consolidation and deletion candidate classes

| Class | Current evidence | Target | Retirement proof |
|---|---|---|---|
| `aq-*` wrapper sprawl | 131+ entrypoints reported in current PRD | `aq <noun> <verb>` plus measured temporary shims | Zero use/divergence for clean cycles; docs/completions/API parity |
| Coordinator extensions/god-service | 49 extensions reported | Admitted modules with dependency rules; research opt-in | Forbidden imports pass; canonical routes no longer import retired extension |
| File lifecycle authorities | PULSE/RESUME/PENDING, registries, inboxes, JSONL, result files | Human/debug projections from durable records | No direct writes; rebuild and recovery tests pass |
| Duplicate payload/fallback builders | At least three paths reported | Switchboard-only execution contract | 100% gateway IDs; direct calls fail explicit QA |
| Dashboard-local calculations | Report/API/dashboard can synthesize different scorecards | Same serialized public API semantics | Contract test equality; old calculator has zero callers |
| Mutable `latest` artifacts | Concurrent clobber reproduced | Immutable artifacts plus verified pointer | Concurrent/crash/GC tests and consumer migration pass |
| Scattered config/defaults | 107 config files and code/env/Nix defaults reported | Versioned schemas and generated projections | Drift gate; old alias/read telemetry reaches zero |
| One-off test corpus | 419+ scripts reported | Risk-tiered focused suites and fixtures | Every retained test has owner/gate/runtime; duplicate/stale scripts archived safely |
| Phase archaeology/docs | 410+ Markdown files reported | Living reference compiled from canon plus history archive | Reference scan passes; onboarding uses only living docs |
| Research-only capabilities | Identity/affective/trading extensions named in kernel declaration | Explicit opt-in capabilities | Canonical routing never activates them; owner/probe/kill switch exists |
| Redundant services | Exact inventory `research_required` in C0.3 | Smallest modular-monolith deployment | No route/consumer, resource baseline improves, rollback drill passes |
| Legacy schemas/events | Current v1 round/A2A/telemetry records | Versioned canonical objects and adapters | Reader telemetry zero; retention expires; immutable audit remains accessible |

Repository policy requires archive scans and reference repair; “retire” never authorizes destructive
deletion. C0.3 must name exact paths, owners and dates before any archival slice.

`VERDICT: RATIFY-WITH-AMENDMENTS — the reference and migration direction is coherent, while exact
retirement file lists, measured dependency costs and restore evidence remain C0.3/Cycle 1 gates.`
