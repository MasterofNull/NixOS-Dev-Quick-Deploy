---
doc_type: plan
id: herdr-agent-operations-h2
title: Herdr H2 Monitored Presentation
status: deprecated
owner: codex-orchestrator
date: 2026-08-08
parent_prd: herdr-agent-operations
depends_on: H1-independent-PASS
---

# H2 design packet — monitored presentation only

> **Historical, non-authoritative design.** This merged `aq.herdr.projection.v1` proposal was
> superseded by the independently split operator-context and HERDR-presentation contracts and
> their dormant P0/P0B implementations. It grants no current implementation, integration, or
> activation authority and must not be used as active projection provenance.

## Decision and boundary

H2 renders existing AQ-OS records into a persistent terminal information
architecture. It is a **presentation projection**, not an execution or
lifecycle system. H1 has an independent `PASS`, but is pending its atomic
commit and package availability proof. H2 may be reviewed now. H2-P0 writes
require the accepted H1 candidate to be atomically committed at its reviewed
hashes; H2-P1/P2 additionally require the pinned package identity to evaluate
locally. No H2 activation or actual Herdr observation is authorized by either
gate.

AQ TaskRegistry/TEG, exclusive leases, review receipts, the tracker, local
inference contracts, and Phase-0/service evidence remain authoritative. Herdr
observations can add `presentation_drift`; they cannot change task state,
admission, model routing, review outcome, lease ownership, or release state.

H2 explicitly excludes attach/start/close/send-text/keys/process launch,
restore, plugin, integration, update, remote/bootstrap, agent prompt, and all
socket mutation. A later, separately authorized activation/canary slice owns
any real server or PTY action.

## Closed projection contract — normative

The adapter emits exactly `aq.herdr.projection.v1`. It is a deterministic,
versioned, redacted snapshot with source revision/digest and freshness metadata.
Unknown is represented as `unknown` or `null`, never `0`, `false`, or healthy.

Every object is closed (`additionalProperties:false`). Required top-level
fields and types are:

| Field | Type / bound |
|---|---|
| `schema_version` | const string `aq.herdr.projection.v1` |
| `projection_revision` | string, exactly 64 lowercase hex |
| `projection_digest` | string, exactly 64 lowercase hex |
| `generated_at` | RFC3339 UTC string, max 35 chars |
| `freshness` | object `{state,age_bucket}` |
| `package_state` | enum below |
| `runtime_state` | enum below |
| `workspace` | closed workspace object below |
| `tabs` | array, exactly seven tab objects in frozen order |
| `attention` | closed six-counter object |
| `coverage` | closed sources/surfaces object |
| `policy` | closed six-policy object |

H2-P0 introduces a closed `aq.herdr.read-snapshot.v1` envelope assembled by a
pure reader under the already-ratified AQ coordinator/projector boundary. It is
not persisted as a lifecycle store and has no writer authority. Its required
fields are `schema_version`, `sources`, `snapshot_revision`, and
`generated_at`; every object is closed. `sources` contains exactly the seven
ledger source IDs and, for each, its canonical `record_revision` (bounded
integer/string exactly as its source schema defines), validated 64-hex digest,
availability enum, and no raw payload.

`snapshot_revision`/top-level `projection_revision` is the full lowercase
SHA-256 of the canonical ordered tuple
`(ledger_version, source_id, canonical_record_revision, validated_digest,
availability)` for all seven sources. The pure reader derives this content
token; it does not mint or advance lifecycle state. ContextStore may cache and
serve an accepted projection, but is storage/projection only and cannot mint
the snapshot revision or alter canonical source revisions.

`generated_at` is a caller-supplied, validated, normalized uppercase-`Z` UTC
RFC3339 input. The resolver performs no clock read. It is included in canonical
projection bytes and `projection_digest`, but excluded from the content-derived
snapshot revision. Identical complete inputs produce identical bytes/digest.
The same snapshot revision with the same source tuple and a newer valid
`generated_at` is a refreshed rendering; an exact full-input replay is
byte-identical. The same snapshot revision with a different source tuple is a
hash/contract conflict and is rejected. CAS binds both `projection_revision`
and `projection_digest`, so a refreshed rendering cannot be mistaken for the
prior projection. No numeric ordering or lower/higher lifecycle claim is made.

Normative enums are complete:

- freshness state: `fresh|stale|unknown`; age bucket:
  `lt_30s|lt_5m|gte_5m|unknown`;
