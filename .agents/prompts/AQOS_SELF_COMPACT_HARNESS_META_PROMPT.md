# AQ-OS Master Meta-Prompt: System 1 Decision Models & Autonomous Self-Compacting Agent Harness

**Date:** 2026-09-21  
**Status:** DRAFT / Ready for Multi-Agent Consensus Round `aqos-system1-selfcompact-v1`  
**Target Architecture:** AQ-OS v1 / NixOS-Dev-Quick-Deploy Core Agent Factory  
**Authority:** Owner Directive for Collaborative Orchestrator Round (Claude, Codex, Gemini/Antigravity, Local Qwen)  
**Protocol:** `.agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md`  
**Companion Artifacts:** `.agent/PROJECT-AQOS-PRD.md`, `.agent/PROJECT-AQOS-CYCLE0-TRUTH-PRD.md`, `.agents/plans/aqos-v1/PLAN.md`, `.agent/research/20260921-system1-jev-open-weight-models.md`  

---

## 1. Executive Intent & The Dual Architectural Breakthrough

I am the operator of `NixOS-Dev-Quick-Deploy`. I want the orchestrator and expert design team to produce a unified, evidence-led architectural amendment to the **AQ-OS Refactor PRD and Implementation Plans**.

Our agentic software development factory currently suffers from two interrelated structural bottlenecks:

1. **The Context Rot & Blunt Compaction Bottleneck (Deficit D3):** Long-running agent loops accumulate noisy command outputs, grep traces, and failed attempts. Standard vendor auto-compaction triggers abruptly mid-edit, erasing transient intent, file locks, and active hypotheses through generic summaries. Furthermore, our agents are passive and blind to their own token consumption.
2. **The "System 2 Overload" Bottleneck (Deficits D1, D4, D8):** We are using heavy, slow, non-calibrated autoregressive LLMs (or brittle regexes like `_LOOKUP_RE` and `_CODE_RE`) to make discrete operational judgments (intent routing, bash safety checks, RAG relevance sorting, memory supersession, and journalctl log triage). On our Renoir APU node (27 GB RAM, 4 GB shared VRAM, Qwen3-35B taking 23.5 GB), running generative LLMs for background micro-tasks causes severe latency spikes and memory thrashing.

### The Unified Solution
We are unifying **two game-changing paradigms** into the core AQ-OS kernel:
1. **System 1 Decision Models (The Jev / `wfzyx/von` Paradigm):** Lightweight (150M–395M), non-autoregressive models running in 10ms–30ms on CPU (<400MB RAM, zero APU VRAM impact). They evaluate structured state and return RLCD Brier-calibrated typed primitives (`noul`, `choice`, `score`) with zero hallucinations.
2. **Autonomous Context Window Management (The IndyDevDan Self-Compact Paradigm):** Shifting context control to the agent via real-time budget telemetry, a first-class `self_compact` tool, an unedited, authoritative "Note-to-Self" state anchor, and a graduated 3-tier threshold ladder (Notice $\to$ Warning $\to$ Force).

---

## 2. Architectural Pillar I: System 1 Decision Models in AQ-OS

The orchestrator must design the integration of open-weight System 1 models (`wfzyx/von` at 395M and `rlcd-modernbert-151m` at 151M) across the six core operating functions of AQ-OS:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       System 1 Engine Operations Mesh                       │
│                                                                             │
│  [1. Ingress & Routing]    hybrid-coordinator (:8003) & switchboard (:8085) │
│                            Choice: task_type | Noul: local_suitable (20ms)   │
│                                                                             │
│  [2. Active RAG Pipeline]  rag_augmentor.py                                 │
│                            Noul: is_relevant | Noul: is_context_sufficient  │
│                                                                             │
│  [3. Memory Lifecycle]     memory_superseder.py & memory_broker.py          │
│                            Choice: relationship | Choice: target_tier        │
│                                                                             │
│  [4. Autonomous OS Safety] aq-safe-gate / pre-exec bash hook                │
│                            Noul: is_destructive | Choice: disposition (5ms)  │
│                                                                             │
│  [5. OS Telemetry Spider]  PRSI / RemediatorAgent journalctl monitor        │
│                            Score: anomaly_severity | Noul: needs_action     │
│                                                                             │
│  [6. Reviewer Gate]        reviewer-gate / gemini-review-gate               │
│                            Score: risk_score | Choice: review_path          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1. Ingress & Semantic Intent Routing (`hybrid-coordinator` & `switchboard`)
- Replace brittle regex heuristics in `task_classifier.py` and raw prototype distance in `intent_classifier.py`.
- Execute a 20ms System 1 forward pass:
  - `choice`: `task_type` (`lookup`, `format`, `code`, `reasoning`, `security_ops`)
  - `noul`: `local_suitable` (calibrated probability the local 35B model can execute accurately)
  - `choice`: `recommended_profile` (`local-agent`, `continue-local`, `remote-claude`, `remote-codex`)

