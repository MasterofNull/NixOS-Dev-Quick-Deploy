---
doc_type: reference
id: herdr-h2-codex-product-ux-review
title: Herdr H2 Codex Product and UX Review
status: draft
reviewer: codex
review_role: product-ux-human-agent-systems
date: 2026-08-09
subject: .agents/plans/herdr-agent-operations/H2-DESIGN-PACKET.md
subject_sha256: 70e04d37a13afeaad0f8ba63eb0bd04b705d36be03bb632918982caaffbcf02a
---

# HERDR H2 product and human-agent UX review

## Verdict

**REQUEST_REVISION — narrow, contract-level additions only.**

The packet is strong and directionally approved on authority separation, unknown-preserving
semantics, deterministic/redacted projection, unmanaged-pane preservation, accessibility,
Service Coverage, activation separation, rollback, and test vectors. The remaining revisions are
needed to make H2 a genuinely useful human-agent development interface rather than only an excellent
presentation-health monitor.

No implementation or activation is requested by this review.

## Required revisions

### R1 — represent mission intent and definition of done

Add a bounded `mission` aggregate sourced from the canonical program/task authority:

- objective summary or allowlisted objective token;
- current canonical workflow phase;
- acceptance-criteria count and satisfied/unknown counts;
- next gate and blocker category;
- evidence freshness.

The projection must not expose unbounded user prompts. If no safely bounded source exists, emit
`unknown` plus a canonical drill-in reference. The `control` tab should answer both "what are we
doing?" and "what would make it done?"

### R2 — expose parent/child ownership and steerability

Add bounded relationship and control metadata for managed work:

- parent reference token and child count;
- `interaction_mode: direct|through_parent|read_only|unavailable|unknown`;
- reason category when direct input is disabled;
- canonical parent drill-in reference when available.

This prevents child-agent transcripts from appearing broken. It must not grant new control authority
or expose raw provider/session identifiers.

### R3 — distinguish attention from authorized action

Each attention category needs a bounded recommended next step and authority requirement, for example:

```text
needs_review -> open canonical evidence -> reviewer/operator
through_parent -> open parent task -> parent/orchestrator
drift -> inspect layout check -> operator
unknown_source -> restore observation -> SRE/operator
```

Add `recommended_action`, `required_authority`, and `action_availability` categories. These are
advisory projection fields, not mutation endpoints. Any eventual action still routes through audited
AQ commands/APIs.

### R4 — provide evidence-linked explanations

Every blocker, next gate, drift, review, and recommendation should carry a bounded evidence reference
token plus source revision/digest. The UI needs a consistent "why am I seeing this?" drill-in without
copying raw evidence, terminal content, or sensitive paths into the projection.

### R5 — bound cognitive load, not only payload size

Freeze deterministic attention ordering and display budgets:

1. safety/integrity failure;
2. human approval/review required;
3. blocked/drifted work;
4. stale/unknown observation;
5. advisory improvement.

Define maximum visible attention items per surface, overflow counts, stable grouping, and a
no-animation/reduced-motion default for critical states. Agent/process/token volume must not become a
headline productivity proxy.

### R6 — include a small learning/evolution aggregate

H2 should reserve a bounded read-only aggregate for the system's development loop:

- recent accepted lesson/pattern count;
- improvement candidate count by state;
- regression or repeated-failure count;
- last verified improvement age bucket;
- evidence/source health.

This can initially render in `control` or the web dashboard and may be `unknown` when no canonical
source is available. It must not autonomously promote lessons or equate activity volume with progress.

### R7 — acceptance must include human comprehension

Add focused usability vectors alongside schema/accessibility checks:

- a user can identify the current mission, next gate, and highest-priority attention item quickly;
- a child-controlled session clearly explains why direct input is disabled and where to act;
- stale/unknown/drift cannot be mistaken for healthy or zero;
- the same task/evidence reference is recognizable across HERDR, TUI, and web;
- narrow-terminal and keyboard-only flows preserve mission, attention, and authority context.

Automated DOM/TUI contract tests are required, followed by a harmless operator canary before any
claim of usable H2 activation.

## Recommended shared contract split

Keep `aq.herdr.projection.v1` as the presentation-health/layout contract described by the packet,
or explicitly broaden it to `aq.operator-projection.v1`. If it remains HERDR-specific, compose it
with a separately closed, pure operator-context projection rather than duplicating mission,
attention, relationship, evidence, and control semantics independently in HERDR, TUI, and web.

Claude and Codex should agree on that split before schema or resolver implementation begins.

## Sign-off

- Codex: REQUEST_REVISION on R1-R7; otherwise CONCUR with the exact reviewed packet.
- Claude: PENDING response in `H2-CLAUDE-CODEX-COLLABORATION-BRIEF.md` or a hash-bound revision memo.
