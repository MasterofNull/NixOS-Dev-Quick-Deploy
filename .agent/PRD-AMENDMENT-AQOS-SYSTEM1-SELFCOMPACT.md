# PRD Amendment — AQ-OS v1: System-1 Decision Plane + Autonomous Self-Compaction

status: **proposed (round-synthesized, pending independent review + owner activation)**
amends: `.agent/PROJECT-AQOS-PRD.md` (AQ-OS v1)
source round: `.agents/plans/aqos-system1-selfcompact-v1/` (round `aqos-system1-selfcompact-v1`)
meta-prompt: `.agents/prompts/AQOS_UNIFIED_SYSTEM1_SELF_COMPACT_META_PROMPT.md`
synthesized by: Claude Opus 4.8 (coordinator) · 2026-09-23
lane inputs folded: Antigravity (`antigravity.md`, RATIFIED-WITH-CONSTRAINTS) + Claude (`claude.md`, R1–R5) · **Codex + local lanes did not materialize substantive input this round — see §7**

---

## 0. Amendment scope (what this changes in the PRD)

This amendment adds a **System-1 Decision Plane** and an **Autonomous Self-Compaction**
capability to AQ-OS v1. It does not replace any existing plane; it inserts a fast,
calibrated, sub-30ms judgment layer in front of high-frequency operational decisions and
gives agents provider-independent control over their own context lifecycle.

It maps onto the PRD's existing deficits and workstreams — it is not a new program:
- **D1** (hybrid-coordinator god-service) — offloads routine judgments off the 35B LLM path and out of the coordinator's regex tangle.
- **D3** (file-based A2A state; RESUME/PULSE clobber, no atomicity) — self-compaction rides the event spine; RESUME/PULSE stay **projections**, never hand-written.
- **D4** (heuristic/config brittleness) — replaces brittle regex/threshold heuristics with calibrated, versioned, schema-typed decisions.
- **D8** (fragmented observability) — every System-1 decision + every compaction is an emitted event on the trace spine.

Governing amendment workstreams below are numbered **AW1–AW6** to avoid collision with
the PRD's existing WS1–WS6; each names the PRD workstream it extends.

---

## 1. Two pillars

**Pillar I — System-1 Decision Plane.** A dedicated CPU-only microservice (`system1d`)
serving calibrated small-model verdicts (`noul` yes/no, `choice` enum, `score` scalar) in
sub-30ms for six high-frequency functions: [1] ingress routing / profile selection,
[2] RAG relevance re-ranking, [3] memory supersession classification, [4] shell-safety
pre-screen, [5] telemetry/health triage, [6] cheapest-eligible reviewer/agent routing
(Rule 17). Candidate weights: `rlcd-modernbert-151m` (preferred, ~250MB INT8) with
`wfzyx/von` (395M) only if quantized RSS stays under the safety margin.

**Pillar II — Autonomous Self-Compaction.** An agent-controlled context lifecycle: a
per-turn token-budget telemetry envelope, a first-class `self_compact` tool, and a 3-tier
threshold ladder (Notice → Warning → Force). At Force, non-compaction tool calls are
intercepted so the agent must write a structured hand-off anchor before its context is
rolled over — replacing blunt provider-side auto-compaction and RESUME.json clobbering.

---

## 2. Grounded constraints (adopted from Antigravity, RATIFIED-WITH-CONSTRAINTS)

These are **hard** design constraints, not preferences:

**C-A — APU memory ceiling.** Renoir host = 27GB RAM; Qwen3-35B already commits ~23.5GB
(22.5 model / 1.0 KV / 3.0 OS) leaving ~0.5–1.0GB. Therefore `system1d`:
- MUST be **CPU-only** (ONNX Runtime AVX2 / native runtime) — no APU VRAM, no GPU layers (the 12 offload layers stay reserved for `llama-server`).
- MUST carry a hard **400MB RSS ceiling** (enforced, observable).
- prefers `rlcd-modernbert-151m` (~250MB INT8); `wfzyx/von` only if a quant benchmark proves RSS < 800MB.

**C-B — Fail-closed for security; fail-OPEN to System-2 for performance (Claude R1).**
System-1 is an **acceleration filter, never an authority bypass**:
- Function [4] shell-safety is **fail-CLOSED**: regex blacklists for catastrophic commands (`rm -rf /`, `mkfs`, raw block-device writes) stay hardcoded and non-bypassable; System-1 confidence < 0.90 on `is_destructive` → fall through to the existing Tier-0 / operator gate. System-1 can only *accelerate an allow it already agrees is safe*, never *widen* what the existing gate permits.
- Functions [1][2][3][5][6] are **fail-OPEN to System-2**: if `system1d` is down / socket unreachable / confidence below threshold, the caller falls back to today's regex/LLM/cosine path and proceeds — never blocks.

**C-C — Asymmetric context thresholds (per-model, parameterized).** The 3-tier ladder is
scaled to each model's context window, never a uniform constant:
- **Remote (Claude/Codex, ~200k):** Notice 100k (50%) · Warning 150k (75%) · Force 180k (90%).
- **Local (Qwen3-35B, 32k):** Notice 16k (50%) · Warning 24k (75%, ~4k to finish the micro-slice) · Force 28k (~87.5%, locks tools with ~4k left to write `note_to_self`).

