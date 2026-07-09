---
title: RSI Readiness — Trust Infrastructure for Local Agentic Self-Improvement
doc_type: prd
id: rsi-readiness
status: draft
owner: claude-fable-5
last_updated: 2026-07-09
---

# PRD — RSI Readiness: earn trust before autonomy

## Thesis (grounded in the 2026-07-09 assessment)

The harness's self-improvement *machinery* is built and now guarded (closed loop,
event bus, tracing, contention-aware evals, cascade, activation gate). The
*machinery is not the blocker*. Two things are:

1. **The local model cannot yet be trusted to execute** — it claimed file writes
   it never performed (twice this session; the unbacked-write guard caught it).
   Its measured envelope is bounded single-edit; multi-step agentic execution
   fails.
2. **The reward signal is corruptible** — the eval loop scored a false 0/12
   under slot contention and nearly recorded it as a regression. A self-improving
   system optimizing a bad metric improves toward the wrong thing.

**Conclusion**: agentic self-improvement works TODAY only as a hybrid (local
drafts → remote corrects → human gates). Granting autonomy requires *trust
infrastructure* first. This PRD builds exactly that, and proves — with measured
evidence, not hope — whether the local model can bootstrap.

**Non-goal**: granting the loop autonomy in this cycle. The exit is a
SHADOW-MODE loop whose proposals are measured against a trustworthy eval harness,
human-gated throughout. Autonomy is a later, evidence-earned decision.

## Workstreams (each an activation-gated deliverable)

### R1 — Trustworthy eval harness (PRIORITY 1; everything depends on this)
Nothing downstream is safe until the reward signal is one we'd stake a decision on.
- R1.1 Golden task sets per capability (coding, tool-use/write-discipline, structured
  output, NixOS-domain, retrieval) — versioned, reviewed, with expected outputs.
- R1.2 Robust scoring: beyond keyword coverage — exec-based checks where possible
  (does the code run? does the edit apply? does the JSON parse?), rubric scoring,
  and a confidence/abstain path (never score infra noise as a capability miss —
  extend the prompt-5 contention/degraded_infra classification).
- R1.3 Eval integrity gates: shadow/canary datasets to detect scorer gaming;
  regression only on REAL evals (already partially shipped); scorecards persisted
  and diffable.
- Accept: two independent runs on the same model produce scores within a defined
  tolerance; a deliberately-broken model scores measurably worse; infra failures
  never register as capability regressions. Reviewer signs off that the signal is
  trustworthy.

### R2 — Local write-execution reliability (the #1 capability blocker)
- R2.1 Draft-only default: local is constrained to DRAFT; execution (file writes,
  commits) goes through the cascade/remote or a verified-apply step — never trust
  local narration of side-effects (generalize the unbacked-write guard into a
  contract). 
- R2.2 Targeted fine-tune: make `write_file`/tool-calling discipline the FIRST
  training target — the closed loop already captures this exact failure. Curate
  those captures, correct via teacher, HITL-approve, train, and eval R2 against a
  tool-calling golden set (R1).
- R2.3 Structured tool-calling enforcement where the runtime allows (schema-forced).
- Accept: local tool-call success rate on the R1 tool-use golden set improves
  measurably post-train; unbacked-write claims → 0 on the golden set; the
  draft-only contract is enforced in dispatch.

### R3 — SMALL_RESIDENT deploy + cascade/verifier activation
- R3.1 Execute the hardware-driven rebudget (model_budget verdict:
  deploy_small_resident_now at Q4_K_M) — Nix declaration + model fetch + wiring
  `tiers.local` and the SMALL_RESIDENT concurrency lane into dispatch.
- R3.2 Back cascade's `score_confidence()` with the small model as a verifier
  (behind the existing interface); route the 5 SMALL_RESIDENT task classes off
  the 35B slot.
- Accept: SMALL_RESIDENT serves the cheap task classes at measured >10× tok/s vs
  the 35B; the big slot is freed for parallel eval; cascade escalation decisions
  use the verifier model; bench delta published.

### R4 — Shadow-mode RSI loop + proposal efficacy measurement
- R4.1 Run the full loop in SHADOW: capture → correct → propose, but NO change is
  applied — proposals are logged with the eval delta they WOULD produce.
- R4.2 Efficacy ledger: for every proposal, measure whether applying it (in a
  sandbox) actually raises the R1 eval score. Accumulate weeks of data.
