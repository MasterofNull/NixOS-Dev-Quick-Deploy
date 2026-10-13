# Durable Proactive On-Call Agent Mesh & Pi Streaming Canvas Design Document

## 1. Context & Motivation

This architecture merges the proactive durable agent pattern from **Pi Durable** (`@earendil-works/pi-durable`) and **TypeSafe Jev** with the interactive, multi-agent visual streaming canvas from **IndyDevDan's Pi Coding Agent UI Interface**.

Core Objectives:
1. **Continuous Stream Triage**: Ingest systemd journald telemetry at sub-second latency via a fast local decision model, filtering benign noise while capturing actionable incidents.
2. **Crash-Resilient Durable Runtime**: Guarantee that agent executions survive crashes, reboots, and timeouts through the Effect Sandwich Pattern and explicit outcome reconciliation.
3. **Autonomous On-Call Remediation**: Wakes an on-call agent in an unprivileged, worktree-isolated sandbox, generates root-cause compliant fixes (Rule 19), obtains independent review (Rule 18), and stages pull requests.
4. **Pi-Style Multi-Agent Streaming Canvas**: Brings the web dashboard (:8889) to full parity with IndyDevDan's Pi UI—providing a live hierarchy tree of agents and sub-agents, dedicated real-time token/tool execution streaming windows, and human-in-the-loop guidance prompts.

---

## 2. Component Architecture

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

## 3. Detailed Component Designs

### 3.1. System 1 High-Frequency Triage Engine (`aq-triage`)
- **Ingestion & Cursors**:
  - Connects to systemd journald via `sd-journal` API or streaming wrapper.
  - Persists durable read cursor (`__CURSOR`) in atomic local SQLite store to survive service restarts.
  - Implements deterministic token-bucket rate limiter per subsystem to prevent event floods during cascade failures.
- **Classification Engine**:
  - Structured classification using lightweight local model or fast embedding + calibrated softmax head.
  - Outputs typed `TriageClassification` record (severity, incident_class, confidence, correlation_key).
  - P95 latency target: <200ms.

### 3.2. Durable Agent Runtime (`aq-durable`) & Effect Reconciliation
- **The Effect Sandwich Contract**:
  ```text
  PREPARED (Intent Logged with idempotency_key)
     │
     ▼
  EXECUTING (Tool Mutation Invoked)
     │
     ├─► Success ──────────────► COMMITTED (Receipt Persisted)
     │
     ├─► Known Failure ────────► FAILED_KNOWN (Error Recorded)
     │
     └─► Interruption/Crash ───► OUTCOME_UNKNOWN
                                      │
                                      ▼
                                 RECONCILING (Target State Inspected)
  ```
- **Tool Classifications**:
  1. *Class 1 (Read-Only)*: Idempotent (`cat`, `agrep`, `git status`). Replay is unconditionally safe.
  2. *Class 2 (Idempotent Overwrite)*: File writes with known target hash. Replay is safe.
  3. *Class 3 (Non-Idempotent External Mutation)*: Git push, external webhooks, process restart. Under `OUTCOME_UNKNOWN`, the reconciler queries git remote or service state to confirm whether the mutation landed before retrying or failing closed.
- **State Document Versioning**: Monotonic CAS (compare-and-swap) versioning prevents lost updates.

### 3.3. Autonomous On-Call Daemon (`aq-oncalld`) & Containment
- Runs as a systemd background service under user `hyperd`.
- **Sandbox & Containment**:
  - Confined to private git worktree (`.agents/delegation/worktrees/<id>`) via `scripts/ai/lib/worktree-isolation.sh`.
  - Ambient credentials (`GITHUB_TOKEN`, `SOPS_*`, SSH agents) scrubbed from sub-process environment.
  - AppArmor profile enforces directory containment and `rwk` lock permissions for SQLite.
- **Remediation Workflow**:
  - Controlled live reproduction.
  - Root-cause fix (Rule 19).
  - Validation: Tier-0 pre-commit gate (56 checks).
  - Independent review by an eligible distinct model lane (Rule 18).
  - Stages pull request with immutable candidate SHA hash binding (`candidate_sha256 = hash(tree + test_proofs)`).

