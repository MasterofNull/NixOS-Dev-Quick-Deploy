---
doc_type: prd
id: durable-proactive-oncall-mesh
title: Durable Proactive On-Call Agent Mesh, High-Frequency Triage, and Pi-Style Streaming UI
status: draft
owner: hyperd
date: 2026-10-12
priority: P0-high
references:
  - https://youtu.be/DNDYYHsypZg
  - Pi Durable (@earendil-works/pi-durable)
  - TypeSafe Jev Fast Classifier Architecture
  - IndyDevDan Pi Coding Agent UI Interface
  - .agents/plans/durable-proactive-mesh/review/codex-expert-review.md
---

# Durable Proactive On-Call Agent Mesh & Pi Streaming UI PRD

## 1. Intent & Executive Summary

Current AI coding assistants predominantly operate as **passive, terminal-bound reactive tools**: they wait idly for human text prompts, lack **durable execution guarantees** across process restarts, and obscure multi-agent collaboration behind disconnected log files.

This project delivers a **Durable Proactive On-Call Agent Mesh** into the NixOS AI harness, establishing complete architectural parity with and surpassing the benchmarks demonstrated in the **Pi Durable** (`@earendil-works/pi-durable`), **TypeSafe Jev**, and **IndyDevDan Pi UI** ecosystems:

1. **System 1 High-Frequency Triage Engine (`aq-triage`)**: Continuous, sub-second classification of live systemd journald logs and service errors using fast structured classifiers. Employs durable cursors (`__CURSOR`) and calibrated probabilities, filtering out benign operational noise (<200ms latency).
2. **Crash-Resilient Durable Runtime (`aq-durable`)**: Implements the **Effect Sandwich Pattern** with explicit **Outcome Reconciliation** (`PREPARED -> EXECUTING -> COMMITTED / OUTCOME_UNKNOWN -> RECONCILING`), strict idempotency keys, and atomic state document versioning.
3. **Autonomous On-Call Agent Service (`aq-oncalld`)**: Event-driven background daemon that wakes on high-confidence incident triggers, spawns worktree-isolated implementers (Rule 17), enforces live reproduction and Rule 19 root-cause discipline, obtains independent review (Rule 18), and stages pull requests.
4. **Pi-Style Multi-Agent Streaming UI & Canvas (Dashboard :8889 / SSE)**: Brings the web dashboard directly into alignment with IndyDevDan's Pi coding agent interface:
   - **Live Agent Mesh Hierarchy**: Visual tree showing primary orchestrators, on-call workers, and agentically spun-up sub-agents with live lifecycle states (`idle`, `thinking`, `tool_executing`, `awaiting_input`, `done`, `errored`).
   - **Per-Agent Streaming Execution Window**: Real-time streaming of tokens, thinking blocks, tool calls, and live stdout/stderr output.
   - **Human-in-the-Loop Interaction & Guidance**: Direct operator guidance input prompt per agent ("mid-flight guidance"), step-by-step approval buttons, and pause/resume execution controls.

---

## 2. Parity Matrix: Pi Durable / Jev / Pi UI vs. NixOS Harness

| Dimension | Video Benchmark (Pi Durable + Jev + Pi UI) | NixOS Current State | Parity & Enhanced Specification |
| :--- | :--- | :--- | :--- |
| **Agent Triggering Model** | **Proactive**: Event-driven triggering from live telemetry streams. | **Reactive / Polled**: Interactive terminal prompts or batch cron jobs. | **`aq-oncalld`**: Background systemd daemon continuously listening to live journald streams. |
| **Stream Triage (System 1)** | **TypeSafe Jev**: Sub-300ms fast decision model returning calibrated choice probabilities. | Regex patterns in `watch-agents.sh` and `health-spider.py`. | **`aq-triage`**: Structured classification engine yielding typed `TriageClassification` schemas with durable cursors in <200ms. |
| **Crash Safety & Idempotency** | **Pi Durable**: Effect sandwich, state document versioning, idempotent tool dispatch. | Resumption via `RESUME.json`, but tool calls lack transactional side-effect envelopes. | **`aq-durable`**: Transactional tool sandwich with deterministic idempotency keys and explicit `OUTCOME_UNKNOWN -> RECONCILING` recovery. |
| **Incident Investigation & Remediation** | Autonomous coding agent investigates, tests, and stages candidate fix. | PRSI autonomous loop, but primarily geared toward periodic batch self-improvement. | **On-Call Pipeline**: Auto-spawns worktree-isolated implementers (Rule 17) with independent review (Rule 18) and PR staging. |
| **Multi-Agent UI & Visualization** | **Pi UI Interface**: Live visible agent/sub-agent tree, dedicated streaming window per subagent. | Fragmented between terminal logs, Zellij tabs, and static card polls on :8889. | **Pi-Style Streaming Canvas**: Interactive agent hierarchy on Dashboard (:8889) with real-time SSE streaming window per sub-agent. |
| **Human-in-the-Loop Interaction** | Direct interactive prompt per agent, pause/resume, mid-flight guidance, step approval. | Batch approval (`aq-approve`) or manual CLI terminal interaction. | **Interactive Agent Guidance**: Live web input box per agent, instant pause/resume, step-by-step tool approval, and mid-flight steering. |

