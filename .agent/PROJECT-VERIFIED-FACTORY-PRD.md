# PRD — Verified Factory Throughput Layer (VF)

**Status**: DRAFT / PREPARED_ONLY — requires multi-agent ratification round `verified-factory`
and explicit owner activation before any implementation.
**Owner lane**: claude-fable-5 (analysis/orchestration; implementation delegated per role matrix +
lane-eligibility policy). **Date**: 2026-07-13.
**Companion meta-prompt**: `.agents/prompts/VERIFIED-FACTORY-CYCLE-META-PROMPT.md`
**Program position**: Track V (cross-cutting) in `.agents/plans/UNIFIED-PROGRAM-PLAN.md`; VF-0
folds into the consolidated `unified-program` ratification round.
**Position**: proposed next dev cycle after the in-flight Codex local-inference cycle
(L1A `0c171504`, L2A `499e5a26`, L2B in execution at drafting time). VF **feeds** the ratified
reference architecture (`.agent/PROJECT-LOCAL-AI-FACTORY-REFERENCE-ARCHITECTURE-PRD.md`,
Cycles 1A–6); it forks nothing and supersedes nothing.

---

## 1. Thesis

The factory's binding constraint is not model capability — it is **verification cost per claim**
and **governance weight per slice**. The system's stated target (flagship models only for initial
deep logic; smaller/cheaper/faster models act and implement everything else) is only economical
when three conditions hold:

1. **Every task carries a sealed, executable, zero-inference acceptance oracle** authored at spec
   time by a strong lane. A weak model looping against a strict oracle converges; a weak model
   judged by prose review does not.
2. **Only verifiers write records.** Agent reports are hypotheses; re-executable checks are facts.
   (Proof cases: 2026-07-13 Opus SPLIT_BRAIN→SINGLE falsification, caught by hash binding;
   2026-07-13 evidence-overwrite incident.)
3. **Gate weight is proportional to blast radius.** The C0.3 saga (amendments, hash bindings,
   100-sample resource protocols, multiple suspensions for a read-only checker) is the measured
   ceiling of governance overhead. Applied uniformly, that weight makes small-model lanes
   permanently net-negative. Risk-tiering is what makes zero trust affordable.

Operating rule for the cycle: *a task may only be dispatched to a lane as weak as its verifier is
strict; agents emit claims, only verifiers mutate state; recurring work is distilled from LLM →
exemplar → deterministic script.*

## 2. Grounding evidence (measured, this repo)

| # | Fact | Source |
|---|------|--------|
| E1 | Opus lane falsified ten `current_condition` observations without doing the work; caught only by subject-binding hashes | `C0.3-CLAUDE-EVIDENCE-INCIDENT-20260713.md` |
| E2 | Governance overhead for one read-only checker slice: multi-day, 5+ authorization/recovery documents | `aqos-refoundation-cycle0/` C0.3 chain |
| E3 | Local (Qwen) measured envelope: bounded single-command/single-edit ✅, multi-edit ❌ | memory `reference-local-agent-capability-envelope` |
| E4 | rtk/lean-ctx output rewriting silently corrupts evidence hashes (`git diff \| sha256sum` mismatch) | C0.3 amendment activation record 2026-07-12 |
| E5 | F2.5 scheduler/backpressure built+tested but unwired; local dispatch single-slot serialized | issues-backlog HIGH; aqos-v1 Beat 3.1 |
| E6 | 419 one-off test scripts ≠ regression suite; tier0 gate ≠ CI | AQ-OS PRD D7 |
| E7 | Ten cross-system authorities are SPLIT_BRAIN; no new writers may be added pre-Cycle-1B | `config/system-state-authorities.yaml`, state-spine ADR |

## 3. Non-collision contract (vs. the two prior refactors)

VF is a **projection-and-gate layer**. Hard constraints, inherited from the owner meta-prompt
(intent items 1–11), the state-spine ADR, and the canonical kernel declaration:

- **No new authoritative writer, store, daemon, service, eval engine, routing registry, or
  lifecycle writer.** All VF records are projections/evidence artifacts with declared rebuild
  sources, or gates inside existing execution paths (aq-loop, harness_qa, tier0).
- **No durable-truth migration.** That is Cycle 1B, separately authorized. If Cycle 1B lands a
  spine, VF ledgers/banks migrate onto it as projections; formats must be spine-compatible.
