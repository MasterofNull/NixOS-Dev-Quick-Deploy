# AQ-OS Unified Program Plan — One Trajectory, All Sources Bound

**Status:** CONSOLIDATION DRAFT — projection/index over the governing documents; itself
PREPARED_ONLY. Ratifying this plan = ratifying the disposition tables below, not new scope.
**Prepared:** 2026-07-13 by claude-fable-5 (analysis lane) at explicit owner request.
**Maintenance rule:** this file is a **projection, not an authority**. On any conflict, the source
document wins per the precedence order in §1. Update this file at every cycle transition; a stale
row here is a bug, not a license.

---

## 1. Document authority map (precedence order, highest first)

| # | Document | Role | Status (2026-07-13) |
|---|----------|------|---------------------|
| 1 | `OWNER-POLICY-RATIFICATION.md` (cycle0 dir) + explicit owner statements | Owner authority — activates everything below | standing |
| 2 | `docs/architecture/canonical-kernel-declaration.md` | Frozen kernel objects + `local-orchestrator` front door; changes need a named revision | frozen |
| 3 | `docs/architecture/aqos-cycle1-state-spine-adr.md` | Per-authority consolidation proposal; ten SPLIT_BRAIN rows | Proposed, NOT authorized |
| 4 | `.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md` | **Parent architecture candidate** — reconciles Fable + Codex corpora | REQUEST_REVISION, awaiting owner ratification |
| 5 | `.agent/PROJECT-LOCAL-AI-FACTORY-REFERENCE-ARCHITECTURE-PRD.md` | Ground-up target + Cycles 0–6 roadmap + delivery gates | trajectory doc; Cycle 1A executing under it |
| 6 | `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md` + L-series plans | Current implementation track (Cycle 1A / Foundation B1) | L1A+L2A landed; L2B-A in flight |
| 7 | `.agent/PROJECT-AQOS-CYCLE0-TRUTH-PRD.md` + `aqos-refoundation-cycle0/` | Cycle 0 record: evidence algebra, authority inventory, threat register, incidents | evidence integrated `c9fe3974`; exit adjudication pending |
| 8 | `.agent/PROJECT-AQOS-PRD.md` + `.agents/plans/aqos-v1/` | Fable AQ-OS v1: WS1–WS10, 7 beats, horizon/unknowns, command-center roadmap | never ratified standalone; **absorbed as product backlog** (see §4) |
| 9 | `.agent/PROJECT-VERIFIED-FACTORY-PRD.md` + companion meta-prompt | Cross-cutting verification/throughput layer (VF-1…VF-8) | PREPARED_ONLY, awaits ratification |
| 10 | `.agents/plans/epic-flat-collaborative-factory.md` + F1/F2/F3 briefs | Flat-factory operating model + foundation critiques | F1 done; F2 partial (F2.5 dormant); F3 unimplemented |
| — | Owner meta-prompts (`LOCAL-AI-FACTORY-NEXT-CYCLE…`, `VERIFIED-FACTORY-CYCLE…`, `AQOS_OWNER_NEXT_CYCLE…`) | Process constitutions for rounds | standing |

"AQ-OS versions" reconciled: there are **four** — Fable AQ-OS v1 (07-09), Codex Cycle-0 truth PRD
(07-10), Codex reference architecture (07-13), and the Codex–Fable synthesis (07-13). The synthesis
is the merge point; the other three remain source corpora, not competitors.

## 2. Program state ledger (what is DONE / LIVE — do not re-plan)

