APPROVED (with Q2 threshold tightening & KISS scope focus)

Reviewers:
- `Simurg@local/qwen#local-20261113-184833-6db4tv` (`VERDICT APPROVED`)
- `Simurg@local/qwen#local-20261113-184559-utr1pk` (`CONCERNS` on Q2 loadavg threshold)

### 1. Answers to Open Questions (§5 Q1–Q3)
- **Q1 (`aq-context-packet` 2,500-token ceiling)**: **APPROVE.** Enforcing the 2,500-token hard ceiling via AST signatures + line ranges prevents context overflow on the 8k local window and preserves high-signal guidance without noise.
- **Q2 (Laptop thermal, battery & load guard)**: **REVISE / TIGHTEN.** Gating neural `llama.cpp` tasks on AC power (or battery >= 50%) is sound, but `0.70 * cpu_count` is too permissive on a 12-GPU-layer laptop where thermal throttling begins earlier; tighten to `0.40 * cpu_count` (or `/proc/loadavg` <= 2.0) and CPU temp `< 75°C–80°C`. Keep sub-20ms CPU checks lightweight.
- **Q3 (Secret scrubbing & CLI-direct owner gate)**: **APPROVE.** Mandatory redaction via `telemetry_privacy.py` across `(context_packet, rejected_attempts, verified_diff)` and CLI-direct owner sign-off before any external publication are non-negotiable.

### 2. Local Model Perspective on F1–F5 Deliverables (What Actually Helps Local First-Pass Success)
- **Directly Helpful**: **`F1` (`aq-context-packet`)** is critical—the deterministic context packet is the primary input mechanism that lets local Qwen succeed within its 8k token limit. **`F3` (exemplar & intent routing)** helps once real receipts exist.
- **Defer / Strip for KISS**: Dashboard cards and broad OS telemetry overhead do not directly improve local first-pass code generation; keep the MVP focused on `aq-context-packet`, the pre-review `tier0` gate, the local thermal/power guard, and simple receipt counting.
