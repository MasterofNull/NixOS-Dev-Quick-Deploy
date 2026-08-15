---
doc_type: reference
id: herdr-h2-canonical-aq--operator-context
title: Herdr H2 Canonical AQ to Operator Context Integration Contract
status: draft
date: 2026-08-09
parent_prd: herdr-agent-operations
parties:
  - claude-opus-4-8
  - codex
implementation_authority: false
runtime_authority: false
---

# Integration Contract: Canonical AQ records <-> `aq.operator-context.v1`

## Purpose and boundary

This is contract-zero for HERDR H2. It defines one pure, closed, surface-agnostic projection of
human-agent work context. HERDR, `aq-tui-dashboard`, and the web command center consume identical
operator-context semantics rather than independently interpreting canonical records.

This contract grants no implementation, runtime, socket, pane, process, deployment, staging, commit,
or activation authority. H2 implementation remains blocked on accepted H1, exact slice inventories,
owner ratification, and the remaining mutually agreed integration contracts.

`aq.operator-context.v1` answers "what does canonical AQ authority say about the work?"
`aq.herdr.presentation.v1` separately answers "is the HERDR presentation runtime healthy and showing
the expected layout?" Presentation observations never mutate canonical state.

## Shared interface

### Inputs

The resolver accepts only bounded, already-sanitized facts from named canonical adapters:

- program/task objective and workflow authority;
- TaskRegistry/TEG task, parent/child, role, lane, slice, state, and revision facts;
- exclusive lease ownership/mismatch facts;
- independent review receipt, subject digest, and verdict-state facts;
- bounded agent-event progress and interaction-capability facts;
- canonical attention, approval, blocker, and next-gate facts;
- lesson/improvement/regression aggregate facts;
- optional bounded presentation observations used only for explicit drift comparison.

Raw prompts, model reasoning, terminal content, argv, environment values, secrets, sensitive paths,
network identity data, provider credentials, and unbounded task/provider/session identifiers are not
valid resolver inputs.

### Output

The resolver emits exactly one `aq.operator-context.v1` object. It is:

- deterministic and byte-stable for identical normalized inputs;
- closed (`additionalProperties: false` at every object boundary);
- versioned and revision/digest bound;
- redacted and bounded before serialization;
- read-only and side-effect free;
- independent of HERDR libraries, binaries, sockets, processes, panes, and runtime availability;
- consumable unchanged by HERDR, TUI, and web surface adapters.

### Cardinal direction

```text
canonical AQ facts -> pure operator-context resolver -> HERDR / TUI / web
```

No consumer writes back through the projection. Human actions use separately audited AQ commands or
APIs and are governed by contract four; recommendations in this projection are advisory only.

## Data schema

Top-level field groups are frozen as:

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

### `mission`

- bounded objective summary or allowlisted objective token;
- canonical workflow phase;
- acceptance-criteria total, satisfied, and unknown counts;
- next-gate category and blocker category;
- canonical drill-in reference token;
- evidence freshness.

If a safe bounded objective source is unavailable, the objective is `unknown`; raw user prompts are
never substituted.

### `work[]`

- bounded task reference token and optional parent reference token;
- bounded child count;
- role, lane, slice token, canonical state, and record revision;
- `interaction_mode: direct|through_parent|read_only|unavailable|unknown`;
- bounded interaction-reason category and parent drill-in reference;
- presentation observation when available;
- explicit `drift: match|mismatch|unknown`;
- last-progress age bucket, blocker category, next-gate category;
- allowed-control categories for the current context, never executable control payloads.

Child-controlled sessions must render `through_parent` with a parent reference when canonical facts
support it. They must not appear as failed prompt inputs merely because direct input is disabled.

### `attention[]`

- severity, category, reason category, and age bucket;
- bounded work/evidence reference tokens;
- `recommended_action` category;
- `required_authority` category;
- `action_availability: available|through_parent|read_only|blocked|unavailable|unknown`;
- deterministic rank and stable group.

Priority order is frozen:

1. safety/integrity failure;
2. human approval or independent review required;
3. blocked or drifted work;
4. stale or unknown observation;
5. advisory improvement.

Each consumer enforces a bounded visible-item budget and exposes an overflow count. Agent, process,
token, or tool-call volume is never a headline productivity score.

### `evidence[]`

Only bounded reference token, evidence type, source authority, subject/revision digest, freshness, and
availability are projected. Raw receipts, terminal output, paths, and artifact contents remain in
their authoritative drill-in surfaces.

### `learning`

- accepted lesson/pattern count;
- improvement-candidate counts by bounded state;
- regression/repeated-failure count;
- last verified improvement age bucket;
- source health and evidence reference tokens.