| Item | State | Evidence |
|------|-------|----------|
| F1 round state machine (`round.json`, wired into aq-collab-round) | DONE | epic F1; live rounds |
| F2 scheduler Phase A (scheduler/backpressure/model_tier code + tests) | BUILT, **DORMANT** (F2.5 wiring gap, standing HIGH) | issues-backlog |
| Closed learning loop (capture→correct→HITL→ingest→train→eval) guarded + observable | LIVE | ACTIVATION-AUDIT |
| Cycle 0: C0.1, C0.2 (+recovery), C0.3 authority/retirement ledger + read-only checker + projection | INTEGRATED | `c9fe3974` |
| Cycle-0 incident record: Opus evidence falsification + overwrite; quarantined artifacts | RECORDED | `C0.3-CLAUDE-EVIDENCE-INCIDENT-20260713.md`, evidence/rejected/ |
| L1A local-inference contract foundation (schemas, pure resolver, golden parity vectors) | DONE | `0c171504` |
| L2A canonical request/context/policy shadow kernel | DONE | `499e5a26` |
| a2a event log + PULSE/RESUME projector (`aq-event`) — files are projections now | LIVE (partial WS2/B3 delivery) | `.agents/events/a2a-events.jsonl` |
| Fable-parity behavior contract injected in payloads/profiles | LIVE (pending model-neutral rename, owner decision Q4) | FABLE-PARITY-CONTRACT |
| Qwen3-35B promoted primary local agent; measured envelope = bounded single-edit | MEASURED | memory |

**IN FLIGHT (do not collide):** L2B-A shadow transport kernel (Codex executing; ~14-file slice,
uncommitted worktree). L2B-B (payload normalization/adoption) queued behind it.

## 3. Unified track structure (the one spine)

The synthesis Foundations/Products and the reference-architecture Cycles are the same trajectory;
this table is the single naming bridge. Every other artifact maps INTO these tracks (§4).

| Track | = Ref-arch cycle | Content | Gate to start | Status |
|-------|------------------|---------|---------------|--------|
| **Foundation A** — Cycle-0 truth exit | Cycle 0 exit | Owner adjudicates target/transition-owner/deadline/rollback for all ten SPLIT_BRAIN/UNOWNED rows | owner session over `system-state-authorities.yaml` | **BLOCKING; pending owner** |
| **Foundation B1** — contract kernel + parity vectors | Cycle 1A | L-series: L1A ✅, L2A ✅, L2B-A ▶, L2B-B, then chat/batch parity in shadow | done (authorized) | EXECUTING |
| **Foundation B2** — one shadow state vertical | Cycle 1B | CAS + outbox/replay for ONE workflow-run authority; legacy stays authoritative | state-spine ADR adjudicated (owner decision Q2) | NOT AUTHORIZED |
| **Foundation B3** — projector + canon-compiler shadow | Cycle 1B/2 seam | Extend `aq-event` projector to one dashboard surface; canon compiler (docs/clients/cards; never runtime authority) | B1 contracts stable | partial (aq-event live) |
| **Foundation C** — identity, leases, execution cells | Cycle 2 | Principal envelopes, CapabilityLease, effect brokers, network profiles, cells; absorbs F3 + WS9 core | B1 + ratified security model (Q3) | NOT STARTED |
| **Product D** — inference/client live convergence | Cycle 3 | Switchboard sole gateway; delegate-to-local/aq-chat as coordinator clients; **global scheduler activation closes F2.5 HIGH**; route/profile registry consolidation | B1 parity fixtures + C boundaries | NOT STARTED |
| **Product E** — evaluation & learning factory | Cycles 4–5 | Dataset/scorer/prompt registries, sealed answers, certified scorers, counterfactual replay, promotion ledger, small-model admission; absorbs WS8, aq-eval + inference-bench PRDs, VF-4/5/8 | B2 evidence store + C integrity | NOT STARTED |
| **Product F** — one CLI + command center | Cycle 6 (partial) | `aq <noun> <verb>` + shims; OTel traces; SLO burn; typed console (Fleet/Runs/Evals/Approvals/…); absorbs WS4/WS5/WS6 + ws6-command-center-roadmap | authoritative telemetry from C/D | NOT STARTED |
| **Product G** — edge, release, retirement | Cycle 6 | Hardware-class probes, install profiles, restore/upgrade drills, semver v1.0, legacy retirement after 2 clean cycles; absorbs WS10 + WS7 drills + edge research + HORIZON-UNKNOWNS | everything prior | NOT STARTED |
| **Track V (cross-cutting)** — Verified Factory throughput layer | feeds 4–5; gates all | VF-1 oracle-required dispatch, VF-2 risk-tiered gates + governance-overhead KPI, VF-3 report≠record verifier (interim until C/E make it structural), VF-6 distillation ratchet, VF-7 `aq-evidence` unwrapped path, VF-9 intake contract (capture→triage→frozen slate + interrupt rubric; owner-approved 2026-07-13) | VF-0 round after L2B-A close | PREPARED_ONLY |

