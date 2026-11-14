# PRD: SOTA Agentic Operating System (`AQ-OS`), Co-Evolving System 1 / System 2 Collective & Verified Software Factory

- **Document ID**: `PROJECT-FRUGAL-SOTA-LEADERSHIP-PRD`
- **Status**: `ROUND 1 DEBATE ACTIVE (Active Cohort: Gemini + Claude + Local; Codex Window Closed -> Queued in AGENT-CATCHUP-QUEUE.md per Rule 18)`
- **Author**: `Simurg@gemini/gemini-4-argon#05b9c7ce` (co-designed with Owner)
- **Date**: 2026-11-13
- **Plan Directory**: `.agents/plans/frugal-sota-leadership-20261113/`
- **Companion Artifacts**:
  - Architecture & 5-Slice Plan (`F1`–`F5`): `.agents/plans/frugal-sota-leadership-20261113/DESIGN.md`
  - Multi-Agent Debate & Execution Meta-Prompt: `.agents/plans/frugal-sota-leadership-20261113/META-PROMPT.md`
  - PM Tracker: `.agents/plans/frugal-sota-leadership-20261113/tracker.json`

---

## 1. Owner Intent & Vision: Five Interlocking SOTA Pillars (KISS & Frugal-First)

Our mission is to blaze the path and hold a durable SOTA lead across **five interlocking domains**, engineered with **radical simplicity (KISS)** to run within a sovereign, resource-disciplined envelope (**standard developer laptop: 27 GB RAM / max 12 GPU layers + pooled basic cloud subscriptions across `Claude`, `Codex`, and `Gemini` with zero API overage burn**):

1. **Pillar 1 — The Declarative Agentic Operating System (`AQ-OS` on NixOS)**:
   - The OS, containment boundary, and agent harness are one declarative unit. Every service, port (`nix/modules/core/options.nix`), secret (`/run/secrets/*`), AppArmor MAC profile, systemd unit, power/sleep inhibitor (`aq-keep-awake` / `aq-llama-resume-gate`), git hook (`git-hooks.nix`), and compiled Rust state gate (`aq-state`) boots deterministically from NixOS with generation-fenced self-healing (`ai-stack-health-monitor`).
2. **Pillar 2 — Co-Evolving Local "System 1" Models Inside `AQ-OS` (Distilled from "System 2")**:
   - On a basic laptop, we do not run slow 70B models in 20-turn loops—we run **fast, specialized Local "System 1" models** (sub-20ms CPU statistical/feature routers, `AIDB` embeddings/rerankers, and bounded `Qwen` GGUF specialists via `llama.cpp`) that act as the OS's fast reflexes.
   - **The Flywheel**: Every time our **System 2** frontier lanes (`Claude`, `Codex`, `Gemini`) freeze a design, land a `tier0`-verified patch, or catch a defect in `aq-land`, that verified trajectory (`Surgical Context Packet -> Verified Diff -> Gate Receipt`) is archived as a **Compiler-Verified Distillation Dataset** (`trajectories.jsonl`) to continuously calibrate local System 1 routing and inject 1-shot verified exemplars into local prompts.
3. **Pillar 3 — The Phalanx of Deterministic Compilers, Verifiers, Tests & Gates**:
   - Local System 1 models and cheap Tier-2 implementers achieve frontier-grade reliability when surrounded by an **unforgiving, sub-second deterministic verifier phalanx** (`tier0.d`, `aq-qa` phases 0–N, Rust `aq-state` gates, `basedpyright` + `ruff` ratchets, tree-sitter AST validators, call-graph contract checks, fault-injection tests, and real-JS dashboard probes).
   - Candidate patches are validated or rejected locally on CPU in milliseconds for `$0.00` before a single cloud review token is spent.
4. **Pillar 4 — The Multi-Model Collaborative Environment (`Simurg` Collective)**:
   - Four independent model families (`Claude`, `Codex`, `Gemini`, `Local`) collaborate under one collective identity (`Simurg@<lane>/<model>#<session>`) with **strict epistemic independence**:
     - **Never Self-Review (`Rule 18`)**: Off-branch `aq-land` review receipts signed by an independent model family.
     - **Epistemic Memory Collapse (`Persona P3` rev 3 — KISS)**: Cross-lane agreement corroborates facts in Postgres `collapse_facts`; cross-lane contradiction never silently overwrites—the active agent asks the owner a plain numbered question in the CLI (`1) keep mine, 2) keep theirs, 3) keep both`) and applies the reply directly.
     - **Synchronized Subscription Quota Arbitrage**: Rolling window rotation + `AGENT-CATCHUP-QUEUE.md` eliminates single points of failure when any provider window (such as `codex` today) is closed.
