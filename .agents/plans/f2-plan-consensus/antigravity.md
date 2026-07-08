# Antigravity Review — F2 Implementation Plan Consensus

## Verdict: APPROVE_WITH_CHANGES

The division between Phase-A (pure Python, offline testable) and Phase-B (rebuild-dependent model-residency/Nix infrastructure) is highly appropriate. However, the constraints of the 4GB shared VRAM APU substrate must be made explicit.

---

## 1. APU Hardware Constraints and VRAM Pool Swap Cost
On the Renoir APU system (4GB shared VRAM), memory thrashing is a critical hazard:
- **Resident small models + 35B**: There is zero headroom for simultaneous residency. The 35B model MUST run in a dynamic session-based load/unload model.
- **Cooling/Swap Gate**: Swapping models (loading/unloading GGUFs) can cause 30–60 second latency spikes. The VRAM Pool Manager must enforce a strict cooling-period lock to prevent thrashing when multi-agent dispatches overlap.
- **35B-on-CPU (n_gpu_layers=0)**: We support gating this as a Phase-B measurement. Offloading layers to system RAM instead of VRAM will degrade tok/s but frees VRAM for the concurrent small resident models on port `:8082`. This trade-off must be measured.

---

## 2. MLFQ Aging & Back-Pressure Logic
- **Hard Starvation Bounds**: For F2.1, the aging promote rule should use a concrete upper bound (e.g. `max_wait_seconds = 180`) rather than only incremental adjustments, ensuring low-priority jobs (like general telemetry analysis) eventually get slot allocation within a predictable window.
- **local-delayed Quorum Block**: In F2.3, the `local-delayed` status must be a typed terminal indicator. The F1 consensus engine must respect this, keeping the round in an open stage until the local execution slot completes, rather than timing out and executing consensus without local contribution.

---

## 3. GBNF Cache Key Stability
The cache key in F2.2 must be canonically serialized to prevent collisions. We recommend:
`sha256(canonical_json(schema) + ":" + canonical_json(zero_trust_policy))`

---

## 4. Top 3 Required Changes
1. **Explicit Starvation Bounds**: Implement a strict `max_wait_seconds` threshold in the MLFQ queue scheduler to prevent background tasks from starving infinitely.
2. **Canonical Cache Key Serialization**: Enforce deterministic salt and concatenation patterns for the GBNF cache key hashing.
3. **Isolate Phase-A Code**: Guarantee that all Phase-A scheduler work resides inside `scripts/ai/lib/` and remains entirely decoupled from deployed system services until Phase-B.
