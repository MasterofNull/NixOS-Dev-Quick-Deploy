# Claude Contribution — Round 'aqos-system1-selfcompact-v1'

**Agent:** Claude Opus 4.8 (coordinator lane; this lane was `pending` — completed on coordinator handoff 2026-09-23)
**Reference:** `.agents/prompts/AQOS_UNIFIED_SYSTEM1_SELF_COMPACT_META_PROMPT.md`
**Status:** Expert contribution + synthesis input. Complements Antigravity's `antigravity.md` (ratify-with-constraints); does not re-derive its WS1-6 amendments/slices/DoD, which I concur with.

## 1. Verdict
RATIFY, adopting Antigravity's constraints (APU 400MB-RSS CPU-only ceiling; fail-closed security; asymmetric local/remote context thresholds). I add five refinements grounded in the harness's actual patterns and the pieces landed this cycle.

## 2. Round quality note (Rule 11)
This round is thin and should be treated as such by the synthesis: `local.md` is a BLOCKED non-contribution (the dispatch did not inline the meta-prompt, so local reported "missing context" — a real round-dispatch bug: `aq-collab-round` must inline the reference doc or the lane can't act), Codex's lane shows `submitted` with no materialized file, and `round.json.contributions` is `{}`. Substantive inputs = Antigravity + this Claude lane. Quorum-of-2 is met on substance; record the local-dispatch bug as a follow-up so future rounds inline the prompt.

## 3. Claude-lane refinements (distinct, not in antigravity.md)

### R1 — Fail-OPEN to System 2 for performance functions; fail-CLOSED only for security
Antigravity's fail-closed rule is correct for function [4] shell-safety. For the other five functions (routing, RAG, memory, telemetry, review-triage) the governing principle is **fail-OPEN to the existing System-2 path**: System 1 is an acceleration layer, never a hard dependency. If `system1d` is down / socket unreachable / confidence below threshold, each caller falls back to today's regex/LLM/cosine path and proceeds — never blocks. This mirrors the harness patterns just landed: router-health fail-safe-to-healthy (`bdb7fa63`), capability-manifest declare-unavailable (`7a25ce46`), FT-5 readiness `TRANSPORT_UNAVAILABLE`-is-informational. Net: security = fail-closed to the safe gate; performance = fail-open to System 2.

### R2 — Declare system1d as a shared-engine CAPABILITY, not an assumed dependency
`system1d` is itself a shared-factory-engine capability. Declare it in the capability manifest (`7a25ce46` pattern): `state ∈ {available, unavailable, unauthorized}`, resolved from the live socket. A project/agent whose host lacks `system1d` gets a typed `unavailable` (→ R1 fallback), never a dead call. This keeps the System-1 layer portable across deployed projects consistent with the shared-engine contract.

### R3 — System-1 routing must feed the health filter, never bypass it
Function [1] `choice: recommended_profile` and function [6] `choice: cheapest_eligible_agent` (Rule 17) must pass their pick through the health-aware router just landed (`bdb7fa63`: `_health_filter` / `lane_health` over `.agents/delegation/.<lane>-down` + `.codex-quota-cooldown`). System 1 proposes; the health filter disposes — so System 1 can never recommend a lane that is flagged-down/in-cooldown (the exact "recommends dead qwen" defect we just fixed). System-1 accelerates the *choice*; it does not replace the *health gate*.

### R4 — Self-compaction reuses the existing anchors + aq-event, not a parallel mechanism
The harness already has the compaction anchor Pillar II describes: `RESUME.json` (Rule 8b — its `resume_hint` IS the authoritative "Note-to-Self") + `PULSE.log` (Rule 8a) + the `aq-event` projection SSOT (Rule 20). `self_compact` must EMIT an `aq-event` (`resume`/`pulse`) that projects into RESUME.json/PULSE — never hand-write them (they are projections; hand-editing is anti-gaming). The `context.compacted` Redis event Antigravity proposes is the durable spine; the RESUME/PULSE update is its projection. This makes self-compaction a first-class citizen of the event model we already run, not a new state store.

### R5 — Shadow-first adoption per function (minimal-code, Rule 20b)
Each of Antigravity's Slices 2/4 should land System 1 in SHADOW alongside the live System-2 path first: run both, log the System-1 verdict + the System-2 outcome to `agent.decision.system1`, measure agreement/latency, and cut over per-function only after shadow evidence clears a bar — matching the harness's established shadow-kernel pattern (L2B-B, Foundation C landed shadow-first, default-off). This de-risks the six-function replacement and gives the DoD "real-world validated" dimension its evidence.

## 4. Concurrence
I concur with Antigravity's WS1-6 amendments, the 5 phased slices, and the 6-point DoD, with R1-R5 folded in. Synthesis target: `PRD-AMENDMENT-AQOS-SYSTEM1-SELFCOMPACT.md` amending `.agent/PROJECT-AQOS-PRD.md`, with a `tracker.json` for the plan (Rule 20).
