# Codex Expert Team Review: Durable Proactive On-Call Agent Mesh

## Executive Summary & Verdict

**Verdict: APPROVED_WITH_RECOMMENDATIONS for design refinement.**
**Overall score: 0.88 / 1.00. Confidence: 0.93.**

The proposal identifies critical architectural capabilities missing from the current harness:
1. Inexpensive, sub-second event triage (`aq-triage`).
2. Durable execution records surviving crashes (`aq-durable`).
3. Isolated on-call incident investigations (`aq-oncalld`).
4. Shared, multi-client operator visibility and human-in-the-loop control.

However, to be production-ready and fully aligned with harness rules, the implementation packet must resolve:
1. **Effect/receipt ambiguity in the Effect Sandwich**: When a mutation succeeds externally but the agent process crashes before persisting the receipt, local idempotency keys alone cannot determine whether the mutation occurred. We need an explicit `OUTCOME_UNKNOWN -> RECONCILING` state machine.
2. **Containment & Credential Boundaries**: Execution under `hyperd` must scrub ambient operator tokens, SSH agents, and cloud credentials, using AppArmor + bubblewrap + git worktree isolation.
3. **Independent Review & Subject-Bound Grants**: The incident lifecycle must include an explicit Independent Reviewer gate prior to PR staging, and operator deployment grants must bind to an immutable commit SHA.
4. **Multi-Agent Streaming UI (Pi Interface Parity)**: A unified Server-Sent Events (SSE) session streaming protocol delivering real-time agent/sub-agent tree state, live token/tool call streaming windows, and human-in-the-loop guidance/intervention.

---

## Section 1: Workflow Analysis & Recommended Improvements

### 1.1 Ingestion Cursor & Event Provenance
The classification schema must not rely on ephemeral log text. Ingest events with:
- Source identity and durable journald cursor (`__CURSOR`).
- Ingestion timestamp and normalized event hash.
- Correlation identity distinct from incident identity (to group cascading symptoms).
- Deduplication and flood rate-limiting (token bucket with per-subsystem backoff).

### 1.2 Remediation State Machine
Extend the linear lifecycle into a fault-tolerant state machine:
```text
INTAKE -> CORRELATE -> ADMIT -> CLAIM -> ISOLATE -> REPRODUCE
       -> DIAGNOSE -> FIX -> VALIDATE -> INDEPENDENT_REVIEW
       -> STAGE_PR -> AWAIT_OPERATOR -> ACTIVATION
```
Include explicit terminal/exception states: `BLOCKED`, `NOT_REPRODUCED`, `AWAITING_RECONCILIATION`, and `SUPERSEDED`.

### 1.3 Effect Sandwich with Reconciliation
Replace universal crash-safety assumptions with an explicit three-class effect contract:
- **Class 1 (Read-Only)**: Idempotent, safe to replay without side effects.
- **Class 2 (Idempotent Overwrite)**: Deterministic state write (e.g., file replace with known hash); replay is safe.
- **Class 3 (Non-Idempotent / External Mutation)**: Git push, external API calls, process restarts. If interrupted mid-flight:
  `PREPARED -> EXECUTING -> OUTCOME_UNKNOWN -> RECONCILING`
  The reconciler queries target state before deciding to retry, roll back, or escalate to the operator.

---

## Section 2: Roles & Authority Analysis

### 2.1 Role Separation & Non-Self-Review
Enforce strict separation:
- **System 1 Triage**: Classifies and proposes admission; has ZERO tool execution authority.
- **Orchestrator**: Dispatches roles, manages leases; never self-implements or self-reviews.
- **On-Call Implementer**: Bounded to assigned worktree; lowest eligible tier per Rule 17.
- **Independent Reviewer**: Evaluates exact candidate diff and test proofs; MUST be an independent model lane (Rule 18).
- **Human Operator**: Grants privileged deployment and activation actions.

### 2.2 Immutable Subject Binding
Operator approvals must bind to `candidate_sha256 = hash(git_tree + test_proofs)`. Any subsequent edit invalidates the approval and requires re-review.

---

## Section 3: Tools, Containment & Multi-Agent Streaming UI

### 3.1 Containment Architecture
- Confine on-call implementers within an unprivileged sandbox:
  - Writable access restricted to `.agents/delegation/worktrees/<id>/` and `/tmp`.
  - Scrub `GITHUB_TOKEN`, `SOPS_*`, SSH agent sockets, and live database admin credentials.
  - Apply AppArmor profile enforcing `rwk` rules and bubblewrap namespace isolation.

### 3.2 Pi-Style Streaming UI & Human-in-the-Loop Interaction
To match the IndyDevDan Pi Coding Agent UI interface:
- **Agent Mesh Tree View**: Expose live tree of all active agents and dynamically spawned sub-agents with status (`idle`, `thinking`, `tool_executing`, `awaiting_input`, `done`, `errored`), target worktrees, and token usage.
- **Real-Time Streaming Window**: SSE endpoint (`/api/v1/agents/{id}/stream`) emitting token streams, thinking blocks, active tool names, arguments, and live tool execution stdout/stderr.
- **Human-in-the-Loop Intervention**:
  - `POST /api/v1/agents/{id}/input`: Inject mid-flight human guidance or answers to agent queries.
  - `POST /api/v1/agents/{id}/pause` and `resume`: Pause/resume agent loop execution.
  - `POST /api/v1/agents/{id}/approve-step`: Step-by-step tool approval gate.
