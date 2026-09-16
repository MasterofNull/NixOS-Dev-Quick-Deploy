# ECC outcome integration implementation plan

Status: Gate A accepted; P0-A queued for coordinator dispatch  
Rule: one bounded, end-to-end slice at a time; implementation momentum continues
while nonblocking findings move forward to the next slice.

## Gate A — freeze evidence and contracts

- Finish semantic coverage of agent/skill clusters, hook implementations,
  orchestration, dashboards and relevant tests.
- Reconcile Antigravity report claims; label unsupported claims explicitly.
- Finalize feature-level verdicts and baseline measurements.
- Independently review the ledger, PRD, meta-prompt and this plan.
- Commit intake metadata and planning artifacts atomically. ECC remains disabled.

Completion: every selected outcome has upstream/local evidence, authority and
acceptance criteria; unknown catalog areas are visible and assigned, not implied
complete.

## P0-A — capability taxonomy and native resolver

Objective: prove actual outcome coverage before adding agents or skills.

- Extend the existing discovery/shared-skill surfaces with a versioned capability
  taxonomy independent of provider filenames; do not create a second registry.
- Index existing AQ-OS skills, domain instructions, tools, roles, CLIs and QA coverage.
- Map sampled ECC capabilities to equivalent/stronger/partial/missing/unsuitable.
- Add deterministic query/report output, collision/ambiguity diagnostics and a
  dashboard coverage/gap view.
- No prompt activation or skill installation in this slice.

Acceptance: representative fixtures cover existing, aliased, ambiguous, missing
and denied capabilities; QA and dashboard agree; inventory freshness is visible.
Exact ownership, baseline, validation commands and stop conditions are frozen in
`P0A-SLICE-BRIEF.md`.

## P0-B — canonical provider projection compiler

Objective: eliminate configuration drift without copying secrets or overwriting
adopted provider state.

- Extend existing canonical compile/sync tooling with one typed
  role/tool/hook/capability contract.
- Preview deterministic provider projections for Codex, Claude, Gemini and local.
- Refuse unknown/colliding fields and secret-bearing output; hash-bind confirm.
- Use existing guarded project installer, backup, receipt and rollback machinery.

Acceptance: byte-deterministic fixtures, round-trip/drift detection, brownfield
preservation, stale-confirmation refusal, rollback proof, QA/dashboard visibility.

## P0-C — typed lifecycle event adapter

Objective: close useful pre/post/failure/compact/stop event gaps safely.

- Event schema includes source, target, payload classification, capability lease,
  timeout, fail policy, loop budget, outcome and evidence ID.
- Handlers are explicitly registered and least-privileged; no dynamic root search
  or inherited whole environment.
- Suspend/resume, cancellation, backpressure and crash recovery are first-class.

Acceptance: malformed/untrusted payloads, missing tools, timeout, handler crash,
suspend/resume and recursive-event suppression tested; dashboard shows health,
latency, failures and disabled handlers.

## P0-D — hermetic candidate evaluation evidence

Objective: join real containment with tamper-evident evaluation and promotion.

- Bind artifact digest, exact sandbox/lease/network configuration, fixtures,
  actual exit/output/resource metrics and append-only receipt.
- Require independent reviewed promotion; receipt integrity alone never PASSes
  candidate behavior.
- Dogfood one harmless local-agent capability through baseline and after-run.

Acceptance: escape/secret/network/write denials, timeout/kill, corrupted receipt,
replay, suspended host and reviewer mismatch all fail closed and are observable.

## P0-E — portable GitHub CI pack

Objective: enforce factory fundamentals in generated greenfield projects and
guarded brownfield adoption.

- Pin actions by immutable SHA; least-privilege permissions and fork-safe secrets.
- Run structure, formatting, tests, secret/supply-chain scans, bundle self-test and
  evidence validation with explicitly blocking/nonblocking policy.
- Produce attestable artifacts/provenance where supported.
- Preserve existing workflows; preview/confirm collisions.

Acceptance: fixture repositories cover greenfield, adopted brownfield, collision,
untrusted PR and missing-secret cases. Local tests validate rendered workflows.
Register a focused integration result in `aq-qa` and project CI policy/render
status into the dashboard. Remote required checks/rulesets remain
`UNVERIFIED_REMOTE` until authorized; metadata-only checks never display PASS.

## P1 — operator diagnostics and eval dimensions

- Add bounded memory recall completeness/invalid/symlink/truncation telemetry to
  the existing memory authority and dashboard.
- Add silent-failure, cancellation, suspend/resume, permission-denial, resource
  and completion-truth dimensions to existing local dogfood/eval loops.
- Add only capability gaps proven by P0-A; use skill intake one candidate at a
  time with source/license/security review.
- Harden the existing `WorkspaceManager` merge/Tier-0/operator path if measured
  use demonstrates a gap; do not build a duplicate worktree orchestrator.
- Bind existing discovery/shared-skill APIs into the current dashboard's
  searchable capability catalog; do not add a redundant discovery service.
- Intake an accessibility review rubric only if a focused comparison shows a
  missing WCAG/keyboard/screen-reader outcome; integrate it with existing UI
  testing and keep browser/write authority separately gated.

Acceptance: each selected P1 outcome receives a bounded slice brief before edit,
focused tests plus an integration-path `aq-qa` result, and a dashboard indicator
for freshness/health/failure. Missing live evidence displays `UNVERIFIED`, never
PASS. Suspend/cancel/permission/resource cases must be exercised where relevant.

## P2 — separately approval-gated CD

- Environment approvals, concurrency, artifact verification, deployment health,
  owner-controlled promotion and rollback.
- No external account, repository setting, secret or production mutation without
  explicit owner authority and verified recovery path.

Acceptance: isolated renderer fixtures cover environment approval, concurrency,
artifact digest/provenance verification, failed health gate and rollback plan;
an `aq-qa` check and dashboard status distinguish local-template readiness from
`UNVERIFIED_REMOTE`. Any live GitHub/environment/deployment mutation requires
separate owner authorization and a rehearsed rollback; absent authority stops
activation without blocking repo-only implementation.

## Per-slice coordinator envelope

Every dispatch must state: objective; owned files/sections; evidence inputs;
explicit exclusions; permissions; tests/live proof; QA/dashboard contract;
completion/stop conditions; reviewer independence; activation authority; and the
next dependency. A lane may not expand scope or accept its own implementation.
