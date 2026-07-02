---
title: Local inference scaling — adaptive budget + complexity routing + embed offload
status: PLANNED
owner: hyperd
author: claude-sonnet-4-6
created: 2026-07-02
scope: ai-stack/switchboard/switchboard.py, ai-stack/mcp-servers/hybrid-coordinator/{intent_classifier.py,model_coordinator.py,inference_param_manager.py}
---

# Objective

Make the local lane "scale" as far as the Renoir APU physically allows, and route
what it can't handle to lanes that scale (remote Gemini + the underutilized embed
server). Local hardware is maxed: Qwen3.6-35B Q5, 12 GPU layers (APU ceiling),
`--parallel 1`, MTP spec decoding already on, RAM already swapping (~14 GB). No knob
adds same-model concurrency; the wins come from routing and idle-capacity use.

User decision (2026-07-02): do A + B + embed-offload. NOT C (second local gen model)
— RAM is already swapping.

# Grounding (verified anchors)

- Local ceiling injection: `switchboard.py:2440 _apply_local_thinking_profile()` — already
  early-returns for `target_type != "local"` (line 2444), so remote is ALREADY isolated
  from local ceilings. Forces `enable_thinking=False` for local unless profile contains
  "reasoning".
- Local slot gate: `switchboard.py:2651 _local_sem = asyncio.Semaphore(LOCAL_CONCURRENCY)`;
  `LOCAL_CONCURRENCY` from `SWB_LOCAL_CONCURRENCY` (default 1) at line 634.
- Routing classifier: `intent_classifier.py:620 classify_routing(query, intent, tool_count_hint)`
  → RoutingClass. Tier SSOT: `config/model-coordinator.json` tiers + tier_routing.
- Embed server: `inference_param_manager.py:113` already polls embed:8081 slots (runs
  `--parallel 4`, ctx 4096) — 4 parallel slots, generation slot is separate.

# Phase A — complexity → lane routing (highest ROI, software-only)  [IMPLEMENTED flag-gated 2026-07-02]

STATUS: implemented behind `AI_COMPLEXITY_LANE_ROUTING` (default off) in
extensions/model_coordinator.py `classify_and_route` + pure helper
`_complexity_preferred_lane` (unit-tested: scripts/testing/test-complexity-lane-routing.py,
10 cases). When the caller has not forced prefer_local, heavy complexities
(complex/critical/architecture) bias to remote candidates (scale natively), bounded
(trivial/simple/medium/unknown) bias to local — only NARROWS candidates when a matching
lane exists, never forces an unavailable lane. LIVE-VALIDATE after the Gemini remote lane
is up (needs the rebuild) so remote candidates actually exist, then flip the flag on.


Route heavy work to remote (scales natively), keep local for bounded tasks.