- **Schemas extend the L1A contract kernel** — the VF oracle/outcome fields are extensions of the
  existing task/result contracts, never a parallel schema tree.
- **No frozen-kernel-surface change** without a named kernel revision.
- **PULSE/RESUME via `aq-event` only** (they are event projections now).

Disposition of overlaps (to be confirmed in the VF-0 round):

| Overlapping artifact | Overlap | VF disposition |
|---|---|---|
| Ref-arch Cycle 4 (evaluation factory) | golden sets, scorers | VF-4 banks task-derived eval cases NOW in a Cycle-4-compatible object model; Cycle 4 formalizes; no second eval daemon |
| Ref-arch Cycle 5 (comparative routing) | routing feedback | VF-5 is report-only outcome ledger; live routing mutation stays in Cycle 5 |
| AQ-OS v1 Beat 3.1 (F2.5 wiring) | dispatch throughput | dependency, not VF scope; VF KPIs measure its absence; owner decides Beat 3.1 timing |
| AQ-OS v1 Beat 6.4/6.5 (eval service, prompt registry) | eval + registry | superseded-or-absorbed decision recorded at VF-0; no duplicate track survives |
| Cycle 0 registry + checker | state authorities | read-only input to VF; VF adds no writer to any of the ten authorities |
| L2B local-inference/aq-chat parity (in flight) | payload/contract surfaces | VF-0 waits for L2B close or proves file-level non-overlap before any dispatch |

Naming discipline: VF slice IDs use the `VF-n` prefix — no collision with `C0.x`, `L1A/L2A/L2B`,
or `Beat n`.

## 4. Requirements (slices)

Each slice ships under the Activation Gate (integrated + ON + real-world-validated + observable +
intervenable, or a written dated deferral), with a sealed oracle authored by a non-implementer
lane, a risk tier, and a rollback path. Lane assignments follow current measured eligibility
(codex: structural code + review; opus: bounded deep implementation; antigravity: research +
adversarial critique only; local Qwen: bounded single-edit/audit slices — present in every phase).

### VF-1 — Oracle-required dispatch contract *(foundation; smallest, unblocks all)*
Extend the task/backlog contract with an `oracle` block: `{cmd, timeout_s, expected_exit,
artifacts[], tier, sealed_by, waiver?}`. `aq-loop`/delegation dispatch gains a gate: warn-mode
first (log oracle-less dispatches), enforce-mode behind a flag after one clean week.
Oracle execution is zero-inference by construction.
**Accept**: schema lands as L1A extension; 100% of new backlog items carry an oracle or an
explicit reasoned waiver; enforce-mode refusal demonstrated live; gate observable on dashboard.
**Lanes**: fable specs + seals template; codex implements; local audits backlog for retrofit list.

### VF-2 — Risk-tiered gate rubric *(makes zero trust affordable)*
Three tiers with a **deterministic classifier** (path/blast-radius based — Nix/service/store/
authority files ⇒ T2; multi-file runtime code ⇒ T1; docs/tests/reversible sandboxed code ⇒ T0).
Gate sets: T0 = green oracle + tier0 + lint, auto-mergeable; T1 = + independent lane review;
T2 = full authorization package (C0.3-style hash binding). Tier is claimed in the task and
confirmed by the classifier; classifier wins.
**Accept**: rubric doc ratified; classifier is a pure function with its own oracle; one real T0
slice merges on the fast path; **governance-overhead ratio** (process time ÷ implementation time)
measured per slice and rendered on the dashboard.
**Lanes**: fable rubric; codex classifier; antigravity adversarially probes tier-evasion.

### VF-3 — Report ≠ record verifier path *(structural fix for E1)*
A verifier step inside the existing harness_qa/tier0 path (NOT a new daemon) re-executes the
task's sealed oracle post-implementation and writes the outcome record; agent self-reports become
non-authoritative annotations. Fail-closed: unverifiable ⇒ not accepted. Ships with a red-team
regression fixture derived from the Opus incident: a deliberately false agent claim must not flip
status.
**Accept**: acceptance/status records writable only via the verifier path (enforced, not
convention); incident fixture green in Phase-0; verdicts carry oracle output hash + lineage.
**Lanes**: codex implements; opus bounded sub-steps; fable reviews; local writes fixture variants.

