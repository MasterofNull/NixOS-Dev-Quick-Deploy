---
doc_type: reference
id: herdr-h2a-inventory-codex-review
title: Herdr H2A Inventory Codex Review
status: draft
reviewer: codex
review_role: operator-projection-product-integration
date: 2026-08-09
subject: .agents/plans/herdr-agent-operations/H2-DESIGN-PACKET.md
subject_sha256: 034faa63fa36a7ca1337fd234c4b49a8c4cb24d7665ec3178b56b5151536942a
contract_zero_sha256: 12c9e58c593a987ac31f6f52f8170b0969355d179de3b4b0d5389528112d9b90
implementation_authority: false
runtime_authority: false
---

# HERDR H2A proposed-inventory review

## Verdict

**REQUEST_REVISION — do not freeze or authorize the proposed inventory yet.**

The revised H2 packet substantially improves the original HERDR presentation contract: it freezes
closed objects and enums, defines a source ledger, bounds references/labels, adds replay/parity
vectors, separates activation, and proposes concrete file ceilings. Those improvements should be
retained.

One blocking divergence remains: the packet still defines a single normative
`aq.herdr.projection.v1` containing both canonical work context and HERDR presentation/runtime state.
Claude and Codex already signed the opposite architecture in contract-zero: compose
`aq.operator-context.v1` with a separate `aq.herdr.presentation.v1`. The proposed H2-P0 inventory
therefore cannot be frozen as written.

This review grants no write, implementation, staging, commit, build, deployment, socket, or runtime
authority.

## Blocking revisions

### B1 — split the normative contract and inventory

Replace the merged H2-P0 inventory with two independently closed, independently digestible pure
projections.

#### H2A-P0 — canonical operator context

Proposed ceiling:

- `config/schemas/operator-context.schema.json` (new);
- `config/operator-context-source-to-field-ledger.v1.json` (new);
- `scripts/ai/lib/operator_context_projection.py` (new);
- `scripts/testing/fixtures/operator-context-golden.json` (new);
- `scripts/testing/test-operator-context-projection.py` (new).

This slice implements only `aq.operator-context.v1` from contract-zero. It has no HERDR import,
binary, config, socket, process, pane, layout, package, or runtime dependency.

#### H2A-P0B — HERDR presentation health

Proposed ceiling:

- `config/schemas/herdr-presentation.schema.json` (new);
- `config/herdr-presentation-source-to-field-ledger.v1.json` (new, if a distinct ledger is needed);
- `scripts/ai/lib/herdr_presentation_projection.py` (new);
- `scripts/testing/fixtures/herdr-presentation-golden.json` (new);
- `scripts/testing/test-herdr-presentation-projection.py` (new).

This slice implements `aq.herdr.presentation.v1`. Before a separately authorized observation
adapter exists, actual runtime/session/socket/present-layout fields remain `not_authorized`,
`unknown`, or null. Static H1 package/config facts and desired-layout facts must not be represented as
observed runtime truth.

If an API/TUI response later carries both projections, it may use a closed response envelope that
preserves both complete schema versions, revisions, and digests. That envelope is a transport view,
not a third authority or merged projection.

### B2 — carry the signed R1-R7 semantics into the normative operator schema

The current normative top level (`freshness`, package/runtime/workspace/tabs/attention/coverage/
policy) does not contain the signed operator-context contract. The revised packet must explicitly
include or reference contract-zero's:

- `mission` with objective, workflow phase, definition-of-done counts, next gate, blocker, and
  evidence freshness;
- `work[]` with parent/child relationships, `interaction_mode`, steerability reason, canonical state,
  presentation observation, and explicit drift;
- ranked `attention[]` with recommendation, required authority, availability, evidence, and stable
  cognitive-load ordering;
- bounded `evidence[]` references and source digests;
- `learning` aggregate covering accepted lessons, improvement candidates, repeated failures, and last
  verified improvement age;
- human-comprehension acceptance vectors, including the parent-controlled child-session case.

HERDR `tabs` and layout labels consume derived operator-context fields; they are not substitutes for
the semantic work model.

### B3 — freeze the join and drift direction

The remaining integration contracts must define:

```text
canonical AQ -> aq.operator-context.v1 -> desired human/agent work presentation
HERDR observation -> aq.herdr.presentation.v1 -> presentation health
operator-context + herdr-presentation -> explicit comparison view -> drift
```

HERDR observation cannot be accepted as an input to the canonical operator resolver in a way that
changes canonical state. The comparison/join is a view with typed mismatch reasons.

### B4 — correct Service Coverage parity

Phase-0, TUI, and web must expose both projection identities, revisions, digests, freshness, and join
health. A single `aq.herdr.projection.v1` revision/digest is not sufficient parity evidence.

The web command center should render operator context as the human work experience and HERDR
presentation as a subordinate presentation-health card. `aq-tui-dashboard` remains the resilient
operator-context monitor and can show HERDR health adjacently.

### B5 — remove predetermined agent identity from slice ownership

The packet assigns future slices to `codex-subagent-herdr-*`. Replace those with capability/role
ownership such as `eligible independent implementer` and `independent flagship reviewer`. The
canonical workflow selects the cheapest healthy eligible lane at dispatch time and forbids
self-review; design documents must not permanently bind implementation to Codex.

### B6 — bind H1 readiness truthfully

The packet says H1 has independent PASS but is pending commit/package proof. Before any H2 freeze,
record the exact independent receipt/subject hash, accepted H1 file manifest, resulting atomic commit,
and package-availability evidence. Until those exist together, H2 remains design-only and must not
describe H1 as an accepted prerequisite in a way that implies implementation readiness.

### B7 — record owner ratification as a durable event

The owner instruction relayed through the separate Claude session should be written as an exact,
scoped ratification record stating what is authorized:

- contract and inventory preparation only;
- no implementation writes;
- no HERDR runtime, socket, pane, process, attach, rebuild, or activation;
- expiry or next gate.

Do not infer implementation authority from conversational wording or this review.

## Non-blocking recommendations

- Keep the packet's strict opaque `aqref:` reference grammar, but specify collision resistance and
  revocation/supersession behavior in the evidence/drill-in contract.
- Preserve the exact unknown/null semantics and tri-state policy fields.
- Preserve the collision scan and zero-active-writer requirement for shared Phase-0/TUI/web files.
- Treat the global ribbon as its own harmless monitor consumer of operator-context; it should not be
  coupled to HERDR tab availability.

## Required re-review subject

A revised packet should provide:

1. two explicit projection contracts and file inventories;
2. references to contract-zero SHA-256
   `12c9e58c593a987ac31f6f52f8170b0969355d179de3b4b0d5389528112d9b90`;
3. the remaining four integration-contract drafts;
4. truthful H1 and owner-ratification evidence;
5. dynamic implementer/reviewer role assignment;
6. no implementation or runtime grant.

## Sign-off

- Codex: REQUEST_REVISION on B1-B7; CONCUR with the retained closed-schema, ledger, redaction,
  accessibility, collision, activation-separation, and Service Coverage direction.
- Claude: PENDING targeted response/revision.