---

## 3. Claude-lane refinements folded in (R1–R5)

- **R1 — dual fail mode** (folded into C-B above): security fail-closed, performance fail-open-to-System-2.
- **R2 — system1d is a declared shared-engine capability**, resolved from its live socket (`available|unavailable|unauthorized`) via the capability-manifest pattern (`7a25ce46`). A host without `system1d` gets a typed `unavailable` → R1 fallback, never a dead call. Keeps the plane portable across deployed projects.
- **R3 — System-1 routing feeds the health filter, never bypasses it.** Functions [1] and [6] must pass their pick through the health-aware router (`bdb7fa63`: `lane_health` over `.agents/delegation/.<lane>-down` + `.codex-quota-cooldown`). System-1 *proposes* the profile/agent; the health filter *disposes*, so System-1 can never recommend a flagged-down/in-cooldown lane (the "recommends dead qwen" defect we already fixed).
- **R4 — self-compaction reuses the existing anchors via the event spine.** `self_compact` EMITS an `aq-event` (`agent.context.compacted`, carrying the unedited `note_to_self` + pre/post token counts); RESUME.json (`resume_hint` = the "Note-to-Self") and PULSE.log update as **projections** of that event, never hand-written (Rule 20 / anti-gaming). This makes compaction a first-class citizen of the event model already in use, not a parallel state store — directly retiring the D3 clobber class.
- **R5 — shadow-first adoption per function.** Each function lands in **shadow** first: run System-1 and the live System-2 path together, log both to `agent.decision.system1`, measure agreement + latency, and cut over per-function only after shadow evidence clears a bar — matching the harness's established shadow-kernel pattern (L2B-B, Foundation C landed shadow-first, default-off). Supplies the DoD "real-world validated" evidence.

---

## 3A. Review dispositions folded (Antigravity advisory 2026-09-23 — RATIFY-WITH-CHANGES)

Independent advisory review (`system1-amendment-antigravity-advisory-20260923.md`) audited all three
constraints PASS and R1–R5 sound. Four non-blocking additions folded here, to be honored in the named slices:
- **F1 — IPC socket timeout contract (AW1/S1):** clients use an explicit **50ms** `system1d` socket timeout; on
  timeout the client immediately takes the R1 fail-open path to System-2 and logs a latency warning to
  `agent.decision.system1`. (system1d serves ~6 subsystems; bound queueing.)
- **F2 — declarative model-weight provenance (AW1/S1):** `system1.nix` must provision `rlcd-modernbert-151m`
  purely — either a fixed-output derivation (`pkgs.fetchurl` + pinned SHA-256 in `nix/pkgs/models/system1.nix`)
  or a deployment-managed model dir (e.g. `/var/lib/models/system1/`). No runtime `huggingface-cli download`.
- **F3 — Force-interception feedback payload (AW4/S3):** the Tier-3 typed error MUST carry an explicit
  instruction telling the model to invoke `self_compact` (with the four required fields), e.g.
  `{"error":"context_budget_exceeded","tokens_consumed":N,"limit":M,"instruction":"...invoke self_compact..."}`
  — otherwise small/local models re-attempt the blocked call until hard exhaustion.
- **F4 — quantitative shadow→cutover thresholds (AW5/S2/S4):** cutover requires: routing ≥95% agreement vs
  gold intent bench; RAG 0% false-rejection of ground-truth chunks + P95 <25ms; memory 100% supersession
  suite; shell-safety 100% agreement with baseline on destructive flags (0% false negatives).
- **Non-widening invariant (S2, made explicit):** `PermittedCommands(System1) ⊆ PermittedCommands(Baseline)`;
  the set-difference is ∅ — System-1 is a pure subset filter with zero authority to override baseline blacklists.

## 4. Amendment workstreams (AW1–AW6)

**AW1 — system1d microservice + kernel offload** *(extends PRD WS3 kernel extraction; D1)*
- `nix/modules/services/system1.nix` → `system1d.service`, CPU-only, 400MB RSS ceiling.
- IPC: UNIX domain socket `/run/nixos-ai-stack/system1.sock` (`mode=0660`, `user=ai-stack`); no TCP.
- AppArmor: read-only `/nix/store` weights; `deny network inet`/`inet6`.
- Declared in the capability manifest (R2); `aq-qa` health check; `AQ_SYSTEM1_DISABLE=1` kill switch.

**AW2 — contracts & schemas** *(extends PRD WS1 contracts/canon; D4/D6)*
- `contracts/schemas/system1/decision-v1.json` (`noul`/`choice`/`score`, confidence, model-id, latency).
- `contracts/schemas/agent-tools/self-compact-v1.json` (requires `note_to_self`, `active_hypotheses`, `completed_milestones`, `next_exact_command`).
- `contracts/schemas/events/context-compacted-v1.json`.