---

## 3. System Architecture & Component Interactions

```text
       +-----------------------------------------------------------+
       |                  Live Telemetry Sources                   |
       |  (systemd journald, :8002-:8005 services, alertmanager)   |
       +-----------------------------+-----------------------------+
                                     |
                                     v
       +-----------------------------------------------------------+
       |            System 1: High-Frequency Triage Engine         |
       |               (aq-triage / Fast Classifier)               |
       |  - Sub-200ms evaluation latency (P95)                     |
       |  - Durable journald cursor tracking (__CURSOR)            |
       |  - Typed incident classification & calibrated confidence  |
       +-----------------------------+-----------------------------+
                                     | [Incident Trigger: Severity >= HIGH, Confidence >= 0.85]
                                     v
       +-----------------------------------------------------------+
       |         System 2: Autonomous On-Call Daemon               |
       |                     (aq-oncalld)                          |
       |  - Deduplicates incidents & acquires incident lock        |
       |  - Dispatches to cheapest eligible implementer (Rule 17)  |
       |  - Confines in isolated worktree + AppArmor sandbox       |
       +-----------------------------+-----------------------------+
                                     |
                                     v
       +-----------------------------------------------------------+
       |             Durable Agent Runtime (aq-durable)            |
       |  - Effect Sandwich: Intent -> Side Effect -> Receipt      |
       |  - Reconciler: PREPARED -> EXECUTING -> OUTCOME_UNKNOWN   |
       |  - Strict Idempotency Keys across all tool calls          |
       |  - Versioned State Documents & CAS update concurrency     |
       +-----------------------------+-----------------------------+
                                     |
                                     v
       +-----------------------------------------------------------+
       |               Validation & Governance Gates               |
       |  - Live controlled reproduction test                      |
       |  - Tier-0 Pre-commit Gate (56 checks)                     |
       |  - Independent Reviewer evaluation (Rule 18)              |
       |  - Staged PR generation bound to immutable candidate hash |
       +-----------------------------+-----------------------------+
                                     |
                                     v
       +-----------------------------------------------------------+
       |       Pi-Style Multi-Agent Streaming Canvas & Control     |
       |         (Dashboard :8889 + Switchboard SSE Stream)        |
       |  - Real-time agent & sub-agent hierarchy tree             |
       |  - Live streaming execution window (thoughts/tools/stdout)|
       |  - Human-in-the-loop mid-flight guidance input prompt     |
       |  - Step approval, pause/resume, and aq-approve grants     |
       +-----------------------------------------------------------+
```

---

## 4. Key Contracts & Specifications

### 4.1. System 1 Triage Schema (`TriageClassification`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "TriageClassification",
  "type": "object",
  "required": [
    "incident_id",
    "journal_cursor",
    "timestamp",
    "subsystem",
    "incident_class",
    "severity",
    "confidence",
    "actionable",
    "correlation_key",
    "context_snippet"
  ],
  "properties": {
    "incident_id": { "type": "string" },
    "journal_cursor": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "subsystem": { "type": "string" },
    "incident_class": {
      "type": "string",
      "enum": ["crash", "deadlock", "cve_vulnerability", "auth_failure", "memory_leak", "timeout", "regression"]
    },
    "severity": {
      "type": "string",
      "enum": ["info", "low", "medium", "high", "critical"]
    },
    "confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "actionable": { "type": "boolean" },
    "correlation_key": { "type": "string" },
    "context_snippet": { "type": "string" }
  }
}
```

### 4.2. Durable Effect Sandwich & Reconciliation Contract

All side-effect tool executions adhere to the 3-phase sandwich and 3-class tool categorization:

```text
PREPARED (Intent Logged)
   │
   ▼
EXECUTING (Tool Executed)
   │
   ├─► Success ──────────────► COMMITTED (Receipt Persisted)
   │
   ├─► Known Error ──────────► FAILED_KNOWN (Error Logged)
   │
   └─► Crash / Timeout ──────► OUTCOME_UNKNOWN
                                    │
                                    ▼
                               RECONCILING (Query target state before replay)