- package: `disabled|configured|available|unavailable|degraded|unknown`;
- runtime: `not_activated|configured_not_running|running|degraded|unavailable|unknown`;
- tab state: `healthy|attention|degraded|unknown|not_authorized`;
- attention: `none|blocked|stale|needs_review|drift|unmanaged|unknown`;
- source availability: `available|missing|stale|malformed|conflict|unknown`;
- surface coverage: `not_implemented|pass|degraded|mismatch|unknown`;
- every policy field: tri-state `disabled|enabled|unknown`—never boolean.

`workspace` requires `desired_name` (const `aq-os`), `desired_revision`
(64 lowercase hex content token), `desired_digest` (64 lowercase hex),
`observation_state` (`not_authorized|unknown|available|degraded`),
`present_revision` (integer bound or null), `present_digest` (64-hex or null),
`expected_tabs` (the seven const names), `present_tabs` (null until a separately
activated adapter, otherwise unique array max 7 from the tab enum), and
`counts`. `counts` requires `managed|unmanaged|orphan|missing|drift`, each
integer `0..1000000` or null; null means unknown.

Each `tabs` element requires: `name`, `state`, `freshness`, `attention_count`
(bounded integer or null), `managed_count` (bounded integer or null), and
`labels` (max 32). Names are exactly `control|reasoning|implementation|review|
research|local|ops` in that order. Labels require `attention`, `role`, `lane`,
`slice_token`, and `record_revision`. Role allowlist:
`owner|orchestrator|architect|reviewer|implementer|researcher|operator|local_agent|
logic|embedding|unknown`; lane allowlist:
`codex|claude|antigravity|local|system|human|unknown`. `slice_token` matches
`^[a-z0-9][a-z0-9-]{0,31}$`; it must come from the source ledger allowlist and
is never derived by truncating arbitrary input. `record_revision` is bounded
integer or null. Each rendered label is max 96 characters.

`attention` requires `blocked|stale|needs_review|drift|unmanaged|unknown`, each
bounded integer or null. `coverage.sources` contains exactly the seven ledger
source IDs, each with `availability`, `digest` (64-hex or null), and
`age_bucket`; `coverage.surfaces` requires `phase0|tui|web` using the surface
coverage enum. `policy` requires `updates|manifest_checks|plugins|integrations|
restore|remote_bootstrap` using the tri-state policy enum. Any `enabled`,
`unknown`, schema mismatch, projection revision mismatch, or digest mismatch
degrades all three surfaces and blocks release.

Default labels are only `<attention> <role>/<lane> · <slice-token> ·
r<record-revision>`. No field accepts prompt, output, argv, filesystem/socket
path, secret, SSID, IP, full task ID, provider text, or model reasoning.

## Canonical inputs and mapping

| Tab | AQ authority | H2 projection | Never inferred |
|---|---|---|---|
| control | program tracker + owner decisions | next gate, blockers, release queue, attention totals | owner approval |
| reasoning | collaboration rounds + review receipts | lanes, dissent/unavailable counts, reviewed subject state | a verdict from terminal text |
| implementation | TaskRegistry/TEG + exclusive lease | admitted/queued/blocked worker counts and lease mismatch | task admission or completion |
| review | independent review receipts + subject hashes | pending/accepted/revision-needed counts | self-acceptance |
| research | admitted read-only research tasks | active/parked evidence-intake counts | external action or trust |
| local | local-agent/logic/embedded contracts | modality queue, progress bucket, thermal/headroom state | progress from elapsed time alone |
| ops | Phase-0/QA/services/health evidence | service coverage, degraded checks, broker/package state | service health from a pane |

Absent, stale, malformed, or conflicting input causes the relevant tab/source
to be `unknown`/`degraded`; it does not suppress the defect or collapse it to
zero.

H2-P0 must create the versioned ledger
`config/herdr-source-to-field-ledger.v1.json`. It is the sole read allowlist and
binds each projection field to: canonical source ID; exact source path or
existing typed reader; trusted schema/version; digest validation rule;
absence/malformed/conflict disposition; maximum age; and permitted fields.
The seven source IDs are `program_tracker|task_registry_teg|leases|
review_receipts|local_inference|phase0_qa|service_health`. The resolver rejects
unlisted paths, caller-selected sources, directory traversal, source aliases,
and records whose digest/schema/revision does not match the ledger.
The read-snapshot schema lives at
`config/schemas/herdr-read-snapshot.schema.json`; the pure snapshot reader is
`scripts/ai/lib/herdr_source_snapshot.py`. Both are owned by the canonical AQ
coordinator/projector projection boundary and perform read/validation only.