5. **Pillar 5 — Ecosystem Leverage & Open-Source Reciprocity**:
   - Stand on the shoulders of external research and agent swarms via quarantined intake (`osint-systems` + `capability-intake`), explicit citation (`docs/architecture/ECOSYSTEM-RECIPROCITY.md`), and owner-gated ("Propose-Not-Push") upstream contribution packets where the active CLI agent asks the owner before any external publication.

---

## 2. Empirical & Research Foundation ("Standing on the Shoulders of Giants")

| Pillar | Foundational Reference | Proven Principle | How Our Stack Operationalizes & Advances It |
|---|---|---|---|
| **Software Factory & Pre-Slicing** | **Xia et al. (UIUC, 2024)** — *"Agentless"* & **Gauthier (*Aider*)** / **Yang et al. (Princeton, NeurIPS 2024)** — *"SWE-agent ACI"* | Deterministic AST localization + bounded tool interfaces match/beat open-ended bash loops at **1/10th–1/20th the token cost**. | `aq-context-packet` compiles `<2,500`-token AST + call-graph + `AIDB` packets on CPU (`<200ms`, `0` LLM tokens) before any model is called. |
| **System 1 / System 2 Co-Evolution** | **Kahneman (System 1 / System 2)**; **Chen et al. (Stanford, 2023)** — *"FrugalGPT"*; **Ong et al. (UC Berkeley, 2024)** — *"RouteLLM"*; **Verification-Guided Distillation (2025)** | Distilling verified System 2 reasoning + compiler/test feedback into smaller System 1 models and learned routers transfers frontier capability into compact local weights. | Harvest every `tier0` + `aq-land` verified slice (`OutcomeReceipt` + diff + context packet) into a local **Verified Trajectory Corpus** to calibrate local System 1 routers and 1-shot exemplars. |
| **Deterministic Verifier Phalanx & `AQ-OS`** | **Zaharia, Stoica et al. (UC Berkeley BAIR, 2024)** — *"Compound AI Systems"* & **Krentsel et al. (2025)** — *"Reality Is the Final Verifier"* | Probabilistic models require deterministic symbolic verifiers and **live deployment verification** to prevent reward-hacking and drift. | Our **Compiler + Gate + `aq-qa` Phalanx** + **Rule 15 Activation Gate**: nothing ships or enters System 1 training data unless it passes deterministic static, unit, integration, and live runtime QA checks. |
| **Collaborative Env (`Simurg`)** | **Du et al. (MIT, ICML 2024)** — *"Improving Factuality and Reasoning through Multiagent Debate"* | Cross-family verification eliminates correlated single-model blind spots. | Cross-family `aq-land` review receipts + `Simurg` P3 memory conflict governance (CLI-direct owner decisions). |

---

## 3. The 4-Tier Compute & Cognition Architecture (Compiler Wall + System 1 + System 2)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ TIER 0: DETERMINISTIC COMPILER, VERIFIER & GATE PHALANX (0 tokens · <100ms)  │
│ • Symbolic Slicers: `lean-ctx` (tree-sitter AST), `understand-anything` graph│
│ • Compilers & Type Walls: `nix flake`, `cargo`, `basedpyright`, `ruff`       │
│ • Trust & State Gates: Rust `aq-state`, `check-owned-scope`, `git-hooks.nix` │
│ • Runtime & UI Verifiers: `tier0.d/*`, `aq-qa` phases 0–N, Node JS harnesses │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ TIER 1: LOCAL "SYSTEM 1" FAST REFLEX MODELS (0 cloud tokens · laptop-tuned)  │
│ • Fast Embeddings & Rerankers (`AIDB` / Qdrant + `MemoryBroker` Postgres)    │
│ • Sub-20ms CPU System 1 Router (`system1_router.py`): intent/risk scoring,   │
│   first-pass `tier0` yield prediction, and 1-shot exemplar selection         │
│ • Bounded Local Coding & Review Specialist (`Qwen` on `llama.cpp`, thermally │
│   gated by `aq-keep-awake`), continuously improved via System 2 distillation │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       ▼ (Pre-sliced <=2,500-token Packet)
┌──────────────────────────────────────────────────────────────────────────────┐
│ TIER 2: POOLED SUBSCRIPTION IMPLEMENTERS (1-to-2 turn execution in worktree) │
│ • Cheapest-eligible healthy subscription (`Sonnet`, `Haiku`, `Codex`,        │
│   `Gemini Flash`) selected by live quota window + measured task-type yield   │
│ • Iterates strictly against the local Tier-0 Compiler & Verifier Phalanx     │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       ▼ (Only after Tier-0 Phalanx is 100% PASS)
┌──────────────────────────────────────────────────────────────────────────────┐
│ TIER 3: "SYSTEM 2" FRONTIER ARCHITECTS & CROSS-FAMILY REVIEWERS              │
│ • Upfront 150-line `DESIGN.md` freeze + multi-perspective architectural audit│
│ • Binding cross-family `aq-land` review receipt; feeds System 1 distillation │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Five Execution Slices (`F1`–`F5`) — Prototype & Rollout Sequence