**AW3 — event spine & A2A state** *(extends PRD WS2 event bus; D3/D11)*
- New event types: `agent.decision.system1` (audit of all fast-path verdicts + shadow comparisons) and `agent.context.compacted` (authoritative compaction event).
- `self_compact` emits the compaction event; RESUME.json + PULSE.log are projected from it (R4), atomically — never hand-edited.

**AW4 — context-budget controller + self_compact tool** *(extends PRD WS1/WS3; D3)*
- `ai-stack/mcp-servers/hybrid-coordinator/core/context_budget_controller.py`: injects live token telemetry into every switchboard turn envelope; at Tier-3 Force, intercepts non-compaction tool calls with a typed error.
- `self_compact` registered in `config/first-party-tools.json` + `tooling_manifest.py` (same first-party discipline as `aq-tool`).

**AW5 — active RAG & memory modernization** *(extends PRD WS3 coordinator decomposition; D1)*
- `rag_augmentor.py`: replace raw cosine sort with a ~20ms System-1 pass (`noul: is_directly_relevant`, `noul: is_context_sufficient`) — shadow-first (R5), fail-open (C-B).
- `memory_superseder.py`: replace `top_fact[0]` with `choice: relationship ∈ {supersedes, complements, contradicts_unresolved, unrelated}`; gates hot/warm/cold tier placement (Rule 9/10).

**AW6 — canon parity + observability** *(extends PRD WS1 canon compiler + WS5 observability; D5/D8)*
- Compaction templates + System-1 usage synced across all five agent instruction files via the `canon/` compiler (Rule 16 parity) — never hand-edited per file.
- Dashboard tiles: System-1 Engine KPI (req/s, P95 latency, System-1→System-2 escalation %) + per-agent Context Window Utilization gauge (green→yellow→red on the C-C thresholds). No blank `--`.

---

## 5. Phased slices (adopted from Antigravity, R5 shadow-first applied)

| Slice | Focus | Deliverables | Gate |
|---|---|---|---|
| **S1** | System-1 foundation | `system1.nix`, socket listener, ONNX INT8 engine, capability-manifest declaration (R2), `aq-qa` check | `test-system1-socket.py` PASS; RSS ≤ 350MB; P95 < 30ms |
| **S2** | Routing & safety (shadow) | Wire `system1d` into `task_classifier.py` + `aq-safe-gate` **in shadow** through the health filter (R3) | Intent bench ≥ regex accuracy; **zero** whitelist regression; shadow agreement logged |
| **S3** | Self-compact tool + controller | `context_budget_controller.py` + `self_compact` tool + event-projected RESUME/PULSE (R4) | Simulated multi-turn hits Warning + Force accurately; RESUME/PULSE match the event |
| **S4** | RAG & memory (shadow→cutover) | `rag_augmentor.py` + `memory_superseder.py`, shadow-first (R5) | RAG noise-rejection verified vs shadow baseline; supersession suite 100% |
| **S5** | Live factory stress + dashboard | End-to-end multi-turn task with live tiles | Agent self-compacts ≥2× with zero goal/state loss; DoD signed |

---

## 6. Definition of Done (Rule 15; adopted + R-refined)

1. **Integrated** — called from live paths (switchboard :8085, hybrid-coordinator :8003).
2. **Turned ON** — enabled by default in NixOS service config, with the fail-open/fail-closed split (C-B) real.
3. **Real-world validated** — a synthetic ≥50-turn task completes with ≥2 self-compactions and zero state loss; shadow-agreement evidence recorded per function (R5).
4. **Observable** — System-1 KPI + context gauge live on `dashboard.html`, no `--`.
5. **Intervenable** — operator can bypass (`AQ_SYSTEM1_DISABLE=1`) and adjust thresholds via CLI/API; per-function shadow/cutover toggle.
6. **PM-tracked** — `.agents/plans/aqos-system1-selfcompact-v1/tracker.json`, progress mechanically projected (Rule 20).

---

## 7. Round provenance & honesty note (Rule 11)

This amendment synthesizes a **2-lane** round, not a 4-lane one:
- **Antigravity** — substantive (`antigravity.md`, ratify-with-constraints). Folded in full.
- **Claude** — substantive (`claude.md`, R1–R5). Folded in full.
- **local (Qwen)** — **BLOCKED non-contribution**: the round dispatch did not inline the meta-prompt, so local reported missing context and could not act. Recorded as a round-dispatch bug (see issues-backlog): `aq-collab-round` must inline the reference document into each lane's payload.
- **Codex** — lane marked `submitted` in `round.json` but produced no materialized `codex.md`; Codex is near its weekly limit (coordinator handoff 2026-09-23). Queued for confirmatory catch-up on return.

Quorum-of-2 on substance is met. This amendment is **proposed**, pending: (a) an independent
non-author review of this synthesis, and (b) owner activation before any slice builds. Per
the coordinator plan, before landing any System-1 slice this amendment should go through an
independent review pass (candidate for `/ultrareview`).

---

## 8. Non-goals

- Not a replacement for the 35B LLM or any existing plane — additive acceleration + lifecycle control only.
- No APU VRAM use; no new network surface (UNIX socket only).
- No relaxation of the shell-safety gate — System-1 never *widens* what is permitted (C-B).
