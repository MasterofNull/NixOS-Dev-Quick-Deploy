# PRD: Project 'Health Spider' (Autonomous Telemetry Mesh)

**Status:** Draft
**Goal:** Implement stochastic, resource-aware system health sampling to drive autonomous, full-cycle remediation.

---

## 1. The Spider Engine (HealthSpider)
A background service that orchestrates telemetry sampling and remediation.

### 1.1 Stochastic Sampling Strategy
*   **Weighted Hotspots**: Sample areas with higher error rates/log volume (e.g., specific services or endpoints) more frequently.
*   **Non-Repeat Randomization**: Uses a deterministic seed (timestamp-based) to select samples, ensuring comprehensive coverage without redundant checks in a single pass.
*   **Resource Awareness**: Adaptive sampling interval based on `CPU/Memory` pressure (if load > 80%, reduce sample frequency).

### 1.2 Life Cycle Contract: The 'Fix-Loop'
Any anomaly detected triggers the **Standardized Remediation Contract (SRC)**:
1.  **Orient**: Collect bounded evidence (logs, telemetry, local state).
2.  **RCA (Root Cause Analysis)**: Architect analyzes evidence; produces `RCA.md`.
3.  **Plan**: Architect produces execution `PLAN.md`.
4.  **Execute**: Coder implements the full-fledged fix.
5.  **Validate**: Tester re-runs the specific failing test/path + Regression suite.
6.  **Record**: Audit trail written to `.reports/remediation/`.
7.  **Commit**: Atomic, verified commit.

---

## 2. Technical Requirements

### R1: Hotspot Identification
*   New endpoint: `/api/telemetry/hotspots` (returns service/code-path metrics).
*   Spider uses this data to prioritize "high-risk" zones for sampling.

### R2: Life Cycle Standard (S.L.C)
All remediation tasks MUST follow the lifecycle above. Any deviation (e.g., skipping validation) is a critical failure.

### R3: Anomaly Detection
*   Integrate `aq-qa` logs and `prsi` status to identify:
    - Missing/Blank data patterns
    - Corruptions
    - Latency spikes
    - Failing validation gates