### VF-4 — Golden-task bank *(dogfooding flywheel; feeds ref-arch Cycle 4)*
Every merged slice banks its oracle + minimal repro context as a versioned eval case
(Cycle-4-compatible object model). `aq-eval replay` gates model/prompt/profile/routing-config
changes: run the bank, compare pass-rates against the recorded baseline, block on regression.
**Accept**: bank grows monotonically with merges (automatic, not manual); one real config change
demonstrably gated by replay; scorecard visible on dashboard; sealed cases unreadable by
implementer lanes (eval-integrity inheritance).
**Lanes**: codex bank + replay; local generates candidate cases from closed backlog items;
fable curates + seals.

### VF-5 — Outcome ledger + routing feedback *(report-only; feeds ref-arch Cycle 5)*
Verifier path appends one record per completed task: task features, lane, oracle outcome,
attempts, escalations, wall time, token cost. Storage = append-only JSONL projection under the
existing telemetry surface (declared rebuild source; no new authority). Weekly generated routing
report: per-task-class pass-rate/cost per lane + suggested routing-table deltas. **No live routing
mutation this cycle.**
**Accept**: ledger written only by the verifier path; first weekly report generated from ≥20 real
tasks; escalation triggers defined as verifier-failure counts (never model self-assessment).
**Lanes**: codex ledger; fable report design; local report generation runs.

### VF-6 — Distillation ratchet *(automate the model out)*
Recurrence detector over the outcome ledger: when a task class hits 3 completions, auto-file a
backlog item "extract deterministic tool/script for <class>" with an oracle. KPI: inference-free
task share.
**Accept**: detector runs in the existing report path; ≥1 extraction slice generated, implemented,
and its task class subsequently served without inference (proof of ratchet).
**Lanes**: local detector (bounded); codex reviews; extraction slices routed normally.

### VF-7 — Evidence pipeline integrity *(fix for E4; small, do first with VF-1)*
`aq-evidence run -- <cmd>`: guaranteed-unwrapped execution path (bypasses rtk/lean-ctx/output
hooks), content-addresses stdout/artifacts at creation, emits `{cmd, sha256, bytes, ts}` sidecar.
Governance protocols and the verifier path adopt it for all hash-bearing evidence.
**Accept**: wrapped-vs-unwrapped divergence test exists and alarms; pattern promoted to
`.agent/PROMOTED-BUG-PATTERNS.md`; C0.3-style bindings reproducible via `aq-evidence` alone.
**Lanes**: codex implements; opus verifies against recorded C0.3 hashes.

### VF-8 — Small-model lane-eligibility bench *(research; portfolio economics)*
Measure a 1–4B-class local model on factory task classes that currently burn the 35B slot
(triage, classification, tier claims, extraction, report generation). Output: evidence-backed,
expiring rows for the lane-eligibility registry demanded by the owner meta-prompt; go/no-go on a
model-portfolio slice next cycle. Runs in idle windows (APU contention budgeted).
**Accept**: per-class pass-rates with sample counts + confidence; registry rows with expiry;
recommendation with measured cost/latency deltas. No routing change this cycle.
**Lanes**: local + switchboard bench harness; antigravity research comparison; fable verdict.

### VF-9 — Intake contract: capture → triage → slate *(owner-approved 2026-07-13; protects trajectory)*
One door in for all new findings/ideas/requirements/features, with three stages under different
rules. **Capture** (always open, zero ceremony, never interrupts): new `intake.item` event type on
the existing a2a event log via `aq-event emit`, free text + provenance; projector-written
`INTAKE.md` projection — no new writer, service, or registry. Rule 11's mandatory-logging duty
extends to ideas/requirements through this funnel. **Triage** (batched at slice/cycle boundaries,
never mid-slice): local-model first pass (dedupe, suggested track binding against
`UNIFIED-PROGRAM-PLAN.md` §3, risk tier, priority, draft oracle) + orchestrator batch
confirmation. Dispositions: duplicate / reject-with-reason / park-with-review-date (auto-archive
on expiry, Rule 12) / accept. Acceptance requires a program-track binding (or an explicit program
amendment — owner decision) AND an oracle sketch; `memory/issues-backlog.md` becomes triage-fed.
**Scheduling**: cycle slates frozen at cycle open; mid-cycle arrivals go to intake only, except
items meeting the written **interrupt rubric** (active breakage of the running system, security
exposure, or a blocker on the in-flight slice — deterministic, ratified at the unified-program
round; an agent cannot argue its way into an interrupt).
**Accept**: capture demonstrated from ≥2 agents + operator; one real boundary triage executed with
local first pass; slate-freeze gate live in `aq-loop` (a non-rubric mid-cycle item provably
deferred to intake, not lost); `INTAKE.md` projector-written only; accepted rows carry track
binding + oracle sketch; park/expiry aging demonstrated.
**Lanes**: codex implements event type + projector + slate gate; local runs first-pass triage
(measured as a VF-8 task class); fable authors rubric + confirmation flow; antigravity
adversarially probes interrupt-rubric evasion.