## Information architecture and operator flow

Design direction: a dense, industrial operations console with a single clear
attention rail, evidence-first drill-ins, and stable spatial memory. It avoids
chat-like panes and “agent theatre”: operators see bounded state, provenance,
and gaps before terminal material.

```text
AQ-OS · PRESENTATION ONLY · revision r42 · freshness <30s
┌ ATTENTION ─ 2 blocked · 1 review · 1 drift · source: 6/7 available ─────┐
│ CONTROL | REASONING | IMPLEMENT | REVIEW | RESEARCH | LOCAL | OPS       │
├─────────────────────────────────────────────────────────────────────────┤
│ CONTROL                                                                  │
│ Next gate: independent review          │ Authority mismatch: 1 unknown  │
│ Program slice: bounded projection      │ Release queue: parked           │
├─────────────────────────────────────────────────────────────────────────┤
│ Evidence timeline (receipt digest + age bucket only)                     │
│ [tracker fresh] [registry fresh] [local stale] [phase0 fresh]            │
├─────────────────────────────────────────────────────────────────────────┤
│ Managed groups (redacted labels)      Unmanaged / missing / drift        │
│ ! reviewer/claude · c1b · r12         1 unmanaged · preserve, inspect   │
└─────────────────────────────────────────────────────────────────────────┘
```

Operator flow: inspect Attention → select tab → open AQ-owned detail view by
an opaque canonical reference matching `^aqref:[a-z0-9._-]{1,32}:[a-zA-Z0-9_-]{1,88}$`
(maximum 128 characters) → compare evidence/source freshness → choose an
existing AQ workflow action. H2 itself has no action button that mutates a
Herdr server. `layout --check` and `reconcile --dry-run` in a later adapter
are expected-revision/CAS plans only: the plan binds projection revision,
desired layout digest, and present-layout digest; mismatch, stale source, or
unmanaged pane yields `conflict|stale|unknown` and no mutation.

Drill-in uses the existing command-center authentication/authorization layer
and resolves only the opaque reference through an allowlisted AQ reader. It
rejects arbitrary source/path/URL/query selection and never accepts a raw
record payload from the browser or TUI.

Through H2-P2, real session state, present panes/tabs, socket facts, and applied
layout remain `unknown`/null. Only desired static layout may be projected.
Actual observations require the separate adapter activation and canary.
Unmanaged panes are preserved and visibly labelled `unmanaged`; missing or
orphaned managed projections are surfaced as defects. H2 never kills,
renames, moves, or claims them automatically.

## Accessibility and narrow terminals

All state uses text plus color, high-contrast attention glyphs, keyboard tab
navigation, focus order matching the tab order, and concise ARIA-equivalent
semantic labels in web/TUI projections. Narrow widths show the active tab,
attention count, and an overflow picker; they do not compress seven tabs into
illegible columns. Reduced-motion mode removes nonessential animation. A
screen-reader summary exposes source freshness and unknowns before counts.

## Service Coverage contract

H2 is incomplete unless the same closed projection is:

1. exercised through a Phase-0 `aq-qa` integration path using canonical
   fixtures and a no-runtime configured/not-running state;
2. shown in `aq-tui-dashboard` Agent Ops with attention, source freshness,
   package/runtime state, and managed/unmanaged/drift counters; and
3. shown in the web command center through one read-only API/card with the
   identical projection revision/digest.

Metrics are low-cardinality: source availability, freshness bucket, bounded
state/reason, tab count, and aggregate counts. No default labels or metrics
contain terminal content, prompt/output, path, identity network data, secrets,
or high-cardinality task/provider values.

## Implementation slices, inventories, and activation

- **H2-P0 projection contract** — owner `codex-subagent-herdr-h2-p0-implementer`;
  exact proposed inventory: `config/schemas/herdr-projection.schema.json` (new),
  `config/schemas/herdr-read-snapshot.schema.json` (new),
  `config/herdr-source-to-field-ledger.v1.json` (new),
  `scripts/ai/lib/herdr_source_snapshot.py` (new),
  `scripts/ai/lib/herdr_projection.py` (new),
  `scripts/testing/fixtures/herdr-projection-golden.json` (new), and
  `scripts/testing/test-herdr-h2-projection.py` (new). No Herdr invocation.