Track V is explicitly **interim process armor**: VF-3's verifier gate is retired into Cycle-2
attestations and Cycle-4 certified scorers when those land; VF-4/5 artifacts are built
Cycle-4/5-compatible so they migrate, not duplicate. This satisfies the standing rejection
criterion "no second parallel harness."

## 4. Traceability matrix — nothing lost, skipped, or forgotten

Dispositions: **GOVERNS** (still the SSOT for its scope) · **ABSORBED→x** (content lives on inside
track x; original kept as source) · **FEEDS→x** (input evidence) · **SUPERSEDED** (kept as record
only) · **STANDING** (independent of this program).

| Source artifact | Disposition |
|---|---|
| AQ-OS v1 PRD §2 deficits D1–D12 | FEEDS→ all tracks (D1→C0/B, D2→F, D3→B2/B3 ✅partial, D4→B1, D5→B3 canon, D6→B1/D, D7→G+V, D8→F, D9→D (F2.5), D10→F, D11→B2, D12→G) |
| AQ-OS v1 WS1 contracts+canon | ABSORBED→B1 (contracts) + B3 (canon compiler, amended per synthesis §3.2: never runtime authority) |
| AQ-OS v1 WS2 event bus/A2A v2 | ABSORBED→B2/B3; "Redis Streams as authority" resolved AGAINST (synthesis §5); aq-event projector = first delivered increment |
| AQ-OS v1 WS3 kernel + F2.5 | ABSORBED→ kernel work in B/C (modular monolith per synthesis §4.1); **F2.5 wiring→Product D**; capability lifecycle→C + capability-intake PRD (STANDING) |
| AQ-OS v1 WS4 one CLI | ABSORBED→F |
| AQ-OS v1 WS5 observability/SLOs | ABSORBED→F (OTel GenAI conventions per ref-arch §17) |
| AQ-OS v1 WS6 console + `ws6-command-center-roadmap.md` | ABSORBED→F ("build after authoritative telemetry" — synthesis §3.1) |
| AQ-OS v1 WS7 data plane/memory v2 | ABSORBED→B2 (store) + E (lineage) + G (backup/restore drills) |
| AQ-OS v1 WS8 RSI industrialization | ABSORBED→E; near-term seed = VF-4 golden-task bank |
| AQ-OS v1 WS9 security/supply chain | ABSORBED→C (leases/threat model) + G (SBOM/signing/release) + THREAT-REGISTER (GOVERNS) |
| AQ-OS v1 WS10 release engineering | ABSORBED→G |
| aqos-v1 Beats 0–7 + DELEGATION.md | SUPERSEDED as sequence (Beat-0 round never dispatched; ratification folded into §6 round); slice content preserved via WS rows above |
| aqos-v1 `HORIZON-UNKNOWNS.md`, `STACKING-AUDIT.md`, `GOD-TIER-PROMPTS.md`, ws-edge | FEEDS→G (edge/blind-spot program, synthesis §3.3) + round prompt library |
| `.agent/FABLE-PARITY-CONTRACT.md` | GOVERNS until owner decision Q4 converts it to model-neutral versioned canon policy (then ABSORBED→B3 canon) |
| `.agent/FABLE-5-ANALYSIS-CHARTER.md` | GOVERNS (analysis-before-delegation retained, synthesis §3.4; lane assignment becomes measured, not entitled) |
| Cycle-0 truth PRD + CONSOLIDATED-PLAN + STATE-CONTRACT + EVIDENCE-ALGEBRA + EVIDENCE-MANIFEST | GOVERNS Cycle-0 record; exit via Foundation A |
| `CURRENT-AUTHORITY-INVENTORY.md` + `config/system-state-authorities.yaml` + checker + `state-authorities-latest.json` | GOVERNS the ten authority rows; input to Foundation A adjudication and B2 vertical selection |
| `THREAT-REGISTER.md` | GOVERNS; expands in C (Cycle-2 adversarial matrix) |
| C0.3 incident + recovery docs (2026-07-13) | STANDING evidence; regression fixture requirement in VF-3; design lesson synthesis §11 |
| Ref-arch PRD §§1–13 (topology, contracts, cells, eval factory, operator plane) | GOVERNS target architecture under the synthesis umbrella |
| Ref-arch §14 Cycles 0–6 + §15 delivery gates + §16 success measures + §17 research refs | GOVERNS roadmap/gates/KPIs — §3 table above is its projection |
| Local-inference contract PRD + L1A/L2A/L2B-A plans | GOVERNS Foundation B1 execution |
| VF PRD (all 9 slices) + VF meta-prompt | GOVERNS Track V; VF-4→E(Cycle 4), VF-5→E(Cycle 5 report-only precursor), VF-8→E(Cycle 5 small-model admission evidence), VF-9 intake funnel feeds every track's slate and makes `issues-backlog.md` triage-fed |
| Epic flat-collaborative-factory + f1/f2/f3 briefs + impl plans + consensus dirs | F1 DONE; F2 GOVERNS scheduler design (activation in D); F3 ABSORBED→C; epic vision FEEDS→ all |
| `EFFECTIVENESS-CENTERED-SYSTEM-IMPROVEMENT-PRD.md`, OBSERVABILITY-PARITY-*, usability-parity, context-sandbox-parity, aq-eval/aq-inference-bench PRDs, capability-backlog, repo-discovery | STANDING satellite PRDs — re-based onto tracks when their next slice is picked (aq-eval/bench → E; observability/usability parity → F) |
| `.agent/PROJECT-CHECK-KERNEL-PRD.md` (CK, 2026-07-13) + Antigravity ARE plan | GOVERNS check/lint consolidation under Track V + B1: one CheckSpec registry/runner absorbing tier0's 19 gates, 99 registry checks, 80-script governance corpus, Phase-0 dual registration, VF oracles; CK-1 = amended ARE plan; awaiting `check-kernel` round |
| Domain PRDs (OSINT, trading, GIS, embedded, mobile, security-systems, scientific, T3MP3ST intake…) | STANDING — out of program scope, unaffected |
| Rust refactor | DEFERRED INDEFINITELY (standing order; do not propose) |

