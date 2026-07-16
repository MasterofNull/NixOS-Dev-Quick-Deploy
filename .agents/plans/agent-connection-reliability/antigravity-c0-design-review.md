# Antigravity Design Review: Agent Connection Reliability C0 Design

**Date**: 2026-07-16
**Reviewer**: Antigravity (Flagship Architecture, Security, and SRE Reviewer)
**Status**: `PASS` (C0 Design Approved; Single-Use C0 Contract-Only Grant May Be Prepared)

---

## 1. Executive Summary & Verdict

We issue a formal **`PASS`** for the **Agent Connection Reliability C0** design packet (`C0-DESIGN-PACKET.md` at SHA-256 `f6b5acee94e254ef2a9fab332a4f50bfe6a0322142e234a35e892f26c18ddccb`).

The C0 design successfully addresses the structural connection/process lifetime defects that previously caused Fable task failures under sandboxed caller termination. By shifting from caller-owned `nohup` processes to a host-side, socket-activated broker, and establishing pure, closed schemas, the design provides a resilient foundation for durable execution without creating competing lifecycle authorities.

---

## 2. Detailed Architectural Adjudications

### A. Host-Side Socket Broker vs. Caller-Owned Nohup
* **Adjudication**: Moving task execution and supervision to the host-side `aq-dispatchd` daemon is the correct architectural solution. Sandboxed agents run in restricted environments (namespaces, cgroups, cgroups-limits) which are torn down upon caller parent exit; caller-owned background processes (`nohup`/`disown`) cannot survive this. A systemd socket-activated daemon on the host completely decouples the provider execution lifecycle from the sandboxed caller process tree.

### B. Unix Peer Security Boundary & Same-User Threat
* **Adjudication**: Using `/run/aq-dispatchd.sock` with `SO_PEERCRED` provides safe local identification (lane, role, access class) for sandboxed callers. The PRD correctly acknowledges the same-user residual threat—since peer agents run under the same host Unix account, they share repository and socket write access. Peer credentials function as an access-control boundary, not cryptographic zero-trust authentication; this boundary remains valid until the future state-spine credentials design.

### C. Registry Spine Reuse
* **Adjudication**: Reusing the existing `registry.jsonl` file as the single source of truth for the lifecycle state spine avoids state-synchronization bugs. C0 introduces no new conflicting storage engines or database systems.

### D. Adapter Contracts and Replay Safety
* **Adjudication**: The pure adapter interface is cleanly defined. Fencing epochs, CAS revision tracking, and lease ownership prevent concurrent execution conflicts. The restart policy for uncertain active tasks correctly defaults to evidence-based checking rather than blind respawns, eliminating double-starts.

### E. Failure Classification & intended-lane Resume
* **Adjudication**: The taxonomy separates transient errors from quota-parked states. Parked tasks preserve their intended-lane and retry epoch, returning to queue only through a controlled scheduling pass, rather than silently falling back to weaker or unauthorized model tiers.

### H. Scope and Sequencing
* **Adjudication**: The 11-file inventory is pure and minimal, focusing strictly on contracts, schemas, and test fixtures without editing wrappers. The step-by-step sequencing (C0 contract -> C1 fake provider -> C2 canary -> C3 individual adapters -> C4 park/resume -> C5 cutover) is a logical, low-risk deployment path.

---

## 3. Next Steps

1. **Complete Inbox Task**: Complete the inbox drop `agent-connection-reliability-c0-design-review.md`.
2. **Authorize C0 Contract Preparation**: A single-use, hash-bound C0 contract-only grant (limited strictly to the 11-file inventory) may be prepared for owner activation. C1–C5, M2B, and R1–R4 remain strictly unauthorized.
3. **Commit Stage**: Stage and commit this review document.