The aggregate is observational. It cannot promote lessons, authorize changes, or equate activity
volume with improvement.

### `freshness`, `source_health`, and unknowns

Freshness uses bounded states and age buckets, not trusted raw lane clocks. Missing, stale, malformed,
conflicting, unauthorized, or unreadable sources propagate `unknown`, `unavailable`, `stale`,
`degraded`, or explicit drift. They never collapse to `0`, `false`, healthy, complete, accepted, or
blank `--`.

## Error behaviour

- Schema/version mismatch: reject the affected input; mark its source and dependent fields degraded
  or unknown.
- Missing source: preserve source-unavailable attention and unknown dependent values.
- Conflicting canonical facts: fail closed with conflict/drift; do not select a convenient winner.
- Redaction or bound violation: reject/redact before output and surface projection degradation.
- Unsafe identifier/content injection: never echo the input; emit a bounded rejection reason.
- Consumer version mismatch: consumer renders projection unavailable/degraded and must not synthesize
  compatibility defaults.
- Resolver failure: no last-known snapshot may be presented as fresh; cached data carries explicit
  stale provenance and age bucket.

## Auth and trust requirements

- Canonical adapters are read-only and named in a source-to-field ledger.
- The projection is not a task registry, workflow writer, review authority, lease authority, evidence
  store, action endpoint, or HERDR control client.
- Consumers cannot increase authority based on role labels, terminal text, pane state, or suggested
  actions.
- All eventual actions route through existing audited AQ paths and enforce current actor authority.
- Prompt/output inspection remains explicit operator drill-in and is excluded from normal projection,
  metrics, logs, RAG, and remote transport.
- Projection metrics are low-cardinality; task/provider/session identities are not metric labels.

## Required design and acceptance vectors

1. Identical normalized facts produce byte-identical output and digest.
2. Every output field maps to a named canonical source or explicit derived rule.
3. Missing or malformed sources remain visible unknowns, never healthy zero.
4. Terminal `done` without an independent receipt remains `needs_review` or drift.
5. A long-running local task with recent canonical step progress is not stale from wall time alone.
6. Child-controlled work clearly renders `through_parent` and points to the parent context.
7. Each recommendation shows why, evidence, required authority, and availability without becoming an
   executable mutation surface.
8. Prompt/output/secret/path/identity/reasoning injection cannot cross any consumer boundary.
9. HERDR, TUI, and web render the same schema version, projection revision, digest, priority order,
   and task/evidence reference semantics.
10. Keyboard-only, narrow-terminal, reduced-motion, and screen-reader summaries preserve mission,
    highest-priority attention, freshness, authority, and unknown/drift signals.

## Explicit exclusions

- `aq.herdr.presentation.v1` implementation and runtime probing;
- HERDR layout planning or reconciliation;
- dashboard/TUI/HERDR consumer implementation;
- human-control implementation;
- raw HERDR CLI/socket use;
- H1 baseline repair, acceptance, staging, commit, rebuild, or runtime activation;
- H3 brokered agent PTYs and all agent execution paths.

## Sign-off evidence

- Claude response: `.agents/plans/herdr-agent-operations/H2-CLAUDE-CODEX-COLLABORATION-BRIEF.md`,
  section "Claude response and sign-off" — `CONCUR-WITH-REVISIONS`, recommends the composed split,
  endorses Codex R1-R7, and explicitly marks canonical AQ <-> operator-context `AGREE`.
- Codex review: `.agents/plans/herdr-agent-operations/H2-CODEX-PRODUCT-UX-REVIEW.md`, exact reviewed
  H2 packet SHA-256 `70e04d37a13afeaad0f8ba63eb0bd04b705d36be03bb632918982caaffbcf02a`.

## Sign-off

- [x] Claude: AGREED — design contract only; composed projection split; no implementation/runtime
  authority. Evidence recorded in the shared collaboration brief.
- [x] Codex: AGREED — design contract only; R1-R7 incorporated; no implementation/runtime authority.
- [x] Owner: RATIFIED 2026-08-08 — contract-zero adopted as design; H2A-prep (exact implementation
  inventory + remaining integration contracts #2–#5) authorized; NO runtime activation. (Owner directive.)
- [x] Claude (orchestrator concurrence): the frozen contract faithfully captures the composed split and
  R1–R7, is read-only / pure / fail-closed with unknowns that never collapse to healthy-zero, routes all
  action through audited AQ paths, and grants no implementation/runtime authority. Sound for ratification.

Next gate: H2A-prep proceeds now (design only) → independent review → freeze — GATED for implementation
on accepted H1 (its draft supply-chain report must land and pin H2A's frozen input hash) plus a SEPARATE
implementation authorization with independent acceptance. No runtime activation before that chain.
