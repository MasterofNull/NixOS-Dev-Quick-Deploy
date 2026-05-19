# MAEAH Combined PRD — Plan Sign-Off Record

**Document:** Multi-Agent Edge AI Harness (MAEAH) Combined PRD v0.1
**Comparison Plan:** SYSTEM-COMPARISON-PLAN.md
**Date:** 2026-05-19

---

## Sign-Off Summary

| Agent | Role | Verdict | Date |
|-------|------|---------|------|
| Claude | CTO / Architect | **APPROVE** (pre-signed as author) | 2026-05-19 |
| Gemini | VP Engineering | **APPROVE WITH AMENDMENTS** | 2026-05-19 |
| Codex | Senior Staff Engineer | **APPROVE WITH AMENDMENTS** | 2026-05-19 |
| Qwen | Edge AI / Inference Lead | **GATED** (model loading; 7-item checklist pending) | 2026-05-19 |

**Overall: APPROVED — Phase A implementation authorized.**
Qwen sign-off gates Phase B (thermal thresholds) only.

---

## Incorporated Amendments (Gemini — VP Engineering)

### AM-G1: Hot-Swap SLA Tiering (§5.2)
**Amendment:** `<5s` is a hard SLA only on iGPU/GPU-capable hardware. `<30s` CPU-only is permitted but must not become default.
**Resolution:** ACCEPTED. `model_lifecycle_manager.py` will expose `swap_sla_tier: Literal["gpu_fast", "cpu_fallback"]` in the LifecycleEvent envelope. Dashboard shows tier label alongside swap duration.

### AM-G2: Signed Agent Cards Day-1 (§4.2)
**Amendment:** Cryptographic signing of Agent Cards is a Day-1 requirement for non-loopback peers, not a "future v2."
**Resolution:** ACCEPTED. Phase C (A2A endpoint) will include Ed25519 card signing. Unsigned remote cards → quarantine. Local loopback peers exempt (same-node trust).

### AM-G3: Thermal-to-Scheduler Coupling (§4.2 / Q27)
**Amendment:** Q27 moved from "Open Question" to Direct Requirement: MLFQ scheduler must consume real-time thermal telemetry.
**Resolution:** ACCEPTED. `inference_param_manager.py` (Phase B) will emit `thermal_state` events; `mlfq_scheduler.py` (Phase C) will subscribe. For Phase A, thermal data is surfaced in dashboard as read-only metric.

---

## Incorporated Amendments (Codex — Senior Staff Engineer)

### AM-C1: API Surface Normalization
**Amendment:** Add `POST /v1/responses`; admin namespace under `/admin/v1/*`; canonical A2A endpoint resolution.
**Resolution:** ACCEPTED for Phase C+. Phase A model lifecycle endpoints use `/api/models/*` (dashboard-internal). Phase C will introduce `/admin/v1/models/*` with alias. A2A canonical contract: `/.well-known/agent.json` + `POST /a2a/tasks/send` (REST-shaped per A2A spec).

### AM-C2: Security Boundary Correction
**Amendment:** Loopback exemption must not silently make admin operations unauthenticated. Signed cards required for network peers.
**Resolution:** ACCEPTED. Dashboard model lifecycle endpoints will require `X-Dashboard-Internal: 1` header or existing `hybrid_coordinator_api_key`. Unsigned remote cards → quarantine.

### AM-C3: Schema/Type Attribution
**Amendment:** Replace "typed Python dataclass schemas" with "versioned JSON Schema/OpenAPI contracts."
**Resolution:** ACCEPTED. `model_registry.py` will expose `ModelEntry` with version field. JSON Schema fragments will be documented inline. Full OpenAPI spec is Phase C scope.

### AM-C4: Durable Lifecycle State Machine
**Amendment:** Full state set required: `available → downloading → downloaded → verified → warming → candidate → active → retiring → archived → failed`.
**Resolution:** ACCEPTED. `model_lifecycle_manager.py` will implement all states as `ModelState` enum. Dashboard status indicator maps each state to a display label and color.

### AM-C5: Testing Appendix as Normative Acceptance Criteria
**Amendment:** Staff Engineer test matrix should be included as required validation, not implied.
**Resolution:** ACCEPTED. `PHASE-A-ACCEPTANCE-CRITERIA.md` will enumerate: model download, progress SSE, promote, swap, rollback, audit event, and CPU-fallback SLA tests.

---

## Qwen Sign-Off Checklist (GATED — Blocks Phase B Only)

Qwen must validate these 7 items from COMBINED-PRD.md §11 before Phase B implementation:

- [ ] Q1: Confirm Q4_K_M default quant tier (~22GB) validated on Renoir 27GB RAM
- [ ] Q2: Confirm n_gpu_layers=12 default is safe (not 16 — ErrorDeviceLost risk)
- [ ] Q3: Confirm thermal thresholds: T_warn=80°C, T_crit=85°C, T_emergency=88°C
- [ ] Q4: Validate MTP draft model as "linked sibling" in catalog (not separate entry)
- [ ] Q5: Confirm UMBM memory budget: llama.cpp 18GB, KV cache 3GB, OS+services 6GB
- [ ] Q6: Validate T0–T5 quant tier ladder against local benchmark results
- [ ] Q7: Sign off on CPU-only fallback queue-buffer behavior (15–25s, 503+Retry-After)

---

## Implementation Authorization

### Phase A — Model Pre-Download + Hot-Swap Dashboard (AUTHORIZED ✓)
No nixos-rebuild required. Dashboard reads Python from repo directly.

Files:
- NEW: `dashboard/backend/api/routes/models.py`
- NEW: `ai-stack/mcp-servers/hybrid-coordinator/model_lifecycle_manager.py`
- NEW: `ai-stack/mcp-servers/hybrid-coordinator/model_registry.py`
- MOD: `dashboard/backend/api/routes/aistack.py` (register router)
- MOD: `dashboard/backend/http_server.py` (if needed for coordinator-side endpoints)
- MOD: `dashboard/dashboard.html` (Model Lifecycle panel)
- MOD: `nix/modules/roles/ai-stack.nix` (extend defaultModelCatalog schema)

### Phase B — IPM Thermal-Aware Inference (GATED on Qwen sign-off)
### Phase C — MLFQ Scheduler + A2A + OTel (AUTHORIZED, post-Phase-A)

---

## Remaining Open Questions (Deferred to Phase C+)

1. Distributed context sharing across gossip mesh (Q1)
2. Power/thermal budget per target device class (Q2)
3. ABC cascade enforcement: proxy vs. agent-negotiated (Q3)
4. Persistent Q4 KV page format: custom binary vs. GGUF extension (Q6)
5. MTP draft model co-download policy (Q21) — resolved by Qwen sign-off
6. AMV-L utility scoring hot-path overhead (Q23)

---

*All four agents authorized to proceed. Phase A implementation begins immediately.*