## 5. Loose-thread register (nothing silently dropped)

1. **F2.5 dormant HIGH** — scheduler built, unwired; closes in Product D; remains in issues-backlog until then.
2. **Cycle-0 exit adjudication** — ten rows need owner target/owner/deadline/rollback (Foundation A). Blocks B2.
3. **State-spine decision** — per-authority ADR vs Postgres/outbox+CAS hypothesis (owner decision Q2). Blocks B2.
4. **aqos-v1 Beat-0 round** — never dispatched; folded into the §6 consolidated round (this is the recorded disposition, not a skip).
5. **Agent-parity 5-file follow-up** (from opus RESUME snapshot) — due with next canonical change; mechanized permanently by B3 canon compiler.
6. **Pending operator restarts** — dashboard restart (scorecard p95 projection), switchboard restart (fable-parity key file). Batch at next end-of-cycle.
7. **Local-lane repair (Cycle-1 gate)** — queued in opus RESUME; fold into VF-8 / Product-D lane-eligibility work.
8. **Quarantined evidence** — `evidence/rejected/c0.3-antigravity-unauthorized-collector.py{,.gz}` retained as incident record; never reused as acceptance evidence.
9. **Uncommitted worktree** — L2B-A slice files (Codex, in flight) + this consolidation's three docs (VF PRD, VF meta-prompt, this plan); commit at slice close per discipline.
10. **Monitors** — ragas faithfulness 0.6 (E-track fixes scorer quality); opencode-undici-bun-crash (low, backlog).
11. **Lane eligibility** — Gemini/Antigravity implementation-INELIGIBLE until measured promotion (owner decision Q5); enforced in every track's delegation.