### 3.4. Pi-Style Multi-Agent Streaming Canvas & Interaction Plane
To deliver parity with IndyDevDan's Pi Coding Agent UI interface, the Web Dashboard (:8889) and Switchboard (:8085) provide:

1. **Live Agent Mesh Hierarchy View**:
   - Visual tree rendering all currently active primary agents, on-call responders, and dynamically spun-up sub-agents.
   - Per-agent metadata chips: Role, assigned model (e.g. Qwen 3.6, Codex, Claude Sonnet), active worktree path, and live token usage.
   - Live lifecycle badge: `IDLE` (gray), `THINKING` (blue pulsing), `TOOL_EXECUTING` (amber), `AWAITING_INPUT` (purple), `DONE` (green), `ERROR` (red).
2. **Dedicated Streaming Execution Window**:
   - Tabbed / split-pane streaming views allowing the operator to inspect any agent in the mesh.
   - Real-time token streaming for model thoughts (collapsible reasoning block) and responses.
   - Live tool execution display: shows active tool name, invocation arguments, and live streaming `stdout`/`stderr`.
3. **Human-in-the-Loop Interaction & Guidance**:
   - **Mid-Flight Guidance Input Box**: Direct prompt input allowing the human operator to type guidance, answers, or corrections that inject into the agent's active turn.
   - **Step Approval & Gating Controls**: "Approve Step", "Deny / Abort", "Pause", "Resume" action buttons.
   - **One-Click Deployment Grant**: Ties into `aq-approve` for reviewing and merging staged on-call PRs.
4. **Real-Time Streaming Protocol (SSE)**:
   - Endpoint: `/api/v1/agents/{id}/stream` (Server-Sent Events).
   - Event Types:
     - `agent_spawned`: Parent-child relationship, role, and model parameters.
     - `thought_delta`: Streamed reasoning tokens.
     - `tool_call_start`: Tool name, parameters, idempotency key.
     - `tool_output_chunk`: Real-time stdout/stderr lines.
     - `step_committed`: Effect sandwich commit receipt.
     - `human_input_requested`: Halts agent loop until operator provides input.

---

## 4. Threat Model & Security Boundaries

1. **Credential Exfiltration via Agent Mesh**:
   - Workers spawned by `aq-oncalld` cannot read host `/run/secrets/`, `~/.ssh`, or ambient environment keys.
2. **Prompt Injection from Untrusted Logs**:
   - Malicious payloads in systemd logs cannot alter agent authority. Tool whitelists and path boundaries are enforced externally by the execution broker, not by LLM intent.
3. **Cascade Incident Flooding**:
   - Token bucket rate-limiter caps concurrent investigations at 3. Identical signatures are deduplicated across a 300-second window.
4. **Approval Drift Protection**:
   - Operator approval is bound to immutable git tree hash. Any subsequent commit automatically revokes the grant.

---

## 5. Delivery Slices & Implementation Roadmap

- **DP0 — Architecture, Schemas, and UI Specification Contracts**:
  - Finalize PRD, Design, and Tracker.
  - JSON schemas: `TriageClassification`, `DurableEffectSandwich`, `AgentStreamEvent`.
- **DP1 — System 1 High-Frequency Triage Engine (`aq-triage`)**:
  - Ingestion stream from journald with persistent cursor tracking.
  - P95 latency < 200ms benchmark. QA check `0.10.66`.
- **DP2 — Durable Agent Runtime Core (`aq-durable`)**:
  - Effect Sandwich middleware in `hybrid-coordinator` (:8003).
  - Idempotency store, CAS document updates, and crash-recovery simulation.
- **DP3 — Autonomous On-Call Daemon (`aq-oncalld`)**:
  - Background systemd daemon with worktree isolation and AppArmor containment.
  - Automated investigation, reproduction, Rule 19 logging, and PR staging.
- **DP4 — Pi-Style Multi-Agent Streaming Canvas & Interaction Plane**:
  - SSE streaming endpoint on Switchboard (:8085) and Dashboard backend.
  - Web UI: live agent hierarchy tree, streaming token/tool execution window, mid-flight guidance prompt, step approval buttons.
- **DP5 — End-to-End Incident-to-Canvas Verification & Activation**:
  - Simulated incident test -> triage -> on-call wakeup -> real-time UI streaming -> operator guidance -> Tier-0 verified PR.
  - Six-dimension Activation Definition of Done attestation.