- **H2-P1 Service Coverage** — owner `codex-subagent-herdr-h2-p1-implementer`;
  proposed inventory: `scripts/testing/harness_qa/phases/phase0.py`,
  `scripts/ai/_aq-qa-bash`, `scripts/ai/aq-tui-dashboard`,
  `dashboard/backend/api/routes/aistack.py`, `assets/dashboard.js`,
  `dashboard.html`, and one new focused parity test
  `scripts/testing/test-herdr-h2-service-coverage.py`. No socket connection.
- **H2-P2 dry-run plan** — owner `codex-subagent-herdr-h2-p2-implementer`;
  exact proposed inventory: `config/schemas/herdr-layout-plan.schema.json`
  (new), `scripts/ai/lib/herdr_layout_plan.py` (new), `scripts/ai/aq-herdr`, and
  `scripts/testing/test-herdr-h2-layout-plan.py` (new). No apply path.
- **H2-A activation:** separate owner authorization, independent review,
  rebuild checkpoint, harmless canary, and live Service Coverage. It is not
  implied by H2-P0/P1/P2 acceptance.

These are proposed ceilings, not write authority. Before each slice, a freeze
packet must record exact HEAD, file hashes or NEW state, implementer/reviewer,
exclusive lease, and collision results; independent design review and owner
activation then bind the final inventory. P1 overlaps high-churn shared QA/TUI/
web files and therefore requires zero active writers in every listed path.
Each slice must collision-scan its exact file inventory, TaskRegistry/TEG
writer boundary, existing dashboard/TUI owners, socket/client ownership, and
foreign worktree changes before first write. Drift or overlap stops the slice.

## Acceptance vectors

1. Identical canonical inputs produce byte-identical projection/digest.
2. A missing tracker, receipt, local, or Phase-0 source yields the affected
   `unknown` state and source-unavailable attention; it never yields zero.
3. Prompt, output, secret, argv, path, SSID, IP, raw model reasoning, and
   long task ID injection are rejected/redacted before labels, telemetry, TUI,
   and web output.
4. Terminal “done” with no independent receipt remains `needs_review`.
5. A terminal “working” with stale/no registry evidence remains `unknown` or
   `drift`, not active.
6. A local task with recent canonical step progress is not labelled stale solely
   by long elapsed wall time.
7. Unmanaged, missing, and orphan panes remain visible and no plan contains a
   close/kill/rename effect.
8. A dry-run plan with stale revision or digest mismatch returns conflict and
   makes no socket call.
9. Phase-0, TUI, and web receive the same schema version/revision/digest.
10. Narrow and screen-reader views retain attention/freshness/unknown signals.
11. Reusing an old projection revision/digest, replaying a plan against a new
    present digest, or mixing surface schema versions degrades every surface
    and blocks release.
12. Unsafe label vectors containing traversal, paths, IP/SSID, prompt/output,
    secret-like material, non-allowlisted role/lane, or truncation collisions
    are rejected rather than sanitized into an ambiguous label.
13. The same canonical source revision/digest tuple derives the same snapshot
    revision; a different tuple derives a different full token. Forced token
    reuse with different tuple is `conflict`; exact full-input replay is
    byte-identical; timestamp-only refresh retains snapshot revision but changes
    projection digest. No ContextStore or resolver lifecycle write occurs.

## Threats, rollback, and stop conditions

Threats: terminal content exfiltration; same-user socket authority bypass;
visual-state/lifecycle confusion; stale source false health; dark presentation
surfaces; destructive reconciliation; feature creep into launcher/remote/plugin
paths; dashboard/TUI disagreement; and source ownership collision.

Mitigations are structural: socket-blind H2 code, closed redacted projection,
canonical input ledger, unknown-preserving resolver, expected-revision dry-run,
unmanaged preservation, independent surface parity checks, and no mutation API.

Rollback is declarative removal/disablement of the H2 projection surface only.
It does not stop Herdr, alter PTYs, kill panes, modify AQ records, or delete
receipts/evidence. Stop immediately on any request to attach, launch, mutate a
socket/layout, start a unit, add a plugin/integration/remote path, expose
terminal content, discover a second authority/writer, fail a redaction vector,
or lack exact Service Coverage ownership. Live canary/rebuild is permitted
only after H2 implementation acceptance, independent review, and a distinct
owner activation grant.