1. In `classify_routing()` (or the coordinator's route decision), map task complexity
   (trivial|simple|medium|complex|critical from the intent classifier) through
   `model-coordinator.json tier_routing` to a lane:
   - complexity >= complex  → remote (tiers.google flagship = gemini-3.1-pro)
   - complexity <= medium   → local (qwen3.6-35b, bounded)
2. Respect explicit route hints and `remoteBudget.fallbackToLocal` (already present).
3. Gate on remote availability (post-Gemini-rebuild); fall back to local if remote down.

Acceptance: a `--task-type deep_reasoning` / long-context task routes remote; a bounded
edit/lookup stays local. Verify via coordinator route logs + `aq-qa` routing checks.

# Phase B — adaptive local thinking budget (idle-capacity use)  [IMPLEMENTED flag-gated 2026-07-02]

STATUS: implemented behind `SWB_ADAPTIVE_LOCAL_BUDGET` (default off) in
switchboard.py `_apply_local_thinking_profile` + pure helper `_adaptive_local_output_budget`
(unit-tested: scripts/testing/test-switchboard-adaptive-local-budget.py, 9 cases).
Mechanism landed: LOCAL reasoning requests get max_tokens clamped by slot state —
`_local_sem.locked()` (idle→SWB_ADAPTIVE_LOCAL_IDLE_MAX_TOKENS 1200; busy→
SWB_ADAPTIVE_LOCAL_BUSY_MAX_TOKENS 400). Non-reasoning and remote unaffected; caller's
smaller max_tokens always respected. LIVE-VALIDATE at next switchboard rebuild, then flip
the flag on. Note: the "budget" is per-profile max_tokens (there is no separate
thinking_budget constant in switchboard); enable_thinking stays False for non-reasoning.


Let a lone local task think deeper when nothing else is queued; clamp under contention.

1. Extend `_apply_local_thinking_profile(payload, profile, target_type)`:
   - Read current local slot pressure from `_local_sem._value` (or a shared counter).
   - If slot idle (no waiters) AND profile is reasoning/deep: allow `enable_thinking=True`
     with a bounded `max_tokens`/thinking budget (e.g. 1024) instead of hard-off.
   - If contended (waiters present): keep `enable_thinking=False` / budget ~200.
2. Keep the hard default OFF for non-reasoning profiles (protects against drift).
3. Never applies to remote (early-return at 2444 already guarantees this).

Acceptance: idle deep task gets larger budget; under 2+ queued tasks, budget clamps.
No slot lock > configured ceiling. Regression test in scripts/testing/.

# Phase C — offload embedding-amenable work to embed:8081 (4 slots)

The embed server has 4 parallel slots and does only embeddings — use it for work that
can be reframed as embed+similarity instead of blocking the single generation slot.

Candidates to route to embed model:
- Semantic search / RAG retrieval (already there for Qdrant)
- Dedup / near-duplicate detection, clustering
- Semantic routing / intent pre-classification by nearest-centroid
- Rerank by cosine similarity (vs generative rerank)
- Gap/drift scoring already using embeddings (`drift_analyzer.py`)

1. Inventory current generation-model calls that are really similarity/classification
   and can use embeddings instead.
2. Route those through the embed endpoint (parallel=4) — frees the gen slot.
3. Confirm embed KV/VRAM headroom (embed uses separate 12-layer budget).

Acceptance: embedding-amenable ops no longer occupy the gen slot; embed:8081 slot
utilization rises under mixed load; gen-slot queue depth drops.

# Risk / testing

- Core inference path — changes affect ALL local requests. Test each phase in isolation
  on the running stack (aq-qa 0, delegate-to-local smoke) before the next.
- RAM already swapping: do NOT add a second generation model (Phase C is embed-only, no
  new model load).
- Batch any rebuild to end-of-cycle review (automation-first).

# Execution note

Suited to phased execution with cross-agent review (the routing changes benefit from a
reviewer verdict). Can run via aq-loop --intent per phase, or delegate-to-antigravity
(reviewer) after each slice.

# Rust rewrite coordination (user flag 2026-07-02) — READ BEFORE IMPLEMENTING

Codex is running a Python→Rust rewrite of key agent implementations. Current state:
- New workspace at repo root: `Cargo.toml` + `crates/` (untracked, Codex-owned WIP).
- First crate: `crates/contract-validator` (package `harness-contracts`) — porting
  GOVERNANCE/CONTRACT validation (memory-surface registry, cross-surface contract,
  active-memory reference paths). Declares canonical hot memory at
  `ai-stack/agent-memory/MEMORY.md` (ties to the memory-hot-index-ssot-missing discovery).
- Codex has WIP edits to flake.nix, options.nix, mcp-servers.nix, validation-check-registry.json,
  AGENTS.md, README.md, WORKFLOW-CANON.md, skills — wiring the Rust crate into the gates.

Implications for THIS plan:
1. NO current collision — the Rust port targets governance/contracts, not the inference
   path (switchboard.py / intent_classifier.py / inference_param_manager.py) this plan edits.
2. The Python→Rust pattern will likely reach switchboard/coordinator next. Before starting
   any phase, re-check whether the target file has been ported to a crate; if so, implement
   the logic in the Rust crate, not the Python file.
3. Do NOT touch Codex's `crates/`, `Cargo.*`, or its uncommitted Nix wiring — that is the
   other agent's in-flight slice. Coordinate ordering via PULSE/HANDOFF before Phase A/B.
4. If governance gates flip to the Rust validator mid-implementation, expect stricter
   memory-surface checks (canonical `ai-stack/agent-memory/MEMORY.md`).