### 2. Calibrated RAG Micro-Reranking & Sufficiency (`rag_augmentor.py`)
- Replace raw cosine similarity sorts:
  - `noul`: `is_directly_relevant`: filters out noise chunks before they pollute the 35B model's prompt.
  - `noul`: `is_context_sufficient`: checks whether retrieved chunks actually answer the query before invoking inference.
  - Post-generation `noul`: `is_answer_grounded_in_context`: instant hallucination detection.

### 3. Memory Integrity & Tier Gating (`memory_superseder.py` & `memory_broker.py`)
- Replace vector-blind supersession (which blindly overwrites based on cosine similarity):
  - `choice`: `relationship` (`supersedes`, `complements`, `contradicts_unresolved`, `unrelated`)
  - `choice`: `target_tier` (`hot_pointer`, `warm_topic_file`, `discard_transient`) per Rule 10 Memory Discipline.

### 4. Autonomous Operations Boundary & Shell Safety (`AUTONOMOUS-OPERATIONS-POLICY.md`)
- Sub-5ms pre-execution check on bash commands:
  - `noul`: `is_destructive`
  - `noul`: `violates_least_privilege`
  - `choice`: `disposition` (`allow`, `warn`, `block`, `prompt_human`)

### 5. Continuous OS Telemetry & Journalctl Spider (`PRSI` / `RemediatorAgent`)
- High-throughput stream filtering on `journalctl -f` and cgroups memory pressure:
  - `score`: `severity_score` (0.0 to 1.0)
  - `choice`: `fault_category` (`gpu_driver`, `nix_store`, `service_oom`, `benign_noise`)
  - `noul`: `requires_remediator_action` (triggers alert only when probability $\ge 0.90$)

### 6. Review Gate Triaging & Rule 19 Implementer Routing
- Screen git diffs before triggering expensive remote flagship rounds:
  - `score`: `architectural_risk_score` (1 to 5)
  - `choice`: `cheapest_eligible_agent` (`local_qwen_floor`, `codex_standard`, `claude_flagship`) per Rule 19.

---

## 3. Architectural Pillar II: Autonomous Self-Compacting Agent Harness

The orchestrator must design the integration of IndyDevDan's self-compacting architecture into the agent runtime:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   Self-Compacting Context Management Flow                   │
│                                                                             │
│  [  0% - 59%  ]  NORMAL: Agent executes tasks unimpeded.                    │
│                                                                             │
│  [ 60% - 79%  ]  NOTICE THRESHOLD: Soft telemetry informs agent to seek a   │
│                  natural milestone boundary.                                │
│                                                                             │
│  [ 80% - 89%  ]  WARNING THRESHOLD: Tactical operational buffer. Instructs  │
│                  agent to wrap up current micro-step and self-compact.      │
│                                                                             │
│  [ 90% - 100% ]  FORCE THRESHOLD: Harness blocks all action tools (bash,     │
│                  write, edit). ONLY `self_compact` is allowed.              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Agent calls self_compact(note_to_self)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Post-Compaction Seed State                         │
│  - System Prompt & Canonical Rules (`WORKFLOW-CANON.md`)                    │
│  - Unedited, authoritative `note_to_self` & `RESUME.json` snapshot          │
│  - Active goals, verified test commands, and exact next step                │
│  - Immediate resumption at Turn 1 without amnesia                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **Real-Time Context Telemetry:** Turn envelopes in switchboard and coordinator inject continuous token awareness:
   `[Context Telemetry: Tokens Used: 142,300 / 200,000 (71.1%) | Stage: WARNING | Compaction Budget: 18,000 tok remaining]`
2. **First-Class `self_compact` Tool:** Exposed in agent manifests (`tooling_manifest.py`):
   `self_compact(note_to_self: str, active_hypotheses: list[str], completed_milestones: list[str], next_exact_command: str)`
3. **Three-Tier Operational Threshold Ladder:**
   - **Notice (50%–60%):** Advisory badge.
   - **Warning (75%–80%):** Operational buffer. Agent is prohibited from starting expansive refactors; must finish the current atomic step and self-compact.
   - **Force / Hard Cutoff (90%–95%):** Policy gate locking all modification tools, permitting only `self_compact`.
4. **Authoritative "Note-to-Self" Anchor:** Preserved verbatim across compaction and re-seeded into Turn 1 of the new trajectory. Eliminates lossy third-person LLM summarization.
5. **Hardware-Honest Scaling:** Calibrated for both 200k remote models (Claude/Codex) and 32k local models (Qwen3-35B on APU).

---

## 4. The Symbiosis: Where System 1 Multiplies Self-Compacting Efficiency

The true leverage occurs where System 1 models directly power the Self-Compacting harness:

1. **Intelligent Milestone Boundary Detection:** During the Tier 2 (Warning) stage, a System 1 forward pass evaluates each tool result:
   - `noul`: `is_clean_milestone_boundary` (e.g. tests just passed, git commit staged).
   - If `true`, the harness injects an explicit directive: *"Clean milestone detected. Trigger self_compact now."*