## 6. Consolidated owner decision queue (deduplicated from synthesis §10 + ref-arch §18 + VF §9)

| Q | Decision | Unblocks |
|---|----------|----------|
| Q1 | Ratify the **synthesis** as parent architecture (with this plan's §3/§4 as its execution projection) | everything below |
| Q2 | State spine: per-authority ADR vs Postgres/outbox+CAS hypothesis (may defer to after B2 evidence) | Foundation B2 |
| Q3 | Security model: principal attestations + CapabilityLease, no fail-open modes; + eight network profiles (connected zero trust) | Foundation C |
| Q4 | Fable behavior contract → model-neutral versioned canon policy | B3 canon migration |
| Q5 | Measured, expiring **lane-eligibility registry** (roles stay model-neutral) | all delegation; VF-8 feeds it |
| Q6 | Kernel front door: keep `local-orchestrator` declaration or issue named revision toward `aq` gateway | Product F CLI |
| Q7 | Eval factory as universal promotion gate (models, prompts, profiles, policies, tools, scorers, datasets) | Product E |
| Q8 | Adjudicate the ten Cycle-0 authority rows (Foundation A exit) | B2 vertical selection |
| Q9 | Activate VF (Track V) after its VF-0 round — incl. ratifying the VF-9 interrupt rubric + triage cadence (slice itself owner-approved 2026-07-13) | oracle/tier/evidence/intake gates |

## 7. Recommended sequence from today

```
NOW        L2B-A finishes (Codex, in flight) → L2B-B payload slice
NEXT ROUND ONE consolidated ratification round `unified-program`:
           synthesis (Q1) + decision queue Q2–Q9 + VF-0 critique — replaces the three
           separately-queued rounds (aqos-v1 Beat 0, synthesis ratification, VF-0).
           All four lanes, own files, local mandatory, aggregation open.
THEN       Foundation A owner adjudication session (Q8; can precede or follow the round)
PARALLEL   Track V fast slices under activated VF authorization: VF-7 (aq-evidence) + VF-1
           (oracle dispatch) — T0-class, no authority moves; VF-2 tiers + VF-9 intake funnel next
THEN       Foundation B2 (one shadow vertical, post-Q2) ‖ B1 completion (chat/batch parity)
THEN       Foundation C (leases/cells) → Product D (convergence + F2.5 close) →
           Product E (eval factory, folding VF-4/5/8) → Product F (CLI+console) → Product G (release)
CADENCE    one foundation track in-flight at a time; Track V slices may interleave (T0/T1 only);
           every slice under ref-arch §15 delivery gates + Activation Gate (Rule 15)
```

## 8. Program-level KPIs (union — measured at every cycle close)

Ref-arch §16 success measures (authority/lease/eval coverage, terminal uniqueness, projection
discipline, restore drills) + AQ-OS v1 §9 product metrics (install→first-delegation <1h, diagnose
<2min, 0 hand-synced files, 1 CLI, 0 dormant features) + VF §6 throughput metrics (first-pass
oracle yield, escalation/rework rates, **governance-overhead ratio**, inference-free share, human
interventions per slice, intake→triage latency, mid-cycle interrupt rate). A blank `--` on any
adopted KPI is a bug.
