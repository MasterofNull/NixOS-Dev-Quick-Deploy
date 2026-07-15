# Antigravity Design Review: Agent Ops Traceability (R0M)

**Date**: 2026-07-15
**Reviewer**: Antigravity (Flagship Architecture, Security, SRE, and Observability Reviewer)
**Status**: `PASS` (M0 Authorized; M1–M3 Blocked Pending L2B-A Resolution)

---

## 1. Verdict & Operational Directives

We issue a **`PASS`** verdict for the **Agent Ops Traceability R0M** Design Review.

### Operational Directives
* **R0 Re-Ratification**: **RE-RATIFIED.** We mathematically confirm that none of the five executable R0 assets changed during administrative closure. The R0 documentation changes in the PRD and PLAN are purely status projection updates and comply with the freeze rule.
* **M0 Slice Authorization**: **YES.** The implementation of the **M0 slice** (pure projection contract: closed schema, pure bounded readers/classifiers, and golden fixtures) is authorized to begin.
* **M1–M3 Slice Status**: **BLOCKED.** Slices M1–M3 remain blocked until the staged L2B-A candidate is fully merged or safely isolated by an owner-approved staging strategy, preventing overlapping changes on shared dashboard and QA assets.
* **R1–R4 Slices Status**: **UNAUTHORIZED.** Run-loop execution modifications (R1–R4) remain strictly unauthorized.

---

## 2. Threat-Model & Security Evaluation

| Threat Vector | Evaluation & Fail-Closed Guardrails | Score |
| :--- | :--- | :---: |
| **Source Authority** | Projector is read-only; conflicts between registry, process state, or inbox result in `conflict` or `stale` states that fail closed to `blocked` or `degraded`. | **10/10** |
| **PID Reuse & namespaces** | Process validation requires the PID start-time tuple from `/proc/<pid>/stat` combined with cgroup tracking, preventing stale registry rows from matching recycled PIDs. | **9.5/10** |
| **`/proc` Permission Loss** | Projector treats missing or permission-denied `/proc` handles as untracked anomalies, marking the target `blocked` rather than assuming nominal status. | **9.5/10** |
| **Argv Spoofing** | Projector parses `/proc/<pid>/cmdline` array boundaries instead of substring matches, preventing process name spoofing. | **10/10** |
| **Ancestry Deduplication** | Ancestry and cgroup-hierarchy tracking collapses nested bwrap/sandbox wrappers and children into a single work unit, eliminating card duplication. | **9.5/10** |
| **Heartbeat & Telemetry Forge** | Progress validator rejects sequence-drifted or forged progress sidecars. Heartbeats without a corresponding progress lease are invalidated. | **10/10** |
| **Exposure of Secrets & Prompts** | Bounded low-cardinality metric names prevent leakage of prompts, commands, paths, or keys into Prometheus labels or console TUIs. | **10/10** |

---

## 3. Inventory Minimalist & Sufficiency Analysis

The proposed **16-file inventory** is sufficient and minimal. It covers the schema, projection logic, golden fixtures, dashboard TUI integration, validation checks, and delegation wrappers.

### Staging Strategy Validation
- **M0 Independence**: The M0 slice creates only *new* files (`agent_ops_projection.py`, `agent-ops-projection.schema.json`, etc.) that have zero overlap with the staged L2B-A candidate files. Thus, M0 is completely safe to run.
- **M1–M3 Block**: Shared assets (`aq-tui-dashboard`, `phase0.py`, etc.) overlap with the staged L2B-A candidate. Blocking M1–M3 until L2B-A is integrated ensures git conflict cleanliness.

---

## 4. Recommended Amendments & Missing Fixtures

### A. Telemetry & Metric Additions (R0M)
1. **`inbox_pending_count`**: Track the size of the Antigravity inbox to measure operator/lane queue backlogs.
2. **`inbox_processing_duration_seconds`**: Measure latency from task drop to archiving.
3. **`cgroup_correlation_failures_total`**: Track occurrences where process ancestry is found but cgroup mappings are missing or corrupt.

### B. Missing Adversarial Fixtures
1. **`/proc` Permission Denial Simulation**: Fixtures must simulate a `/proc` access failure (e.g., `PermissionError`) and verify that the projector defaults to `UNTRACKED / blocked` rather than crashing.
2. **PGID / Session Leader Drift**: Add a test case where a process forks, changes its process group, and escapes parent ancestry, verifying that cgroup grouping still successfully deduplicates it.