2. **Pre-Compaction Trajectory Sifting:** Before rolling over context, System 1 parses prior turns:
   - `choice`: `turn_retention` (`preserve_salient`, `prune_verbose_output`, `drop_noise`).
   - Strips megabytes of raw grep and terminal dumps while preserving critical decision rationales.
3. **Note-to-Self Quality Gate:** When `self_compact` is called, System 1 verifies:
   - `noul`: `is_note_actionable_and_complete`.
   - If missing `next_exact_command` or active blockers, prompts the agent to supply it before executing compaction.

---

## 5. Targeted Workstream Amendments for `PROJECT-AQOS-PRD.md`

The orchestrator must structure PRD amendments across the established AQ-OS workstreams:

### Workstream 1: Kernel & Core Services (WS1 / Kernel Split)
- **`system1d.service` Microservice:** Define a dedicated systemd service in `nix/modules/services/system1.nix`.
  - Engine: ONNX Runtime (C++ / Python) or Rust running CPU AVX2.
  - IPC: High-speed UNIX domain socket (`/run/nixos-ai-stack/system1.sock`), mode `0660`, user `ai-stack`.
  - AppArmor: Offline profile (`deny network inet`, `deny network inet6`, read-only access to `/nix/store/` weights).
- **`context_budget_controller.py`:** Add the 3-tier threshold controller to `hybrid-coordinator` and `switchboard`.
- **`self_compact` Tool:** Wire into `tooling_manifest.py` with Tier 3 enforcement locks.

### Workstream 2: Contracts & Schemas (WS2 / Contracts Before Code)
- Define versioned JSON schemas in `contracts/schemas/`:
  - `contracts/schemas/system1/decision-v1.json` (`/v1/systemone` request/response schema).
  - `contracts/schemas/agent-tools/self-compact-v1.json`.
  - `contracts/schemas/events/context-compacted-v1.json`.

### Workstream 3: Event Spine & A2A State (WS3 / Event Spine)
- Publish `agent.decision.system1` and `agent.context.compacted` to the Redis stream spine.
- When `self_compact` is called, atomically project the state to `.agent/collaboration/RESUME.json` and append to `PULSE.log`.

### Workstream 4: RAG & Memory Modernization (WS4)
- Wire System 1 cross-encoder checks into `rag_augmentor.py` and semantic supersession into `memory_superseder.py`.

### Workstream 5: Canon & Agent Parity (WS5 / Compile the Canon)
- Compile `self_compact` and context telemetry definitions into `canon/` templates, projecting identically to `CLAUDE.md`, `CODEX.md`, `GEMINI.md`, `LOCAL-AGENT.md`, and `WORKFLOW-CANON.md` per Rule 18 Parity.

### Workstream 6: Observability & Dashboard Parity (WS6)
- Add real-time telemetry to `dashboard.html` / `dashboard.js`:
  - System 1 Requests/sec, P95 latency (ms), and System 1-to-System 2 escalation ratio.
  - Active Context Utilization gauge per agent session with color-coded threshold badges (Green / Yellow / Red).

---

## 6. Required Output Deliverables for the Orchestrator

In the collaborative round `aqos-system1-selfcompact-v1`, the orchestrator must produce:

1. **`PRD-AMENDMENT-AQOS-SYSTEM1-SELFCOMPACT.md`:** Comprehensive specification covering the System 1 daemon, the self-compact engine, and their symbiosis.
2. **`PLAN-AQOS-SYSTEM1-SELFCOMPACT-SLICES.md`:** Phased implementation slices:
   - **Slice 1 (System 1 Baseline):** `system1d` ONNX socket server + `aq-qa` health probe + routing integration.
   - **Slice 2 (Context Controller & Tool):** `context_budget_controller.py` + `self_compact` tool + `RESUME.json` atomic projection.
   - **Slice 3 (Threshold Gating & Tier 3 Lock):** Enforcement of Warning buffer and Force tool lock.
   - **Slice 4 (RAG & Memory Wiring):** Upgrading `rag_augmentor.py` and `memory_superseder.py`.
   - **Slice 5 (Live Verification):** 50-turn agent stress test proving zero state loss across 3 compactions + dashboard parity.
3. **`ACTIVATION-GATE-CRITERIA.md`:** Verification matrix across all 6 Definition of Done dimensions.

---

## 7. Non-Negotiable Operational Constraints

1. **Hardware Honesty:** System 1 models must never compete for the 4 GB APU shared VRAM. Memory consumption must remain strictly under 400 MB RAM on CPU.
2. **Rule 18 (Agent Parity):** All features must be model-agnostic and function identically across Claude, Codex, Gemini/Antigravity, and local Qwen.
3. **OWASP Agentic Top 10 Confinement:** System 1 daemon must be strictly network-denied via AppArmor.
4. **Anti-Gaming:** Compaction is only successful if the agent resumes and successfully executes `next_exact_command` post-compaction.