```

1. **Class 1 (Read-Only)**: Pure read operations (`cat`, `grep`, `status`). Safe to replay unconditionally.
2. **Class 2 (Idempotent Overwrite)**: Deterministic state writes (file overwrite with known content hash). Safe to replay.
3. **Class 3 (Non-Idempotent / External Mutation)**: Git commits/pushes, external API mutations, process restarts. Replay is FORBIDDEN under `OUTCOME_UNKNOWN` until the reconciler verifies target state.

### 4.3. Incident Remediation Lifecycle State Machine

```text
INTAKE -> CORRELATE -> ADMIT -> CLAIM -> ISOLATE -> REPRODUCE
       -> DIAGNOSE -> FIX -> VALIDATE -> INDEPENDENT_REVIEW
       -> STAGE_PR -> AWAIT_OPERATOR -> ACTIVATION
```
- **Fencing**: Claims carry monotonic epoch tokens to fence stale workers.
- **Subject Binding**: Independent reviews and operator approvals bind to `candidate_sha256 = hash(git_tree + test_proofs)`. Any subsequent change invalidates the approval.

### 4.4. Pi-Style Streaming UI & Interaction Protocol

1. **SSE Session Stream (`/api/v1/agents/{id}/stream`)**:
   - `agent_spawned`: `{agent_id, parent_id, role, model, worktree}`
   - `lifecycle_delta`: `{agent_id, status: "thinking" | "tool_executing" | "awaiting_input" | "done"}`
   - `token_stream`: `{agent_id, delta: string, is_thought: boolean}`
   - `tool_call`: `{agent_id, tool_name, tool_call_id, args}`
   - `tool_output`: `{agent_id, tool_call_id, stdout: string, stderr: string}`
2. **Operator Control & Guidance Endpoints**:
   - `POST /api/v1/agents/{id}/guidance`: Injects human guidance into the agent's ongoing turn.
   - `POST /api/v1/agents/{id}/step-approve`: Grants single-step execution approval for gated tools.
   - `POST /api/v1/agents/{id}/pause` & `resume`: Pauses or resumes agent execution.

---

## 5. Delivery Slices & Implementation Roadmap

- **Slice DP0 — Architecture, Threat Model & Specification Contracts**:
  - Author formal design packet and editorial tracker in `.agents/plans/durable-proactive-mesh/`.
  - Author schemas for `TriageClassification`, `DurableEffectSandwich`, and `AgentStreamEvent`.
  - Fold Codex expert review recommendations into baseline design.
- **Slice DP1 — System 1 High-Frequency Triage Engine (`aq-triage`)**:
  - Implement journald log stream reader with persistent cursor tracking (`__CURSOR`).
  - Integrate fast structured classification engine (<200ms P95 latency).
  - Add QA check `0.10.66` into `scripts/ai/aq-qa` for triage schema compliance.
- **Slice DP2 — Durable Agent Runtime Core (`aq-durable`)**:
  - Build Effect Sandwich middleware in `hybrid-coordinator` (:8003).
  - Implement SQLite transactional intent logging, idempotency store, and CAS document updates.
  - Implement crash-recovery test simulation proving clean reconciliation across mid-step crashes.
- **Slice DP3 — Autonomous On-Call Daemon (`aq-oncalld`)**:
  - Implement systemd background daemon `aq-oncalld`.
  - Wire automatic incident wakeups to worktree-isolated implementers (`worktree-isolation.sh`).
  - Enforce independent review gate (Rule 18) and PR staging bound to candidate hash.
- **Slice DP4 — Pi-Style Multi-Agent Streaming Canvas & Interaction Plane**:
  - Expose SSE session streaming bus on Switchboard (:8085) and Dashboard backend.
  - Build frontend streaming canvas in Web Dashboard (:8889):
    - Sub-agent hierarchy tree and status indicators.
    - Live streaming execution windows for thoughts, tools, and output.
    - Human-in-the-loop input prompt for mid-flight guidance and step approvals.
- **Slice DP5 — E2E Incident-to-Canvas Verification & Activation Gate**:
  - End-to-end integration test: injected failure -> triage -> on-call wakeup -> live streaming in UI -> operator guidance -> Tier-0 verified PR -> operator merge.
  - Six-dimension Activation Definition of Done attestation.

---

## 6. Definition of Done & Success Criteria

1. **System 1 Triage Latency & Precision**: Measured P95 classification latency < 200ms with persistent journald cursor recovery.
2. **Reconciliation Safety**: 100% of simulated mid-step kill signals (`SIGKILL`) recover through the reconciler without duplicating Class 3 mutations.
3. **Pi UI Streaming Parity**: All active agents and agentically spun-up sub-agents render in real-time in the web dashboard, streaming token deltas and tool calls with <100ms render latency.
4. **Human-in-the-Loop Interactivity**: Operator can successfully inject guidance and pause/resume running agents from the web UI.
5. **Zero Vulnerability / Anti-Gaming**: Strict adherence to Rule 19 (Root-Cause Discipline) and Rule 17 (Cheapest-Eligible Implementer); zero mock passes or hardcoded scanner suppressions.