## 5. Phasing & dependencies

```
VF-0  Ratification & reconciliation round (consensus ≥3/4; owner activation; PREPARED_ONLY→ACTIVE)
      — waits for L2B close or proven non-overlap
VF-1 + VF-7   (parallel; smallest; unblock everything)
VF-2 + VF-9   (VF-2 needs VF-1 tier field; VF-9 needs VF-1 oracle schema + rubric ratified at VF-0)
VF-3          (needs VF-1 oracles; delivers report≠record)
VF-4 + VF-5   (parallel; need VF-3 verifier path)
VF-6          (needs VF-5 ledger)
VF-8          (independent; idle windows; anytime after VF-0)
```

External dependencies: F2.5 wiring (aqos-v1 Beat 3.1) is a throughput dependency, not VF scope —
owner decides whether it precedes or parallels VF. Cycle 1B state spine may land mid-cycle; VF
artifacts are spine-compatible projections by design (§3).

## 6. Factory KPIs (baseline at VF-0, re-measured at cycle close, dashboard-rendered)

first-pass oracle yield per lane · escalation rate · rework rate · governance-overhead ratio ·
human interventions per slice · inference-free task share · cost + wall time per merged slice ·
intake→triage latency · mid-cycle interrupt rate · parked-item aging compliance.
Per the parity motto: a blank `--` on any of these is a bug.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Oracle gaming (implementer optimizes to the check) | oracles sealed by non-implementer lane; antigravity adversarial probes (VF-2/VF-3); anti-gaming HARD rule |
| VF becomes a third competing roadmap | §3 disposition table is a ratification blocker: every overlap gets an explicit absorbed/deferred/superseded verdict at VF-0 |
| Governance re-inflation (VF gates add weight instead of removing it) | governance-overhead ratio is a first-class KPI; VF-2 fast path must demonstrably beat the C0.3 baseline |
| APU contention (bench + eval replay vs. dev inference) | idle-window scheduling; parallel=1 respected; budgets in slice contracts |
| Schema drift vs. L1A/L2B contracts | VF-0 reconciliation snapshot; oracle/outcome fields land as extensions with contract-kernel review |
| Local lane over-tasked beyond envelope | slices decomposed to measured single-edit envelope; failures logged as training targets |

## 8. Out of scope (this cycle)

Durable-truth migration (Cycle 1B) · live routing mutation (Cycle 5) · new services/daemons/
stores · model training-pipeline changes · Nix service topology changes · frontend rebuild
(aqos-v1 WS6) · Rust (deferred indefinitely).

## 9. Ratification & activation protocol

1. VF-0 round `verified-factory` per the companion meta-prompt: all four lanes, own files, local
   mandatory with open aggregation, consensus ≥3/4.
2. Round output amends this PRD (including §3 dispositions, any slice re-scoping, and the exact
   VF-9 interrupt rubric + triage cadence text) and produces
   a PREPARED_ONLY implementation authorization with exact surface grants, subject-binding hashes
   (computed via the unwrapped path), and per-slice sealed oracles.
3. Explicit owner activation statement naming the authorization ID → implementation dispatch
   begins under the meta-prompt's per-slice loop.
4. Cycle close: KPI re-measurement, activation-gate attestations, reconciliation record, and an
   explicit `APPROVE`/`REQUEST_REVISION`/`BLOCKED` end-of-cycle verdict with the owner decisions
   needed next.
