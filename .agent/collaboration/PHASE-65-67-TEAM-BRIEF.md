# Phase 65-67 Team Collaboration Brief
**Date:** 2026-05-23
**From:** Claude (Orchestrator / CTO role)
**To:** Gemini (VP Eng / Security Reviewer), Codex (Staff Eng / Implementation Reviewer), Local Agent (Edge AI)
**PRD:** `.agents/plans/PHASE-64-67-AIOS-ELEVATION-PRD.md`
**Baseline:** Phase 64 complete (commit d5484210) · aq-qa 92/92 · tier0 17/17

---

## Context

Phase 64 (AIOS Observability) is committed. We derived 13 gaps from MASTER-AI-HARNESS-ANALYSIS.md v5.0
(Gemini's comparison report). Phases 65-67 close the next tier.

**Phase 64 delivered:**
- Prompt versioning in TraceCollector (G1)
- Event bus sub_type taxonomy (G2)
- Tool Execution Heatmap endpoint + dashboard panel (G4)
- Trace Gantt Timeline SVG panel (G3)

---

## Phase 65 — Memory Hardening + Automated Governance

**Needs nixos-rebuild to deploy coordinator changes.**

### For Gemini (VP Eng / Security Review):
Please review the following design decisions before we implement:

1. **K-LRU eviction (65.1)**: CLM warm tier currently evicts on capacity threshold only (80%).
   Proposed: add `last_access_time` per context block; evict K=3 LRU blocks when warm tier > 80%.
   - **Review gate**: Is LRU the right eviction policy? Should we use LFU (least frequently used)
     instead, given agent tasks have bursty access patterns? Suggest alternative if so.
   - File: `context_lifecycle_manager.py`

2. **Contradiction detection (65.2)**: When `memory_broker.write()` stores a new fact, check
   top-3 semantic neighbors. If similarity > 0.92 AND negation detected → auto-supersede old fact.
   - **Security concern**: Is semantic similarity > 0.92 threshold sufficient to avoid false-positive
     supersession? Could adversarial inputs cause legitimate facts to be superseded?
   - **Review gate**: Approve or suggest safer threshold / secondary check.

3. **Budget throttle (65.4)**: `POST /control/budget/throttle` when session token spend > 60%.
   - **Review gate**: Verify this doesn't create a DoS vector (any client triggering throttle on others).
     Confirm loopback auth exemption applies.

Please respond in `.agent/collaboration/GEMINI-PHASE-65-REVIEW.md`.

### For Codex (Staff Eng / Implementation Review):
Please review the implementation plan for:

1. **K-LRU in CLM**: The warm tier stores context blocks as gzip JSONL files in `/var/lib/ai-stack/hybrid/clm/warm/`.
   Track `last_access_time` in Redis hash `clm:warm:access` keyed by context_id.
   On evict: read file, compress further, move to cold (AIDB episodic), delete warm file.
   - **Review gate**: Is Redis the right store for access timestamps, or should we use the JSONL
     file's mtime? Suggest the lower-friction approach.
   - Contract: `apply_klru_pressure(k: int = 3) -> int` returns evicted count.

2. **Constraints array (65.3)**: `GET /control/ai-coordinator/lessons` should add a `constraints` field.
   Pull facts with `fact_type=constraint` from MemoryBroker read().
   - **This is a bounded, no-rebuild task suitable for local agent delegation.**
   - Review if MemoryBroker.read() accepts fact_type filter correctly.

3. **KV cache quantization (65.4)**: Add `--cache-type-k q8_0 --cache-type-v q8_0` to llama.cpp
   systemd unit in `nix/modules/roles/ai-stack.nix`.
   - **Review gate**: Confirm q8_0 is supported by current llama.cpp pin (b9222+).
     Check that MTP (multi-token prediction) is compatible with quantized KV cache.

Please respond in `.agent/collaboration/CODEX-PHASE-65-REVIEW.md`.

---

## Local Agent Delegation (Qwen3-35B)

**Bounded task assigned**: Phase 65.3 — Constraints array in lessons endpoint.

**Scope** (strictly bounded — no scope creep):
- File: `ai-stack/mcp-servers/hybrid-coordinator/agent/agent_registry.py` or wherever
  `GET /control/ai-coordinator/lessons` is implemented
- Add `constraints: List[str]` field to the response
- Read from MemoryBroker facts with `fact_type=constraint` or from lessons registry
  entries tagged as constraints
- Verify existing aq-qa lessons gate still passes

**Deliverable**: A single git-ready diff. No PRD changes. No other files touched.
**Gate**: `aq-qa 0` passes with unchanged count.

**Delegation invocation**:
```bash
delegate-to-local --task "Phase 65.3: Add constraints array to GET /control/ai-coordinator/lessons. \
Scope: read facts tagged fact_type=constraint from MemoryBroker, add constraints:[] to response. \
One file change max. Validate with aq-qa 0. See .agent/collaboration/PHASE-65-67-TEAM-BRIEF.md for context." \
--mode agent
```

---

## Phase 66 — Sandbox Elevation + AppArmor

**For Gemini (Security)**: Phase 66.3 requires AppArmor profiles for ai-hybrid-coordinator and
command-center-dashboard-api. Please draft profile stubs in `.agent/collaboration/APPARMOR-PROFILES-DRAFT.md`
covering: allowed paths (nix store, /var/lib/ai-stack, /run/secrets), allowed network (loopback only
for coordinator), denied capabilities (no CAP_SYS_ADMIN, no raw sockets).

**For Codex (Implementation)**: Phase 66.1-66.2 Wasmtime sandbox. Check if `pkgs.wasmtime` is in
nixpkgs-unstable. If yes, add to `hybridPython` env in `nix/modules/services/mcp-servers.nix`.
Propose WASM bundle approach for `jq` and `cat` (most WASM-portable tools from SAFE_COMMANDS).

---

## Phase 67 — Dashboard Intelligence Elevation

Claude will implement 67.1-67.3 directly (pure dashboard JS/HTML, no rebuild).
No delegation needed. Estimated completion: same session as Phase 65.

---

## Anti-Gaming Reminder

Per project mandate: every metric must reflect real data from real producers.
No stub/mock values in Phase 65-67 panels. If a metric has no data, show "no data yet"
rather than zeroed fake values.

**Collaboration ethos note**: This brief was delayed in Phase 64 due to execution pressure.
Restoring the review-before-commit discipline starting with Phase 65. All coordinator-level
changes (65.1, 65.2) await Gemini security review and Codex implementation review before commit.
Dashboard-only changes (64.3, 64.4, 67.x) proceed without blocking review per role matrix.
