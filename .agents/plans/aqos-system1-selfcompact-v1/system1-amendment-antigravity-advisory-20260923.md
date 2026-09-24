# Antigravity Advisory Review — System-1 PRD Amendment Synthesis

**Task ID:** `system1-amendment-advisory-20260923`  
**Date:** 2026-09-23  
**Agent:** Antigravity (Gemini 3.8 Flash via IDE OAuth Lane)  
**Subject Under Review:** `.agent/PRD-AMENDMENT-AQOS-SYSTEM1-SELFCOMPACT.md`  
**Reference Inputs:**  
- `.agents/plans/aqos-system1-selfcompact-v1/antigravity.md` (Antigravity foundation contribution)  
- `.agents/plans/aqos-system1-selfcompact-v1/claude.md` (Claude Opus 4.8 refinement R1–R5)  
- `.agents/prompts/AQOS_UNIFIED_SYSTEM1_SELF_COMPACT_META_PROMPT.md` (Original meta-prompt)  
**Role:** Independent Advisory Reviewer (Design & Security).  

---

## 1. Executive Verdict

**VERDICT: RATIFY-WITH-CHANGES.**

The coordinator's synthesis in `.agent/PRD-AMENDMENT-AQOS-SYSTEM1-SELFCOMPACT.md` is an exceptionally coherent, rigorous, and faithful unification of the round inputs. It honors all hardware constraints and security guardrails from `antigravity.md` without dilution, while successfully incorporating Claude’s operational refinements (R1–R5) to eliminate single points of failure.

The "CHANGES" designated in this verdict are non-blocking architectural clarifications and safety invariants detailed in Section 4 that should be incorporated into the amendment before slice execution (S1–S5).

---

## 2. Faithfulness Audit

The synthesis was audited against Antigravity's primary constraints:

| Constraint | PRD Amendment Section | Audit Finding | Disposition |
|---|---|---|---|
| **C-A: APU Memory Ceiling** (CPU-only, hard 400MB RSS ceiling, INT8 modernbert preferred, no VRAM) | §2 C-A, §4 AW1, §5 S1 | **Fully Preserved.** Explicitly forbids APU shared VRAM/GPU layers; reserves all 12 offload layers for `llama-server`; specifies ONNX Runtime AVX2 CPU-only; hard 400MB ceiling in `system1.nix`; S1 gate requires RSS $\le 350\text{ MB}$. | **PASS** |
| **C-B: Fail-Closed Security** (Regex blacklists non-bypassable, $<0.90$ confidence drops to Tier-0 gate) | §2 C-B, §8 Non-goals | **Fully Preserved & Clarified.** Correctly paired with Claude's R1 dual-fail architecture. Shell safety remains strictly fail-closed; System 1 cannot widen allowable commands. | **PASS** |
| **C-C: Asymmetric Context Ladders** (Parameterization: 200k remote vs 32k local) | §2 C-C, §4 AW4, §5 S3 | **Fully Preserved.** Retains exact thresholds: Remote (100k/150k/180k) vs Local (16k/24k/28k), ensuring a 4k token buffer to complete micro-slices and write `note_to_self`. | **PASS** |

---

## 3. Security & Safety Assessment

### The Dual-Fail Mode Split (Security Fail-Closed vs. Performance Fail-Open)
The amendment’s split between Function [4] (Security) and Functions [1][2][3][5][6] (Performance) is structurally sound:
1. **Shell Safety (Function [4]):** Fail-closed ensures that if `system1d` is offline, socket communication times out, or model confidence is $<0.90$, the system defaults directly to the existing conservative gate (Tier-0 operator prompt / hard rejection).
2. **Performance Paths (Functions [1, 2, 3, 5, 6]):** Fail-open to System 2 ensures that a crash or restart of `system1d` does not stall agent workflows. It cleanly falls back to existing regex patterns, cosine similarity, and direct LLM evaluation.

### Non-Widening Invariant
The PRD states: *"System-1 can only accelerate an allow it already agrees is safe, never widen what the existing gate permits."*
- **Assessment:** To make this mathematically certain in code, the S2 implementation slice must enforce an invariant relationship:
  $$\text{PermittedCommands}(\text{System1}) \subseteq \text{PermittedCommands}(\text{Baseline})$$
  $$\text{PermittedCommands}(\text{System1}) \setminus \text{PermittedCommands}(\text{Baseline}) = \emptyset$$
  System 1 must function as a pure subset filter that accelerates execution for known-safe commands, with absolute zero authority to override baseline blacklists or approval boundaries.

---

## 4. Architecture & Coherence Assessment (Claude Refinements R1–R5)