- R4.3 Answer the real question with evidence: "do the loop's proposals improve
  anything?" Publish the efficacy rate per capability.
- Accept: N weeks of shadow proposals with measured sandbox eval deltas; a
  go/no-go recommendation on partial autonomy backed by data, not hope.

### R5 — End-to-end trace seeding + observability compounding
- R5.1 Auto-seed `AQ_TRACE_ID` at every CLI/loop entrypoint so every run is
  traced (the primitive is live, opt-in today).
- R5.2 Span the switchboard + tool layers; wire the OTLP export hook to the
  already-running ai-tempo/ai-otel-collector so traces land in a real backend.
- R5.3 The eval/loop runs become fully trace-diagnosable (compounds R1/R4).
- Accept: every delegation and loop run carries a trace id; a failed eval is
  diagnosable from its trace alone in the live dashboard; Tempo shows harness traces.

### R6 — Flagship self-improvement application (proves the whole stack)
- R6.1 "The harness maintains its own issues-backlog": triage OPEN issues, draft
  fixes via the cascade (local draft → remote polish), eval the fix against R1,
  and PROPOSE a change (human-gated) — end to end, trace-linked, on the event bus.
- Accept: one real issues-backlog item taken from triage → drafted fix → eval →
  human-gated proposal, entirely through the harness, with the trace as evidence.

### R7 — Multi-agent coordination safety (R-slice work formalization)
Concurrent agents collide on shared repo state. Observed this session: a second
agent's git operations UNSTAGED files mid-commit; malformed PULSE filenames from
racing appends; the RESUME clobber class (partly addressed by the event bus, but
agents still write files directly during migration). Self-improvement means MORE
concurrent agents, so this must be formalized before autonomy — an autonomous
loop that corrupts the shared index or another agent's commit is a hard failure.
- R7.1 Serialize privileged repo mutations: a git/index lock (or per-agent git
  worktrees, isolation: worktree) so no two agents stage/commit into the same
  index simultaneously; a commit queue with per-agent attribution.
- R7.2 Complete the event-bus migration (WS2 follow-up): agents EMIT events;
  PULSE.log/RESUME.json become projector-only writes (no direct agent writes),
  with the drift/compatibility gate from the aqos-v1 codex amendment enforced.
- R7.3 Atomic, race-safe append primitives for any remaining shared logs
  (O_APPEND leading-newline pattern from the event log; never `printf >>` with
  unescaped payloads — the malformed-filename bug).
- R7.4 A coordination contract in WORKFLOW-CANON: which mutations require the
  lock, how agents claim/release, how conflicts surface (not silently clobber).
- Accept: two agents committing concurrently never corrupt each other's index or
  staging (reproduced under test); zero direct agent writes to PULSE/RESUME on
  the migrated path; a documented + enforced coordination contract. This is the
  substrate that makes R4 (more concurrent shadow agents) and R6 safe.

## Cross-cutting requirements (all workstreams)
- Every deliverable: PRD gate → wire → live-test → tier0 → activation attestation
  (integrated+ON+validated+observable+intervenable) → verbose commit → PULSE/RESUME.
- No autonomy granted; human gates everywhere; shadow before live.
- Issues found → issues-backlog (Rule 11). Archive-never-delete (Rule 12). Nix
  declaration same-cycle as any runtime change (Rule 13).
- Every agent every phase (never-skip-local): local failures on these tasks are
  themselves R2 training data.

## Sequencing
R1 first (unblocks all). R2 + R3 in parallel (independent; R3 gives R2 a verifier).
R5 + R7 anytime (additive substrate — R7 should land early since it protects all
concurrent slice work). R4 after R1 (needs the trustworthy signal) AND after R7
(needs safe concurrency). R6 last (exercises everything). R4's efficacy data gates
any future autonomy PRD.

## Success metric (cycle exit)
A trustworthy eval harness (R1 signed off), local write-reliability measurably
improved (R2), SMALL_RESIDENT live and freeing the slot (R3), the loop running in
shadow with measured proposal efficacy (R4), every run traced (R5), and ONE real
self-improvement executed end-to-end under human gate (R6). Outcome: an
evidence-based answer to "is the local stack ready for autonomous self-improvement?"
— not a claim.

---
*Ratify via round `rsi-readiness` (see .agents/plans/rsi-readiness/ROUND-PROMPT.md).*