> **Cohort Note (2026-11-13)**: With `codex`'s session window closed, Round 1 debate and prototype execution proceed immediately across **`Simurg@gemini` + `Simurg@claude` + `Simurg@local`** per Rule 18 (`codex` catches up via `AGENT-CATCHUP-QUEUE.md` on window reopen).

| Slice | ID | Pillar Focus | First Prototype / Deliverable (KISS) |
|---|---|---|---|
| **F1** | `f1-symbolic-factory-engine` | **Pillar 3 (Software Factory & Verifier Wall)** | Build `scripts/ai/aq-context-packet` (deterministic `<2,500`-token AST + call-graph + `AIDB` 1-shot exemplar compiler) and enforce the pre-review deterministic compiler/test wall in `scripts/ai/aq-land`. |
| **F2** | `f2-agentic-os-and-collab-fabric` | **Pillars 1 & 4 (`AQ-OS` + `Simurg` Collab Env)** | Integrate multi-subscription rolling window arbitrage + `AQ-OS` laptop AC/battery/load/thermal guard (`aq-keep-awake` / `delegate-to-local`) + `vw_per_kt` and `tier0_caught_defects` telemetry in `outcome_receipt.py`. |
| **F3** | `f3-system1-distillation-and-gates` | **Pillars 2 & 3 (Local System 1 Co-Evolution & Verifier Phalanx)** | Build `scripts/data/collect-verified-trajectories.py` (archiving secret-scrubbed `(context_packet, rejected_attempts, verified_diff, review_receipt)` tuples on `aq-land` merge), `scripts/ai/lib/system1_router.py` (sub-20ms CPU router + 1-shot exemplar selector), and `scripts/testing/test-system1-calibration.py`. |
| **F4** | `f4-ecosystem-reciprocity-bridge` | **Pillar 5 (Ecosystem Leverage & Reciprocity)** | Ship `docs/architecture/ECOSYSTEM-RECIPROCITY.md`, seed R1–R5 research patterns into `AIDB`, and add `aq-rsi reciprocity-packet` (staging owner-reviewable upstream contribution bundles and asking the owner directly in the CLI). |
| **F5** | `f5-sota-leadership-scoreboard` | **All 5 Pillars (Glass-Box Proof & Showcase)** | Ship the live `SOTA Factory, AQ-OS & System 1 Scoreboard` panel on the Command Center Dashboard (`aistack.py` + `dashboard.js`) + registered `aq-qa` phase-0 check. |

---

## 5. Open Design Questions for Round 1 Debate (`Gemini` + `Claude` + `Local`)

1. **Q1 — Surgical Context Packet Budget & 1-Shot Exemplar Injection (`F1` / `F3`)**:
   - Should `aq-context-packet` enforce a hard `2,500`-token default ceiling (automatically degrading from full function bodies to AST signatures + line ranges when exceeded) while reserving up to `400` tokens for the closest compiler-verified 1-shot trajectory exemplar when targeting `local` System 1 models?
2. **Q2 — `AQ-OS` Laptop Thermal, Battery & Load Governance for System 1 (`F2` / `F3`)**:
   - Beyond `aq-keep-awake`'s AC / 40%-battery floor, what exact `/proc/loadavg` and `/sys/class/thermal` thresholds should govern Tier-1 `llama.cpp` System 1 tasks vs. sub-20ms CPU-only symbolic/statistical routers?
3. **Q3 — System 2 $\rightarrow$ System 1 Distillation Scrubbing & CLI-Direct Reciprocity (`F3` / `F4`)**:
   - What secret-scrubbing invariants must run on `(context_packet, rejected_attempts, verified_diff)` tuples before they are stored in `/var/lib/ai-stack/hybrid/distillation/trajectories.jsonl` or staged into `.agents/delegation/outputs/upstream-reciprocity/` for CLI-direct owner sign-off?
