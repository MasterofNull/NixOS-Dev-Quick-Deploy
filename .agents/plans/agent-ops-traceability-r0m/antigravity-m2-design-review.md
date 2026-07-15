# Antigravity Design Review: Agent Ops Traceability M2 Dispatch Enforcement

**Date**: 2026-07-15
**Reviewer**: Antigravity (Flagship Architecture, Security, and SRE Reviewer)
**Status**: `PASS` (Design Packet Approved; Implementation Remains Blocked)

---

## 1. Executive Summary & Verdict

We issue a formal **`PASS`** for the **Agent Ops Traceability M2 Dispatch Enforcement** design packet.

The proposed design addresses critical concurrency defects and enforces strict pre-launch visibility invariants. It correctly utilizes existing system surfaces (the `registry.jsonl` lifecycle store and the `TaskRegistry` library) without introducing unauthorized network or process-killing authorities.

> [!WARNING]
> This is a design-only review. M2 implementation remains **UNAUTHORIZED** until a hash-bound implementation packet is activated by the owner/orchestrator. M3 (live verification), local/inference reliability R1–R4, and owner Q8 decisions remain strictly **UNAUTHORIZED**.

---

## 2. Bounded Adjudication of Design Dimensions

### A. Inventory & Shared Authority
* **Library Boundaries**: Revising the R0M inventory to include `scripts/ai/aq-delegation-registry` and `scripts/ai/lib/task_registry.py` (totaling 17 files) is the correct boundary. It avoids duplicating lock and write operations across wrappers, ensuring a single entrypoint for registry mutation.
* **concurrency threats**:
  * Mandating a stable lock inode (`registry.jsonl.lock`) and prohibiting truncation before exclusive lock acquisition successfully prevents data loss.
  * Requiring atomic replacement (write to temp + rename), `fsync`, and parent-directory durability protects the registry against partial writes during crashes.
  * Performing read-validate-mutate-write under a single lock using record revisions (CAS) eliminates lost updates.
  * Strict path validation (rejecting symlinks/non-regular paths) protects against path-traversal exploits.

### B. Short-Lived Admission & PID Attachment
* **Queued State Tracking**: Implementing `queued` state visibility before PID attachment is secure under the proposed constraints:
  * Records must carry `admission_producer=dispatcher` to prevent untrusted legacy/forged writes.
  * The state is valid only within a short-lived grace window (e.g., 30 seconds); expired records fall back to `blocked/stale`.
* **Durable Attachment**: Requiring PID plus `/proc` start time for the `running` transition prevents spoofing via recycled PIDs.
* **Fail-Closed Exit Gating**: All wrapper routes must map launch errors, timeouts, zero-output exits, and signals to terminal, immutable states, preventing hung "running" processes.

### C. Data Hardening & Telemetry
* **Information Exposure**: Raw prompts, secrets, environment variables, and argv are strictly excluded from the registry. Only a safe task category class and `prompt_sha256` are recorded.
* **Telemetry Cardinality**: Metrics use closed enums (stable reason codes). PIDs, Task IDs, and prompt hashes are excluded from labels, preventing database card/metric bloat.
* **CLI Parity**: CLI flags `--status`, `--check`, and `--list` must output clean JSON with no trailing human-targeted prose.

### D. Retired Routes & Subagent Isolation
* **Gemini Deprecation**: The retired `delegate-to-gemini` route must fail closed immediately, returning a stable deprecation reason.
* **Subagent Routing**: Direct internal platform subagents and `aq-antigravity-agent` do not have an active registry bridge and must remain untracked/blocked until a separately reviewed lifecycle bridge is approved.

### E. Observability Parity
* The existing TUI/JSON structures and Phase-0 gates provide sufficient monitoring-first delivery. No web-dashboard UI modification is required for M2.

---

## 3. Recommended Inventory (17-File Limit)

We ratify the proposed 17-file inventory as the exact boundary for the future implementation:
1. `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PRD.md`
2. `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PLAN.md`
3. `config/schemas/agent-ops-projection.schema.json`
4. `scripts/ai/lib/agent_ops_projection.py`
5. `scripts/testing/test-agent-ops-projection.py`
6. `scripts/ai/aq-delegation-registry`
7. `scripts/ai/lib/task_registry.py`
8. `scripts/ai/delegate-to-local`
9. `scripts/ai/delegate-to-claude`
10. `scripts/ai/delegate-to-codex`
11. `scripts/ai/delegate-to-antigravity`
12. `scripts/ai/delegate-to-gemini`
13. `scripts/testing/harness_qa/phases/phase0.py`
14. `scripts/ai/_aq-qa-bash`
15. `config/validation-check-registry.json`
16. `docs/architecture/role-matrix.md`
17. `docs/operations/agent-ops-window.md`

---

## 4. Next Steps

1. **Complete Inbox Task**: Complete the inbox drop `agent-ops-traceability-m2-design-review.md`.
2. **Commit Stage**: Stage and commit this review document. Await owner/orchestrator activation of the M2 implementation phase.
