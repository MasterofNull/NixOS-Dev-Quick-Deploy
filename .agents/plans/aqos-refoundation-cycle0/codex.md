# AQ-OS Refoundation Cycle 0 — Recovered Codex Proposal

**Provenance:** The original headless Codex dispatch exited after only
`Reading additional input from stdin...`. This file preserves an independently completed
Codex-team proposal that did not read any other lane artifact. No implementation was done.

## Product definition

AQ-OS is a local-first, reproducible control plane that converts human intent into
bounded agent work, preserves replayable evidence for each consequential transition,
and measures whether remote assistance improves local capability without weakening
operator control.

Non-goals for the next six months: chatbot/personality work, fleet/mobile/WASM product
expansion, NATS or microservice growth, a SPA rewrite, full SPIRE deployment, exactly-once
claims, or portability claims without a second continuously tested target.

## Evidence and authority diagnosis

- `verified_live`: Phase-0 availability is broadly green, but the effectiveness report
  remains warn/fail-shaped: useful-token evidence is absent, required reviews remain
  pending, validation can fail while operator trust passes, and delegation p95 is measured
  in minutes.
- `verified_source`: AQ-OS v1 can be `CONSENSUS_LOCKED` with empty persisted
  contributions and null aggregate evidence because lock eligibility follows lane status,
  not substantive verdict/evidence invariants.
- `verified_source`: A2A v1 makes workspace JSONL primary, accepts unsigned events,
  shares one optional HMAC, trusts producer time for LWW, reads O(n), and silently mirrors
  to Redis. This is clobber mitigation, not audit/workflow truth.
- `verified_source`: workflow, delegation, review, event, model execution, memory, eval,
  config, and operator status each have competing file/database/cache authorities.
- `verified_source/live`: NixOS, SOPS, AppArmor/nsjail, Postgres, Redis, Qdrant,
  switchboard, llama.cpp, brokered memory direction, activation gates, and guarded eval/
  training are assets to preserve.

Target ownership:

- Postgres: run/task/review/lease/eval/current-state plus immutable transition/event ledger
  and transactional outbox.
- Redis: cache, rate limits, wakeups, and rebuildable delivery only.
- Qdrant: semantic projection with source/version/freshness lineage.
- Local content-addressed filesystem: artifact bytes; Postgres holds metadata/provenance.
- Switchboard: the sole non-probe model-generation gateway.
- Modular coordinator: intent, policy, lifecycle, approvals, evidence, and capabilities.
- `aq` CLI and current console: clients of one versioned API.
- NixOS: deployment, identities, secrets, sandboxing, persistence, and rollback.

## Clean-sheet verdict

**RATIFY-WITH-AMENDMENTS.** Keep the owner's reference architecture, but use a modular
monolith plus isolated workers; implement Postgres state tables plus an event/outbox ledger
rather than pure event sourcing; begin workload identity with systemd/Unix identity and
per-producer asymmetric keys; keep full SPIFFE, new brokers, object-store daemons, and UI
rewrites out of Cycle 0.

The four-plane architecture is useful as an operator presentation, not as four independent
authority domains.

## Ranked parity gaps

1. P0 — consensus locks without substantive hashed evidence.
2. P0 — trust/effectiveness can pass with missing or failed required evidence.
3. P1 — no complete authority, duplicate-writer, and retirement inventory.
4. P2 — JSONL/Redis event spine is not durable/authenticated authority.
5. P2 — required reviews do not close or block consistently.
6. P2 — useful-token/trace producers violate their own schemas.
7. P2 — direct model callers bypass switchboard policy and attribution.
8. P2 — eval isolation and dataset/scorer lineage remain incomplete.
9. P2 — producer queues can outrun review/eval/inference consumers.
10. P2 — capability policy is not enforced at every effect boundary.
11. P2 — API/CLI/config compatibility paths have no enforced retirement.
12. P2 — portability lacks a continuously tested second target.

## Cycle 0 proposal

### C0.1 — Evidence-bound consensus

- Lock requires typed substantive contributions, acceptable explicit verdicts, independent
  review identity, contribution hashes, resolved conflicts, and aggregate path/hash.
- Empty, all-reject, self-review, malformed, provisional, and late-conflict fixtures must
  not lock.
- Existing invalid locked manifests surface `invalid_evidence`; never fabricate or rewrite
  evidence.
- Replay AQ-OS v1 and a fresh bounded round to deterministic states.

### C0.2 — Truthful evidence and outcome scorecard

- Every score declares availability, conformance, effectiveness, SLO reliability,
  numerator/denominator, freshness, sample size, provenance, and missing-data behavior.
- Required no-data/invalid/stale evidence degrades or fails dependent claims.
- `blocking_reasons` is non-empty for every failing/degraded dimension.
- Useful-token/run event producers validate at emission.
- Immutable run-ID QA/report artifacts replace a shared mutable latest-result authority;
  `latest` becomes a hash/run-ID pointer.
- Dashboard and CLI expose identical status/reason codes.

### C0.3 — Authority and retirement ledger

- Inventory each canonical object, current writers/readers, store, trust boundary,
  projections, bypasses, migration owner, rollback, and retirement deadline.
- New authorities/configs/CLIs/services fail CI unless they consolidate or retire a path.
- Compatibility paths expire after two completed cycles or 90 days, whichever is earlier,
  unless a dated owner exception is ratified.
- Produce one round replay and one failed-run evidence graph.

Cycle 0 adds no service and performs no Postgres migration. Cycle 1 remains blocked until
all three slices pass together and machine/human state agrees.

## Threat controls

- Reward corruption: isolated goldens, certified/versioned scorer, abstention, dedup,
  lineage, and promotion freeze on untrusted evidence.
- False consensus: evidence-bound verdict/quorum, distinct reviewer, replay invariant,
  and typed reopen/amend transitions.
- Split brain: one write authority, monotonic revisions, drift telemetry, and rebuildable
  projections.
- Capability escalation/exfiltration: short leases at orchestration and tool boundaries,
  egress classification/redaction, attributable deny/audit events, and revocation drills.
- Backlog/resource collapse: producer budgets, dedup, bounded queues, thermal/RAM admission,
  and deterministic shedding of background eval/indexing before interactive work.
- Metric gaming: outcome-linked denominators, missing-data failure, and contradiction tests.
- Strangler abandonment: measured dual-path use, hard expiry, and rollback ownership.

## Retirement decisions

- JSONL event bus, PULSE/RESUME, delegation registry/sidecars, Markdown consensus, and
  dashboard caches become projections rather than lifecycle authority.
- Direct llama generation paths retire after measured switchboard parity.
- Duplicate workflow/FSM implementations receive scoped adapter status or leave runtime.
- `aq-*` shims and generated/manual contract projections retire by measured use and expiry.
- Research identity/affective surfaces remain disabled admitted capabilities, not kernel.

## Verdict

**RATIFY-WITH-AMENDMENTS** — proceed only with evidence-bound consensus, truthful outcome
semantics, and the authority/retirement ledger; reject Redis/file audit authority,
exactly-once language, indefinite compatibility, and UI-first sequencing.