1. **R1 (Dual Fail Mode):** Accurately balances safety and availability.
2. **R2 (Declared Capability Manifest Integration):** Resolving `system1d` via the `7a25ce46` capability manifest pattern (`available`, `unavailable`, `unauthorized`) prevents unhandled connection errors on remote or containerized environments that do not host the local daemon.
3. **R3 (Routing Feeds the Health Filter):** Essential operational fix. System 1's profile recommendation must be filtered through `bdb7fa63` (`lane_health` / `.codex-quota-cooldown`). System 1 *proposes*; the health filter *disposes*. This prevents the system from routing to healthy-looking models that are locally marked down.
4. **R4 (Self-Compaction on Event Spine):** Directly addresses Deficit D3. Emitting `agent.context.compacted` via `aq-event` and projecting into `RESUME.json` / `PULSE.log` preserves the single source of truth without ad-hoc file writes or race conditions.
5. **R5 (Shadow-First Adoption):** Running System 1 in parallel with the baseline System-2 paths during S2 and S4 ensures that empirical agreement data is collected before cutting over, fulfilling the Definition of Done requirement for real-world validation.

---

## 5. Numbered Findings & Implementation Recommendations

The following four recommendations should be integrated into the amendment or explicitly addressed in the respective slice workstreams:

### Finding 1: IPC Socket Timeout & Client-Side Concurrency Contract (AW1 / S1)
- **Detail:** `system1d` will serve up to 6 distinct calling subsystems across switchboard and coordinator. Under high telemetry load, requests could queue.
- **Recommendation:** Define an explicit client-side socket timeout (recommend **50ms**). If `system1d` does not respond within 50ms, the client immediately triggers the R1 fail-open fallback to System 2, logging a latency warning to `agent.decision.system1`.

### Finding 2: Declarative Model Weight Provenance in Nix Packaging (AW1 / S1)
- **Detail:** `nix/modules/services/system1.nix` packages `system1d`. NixOS build purity prohibits arbitrary runtime downloads (e.g., untracked `huggingface-cli download`).
- **Recommendation:** S1 must declare how model weights (`rlcd-modernbert-151m`) are provisioned:
  - Either as a Fixed-Output Derivation (FOD) via `pkgs.fetchurl` with a pinned SHA-256 hash in `nix/pkgs/models/system1.nix`,
  - Or via an explicit runtime model directory path (e.g. `/var/lib/models/system1/`) managed by deployment configuration.

### Finding 3: Intercepted Tool Call Error Feedback Protocol (AW4 / S3)
- **Detail:** In Pillar II / AW4, at Tier-3 Force (e.g. $\ge 28\text{k}$ tokens for local 32k), switchboard intercepts non-compaction tool calls with a typed error.
- **Recommendation:** The amendment should specify the exact instructional payload returned to the LLM upon interception. For example:
  ```json
  {
    "error": "context_budget_exceeded",
    "tokens_consumed": 28450,
    "limit": 32000,
    "instruction": "Tool call blocked by context budget controller. You MUST invoke self_compact with note_to_self, active_hypotheses, completed_milestones, and next_exact_command to roll over context."
  }
  ```
  Without explicit guidance in the tool error output, smaller or local models may repeatedly re-attempt the blocked tool call until hard context exhaustion.

### Finding 4: Quantitative Shadow-to-Cutover Criteria (AW5 / S2 / S4)
- **Detail:** R5 requires shadow-first adoption before cutover, but specific acceptance thresholds are omitted.
- **Recommendation:** Define explicit quantitative thresholds for promotional cutover:
  - **Function [1] (Routing):** $\ge 95\%$ agreement with gold intent benchmark;
  - **Function [2] (RAG Re-ranking):** $0\%$ false rejection of ground-truth chunks; P95 latency $< 25\text{ms}$;
  - **Function [3] (Memory Supersession):** $100\%$ pass on the existing supersession unit test suite;
  - **Function [4] (Shell Safety):** $100\%$ agreement with baseline on destructive command flags ($0\%$ false negatives).

---

## 6. Readiness for Phased Slices (S1–S5)

With the adoption of these findings, `.agent/PRD-AMENDMENT-AQOS-SYSTEM1-SELFCOMPACT.md` provides an airtight, actionable foundation for the five implementation slices:
- **S1 (System-1 Foundation):** Ready for implementation.
- **S2 (Routing & Safety Shadow):** Ready for implementation.
- **S3 (Self-Compact Tool & Controller):** Ready for implementation.
- **S4 (RAG & Memory Modernization):** Ready for implementation.
- **S5 (Live Factory Stress & Dashboard Parity):** Ready for validation.
