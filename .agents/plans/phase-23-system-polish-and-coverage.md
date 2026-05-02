# Phase 23 — System Polish, Coverage, and Observability

Status: `in_progress`
Created: 2026-05-02
Owner: Claude (orchestrator/implementer)
Predecessor: Phase 22 (Eval Recovery + Fleet Resilience — all core tasks done)

---

## Objective

Three-part polish cycle targeting the remaining gaps identified in the Phase 22 aq-report:

1. **Continuation downshift coverage** — fix over-restrictive dual-gate (0/8 → target ≥4/8)
2. **Hint diversity** — expand hint tracking to /query synthesis path (P22-004 done)
3. **Cache warming** — seed continuation-style query patterns for downshift path

Signal baseline (2026-05-02):
- aq-qa: 39 passed / 0 failed / 1 skipped (0.8.1 insufficient sample)
- Cache hit rate: 28% (25 samples, still warming)
- Continuation downshift: 0/8 coverage (root cause: dual resume_markers gate)
- Hint injections: 1/7d (aider-wrapper only, coordinator volume untracked)
- Delegate reliability: 41.6% OK (7d historical; 100% remote-era failures — not a current issue)

---

## Scope Lock

In scope:
- Continuation downshift gate fix (http_server.py)
- Hint injection tracking for /query (http_server.py + aq-report) [done via P22-004]
- Cache prewarm: 8 continuation-style seeds
- Phase 23 plan doc

Out of scope:
- Delegate reliability (41.6% is historical remote-era; no current failures)
- Reviewer gate (4 pending intent reviews — addressed by aq-system-act separately)
- New AGI phases
- AIDB schema changes

---

## Sub-phases

### 23.1 — Continuation Downshift Gate Fix

**Problem**: `_apply_query_response_mode()` in `http_server.py` required BOTH:
- `_is_continuation_query(query)` (broad classification)
- `any(marker in normalized for marker in resume_markers)` (narrow 12-phrase list)

The dual gate was over-restrictive: queries like "continue the remaining improvements"
passed `_is_continuation_query` (matches "continue") but failed `resume_markers` (requires
"continue from" not "continue"). aq-report showed 0/8 downshift coverage as a result.

**Fix** (commit pending): removed `resume_markers` check entirely. The exclusion gates
(`explanation_markers`, `explicit_search_markers`) still guard against false positives.

**Files**: `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`

Status: **done** (2026-05-02, pending nixos-rebuild)

---

### 23.2 — Hint Injection Tracking for /query Synthesis

Status: **done** (2026-05-02, commit 4c976f37 via P22-004)

---

### 23.3 — Continuation-Style Cache Prewarm

**Action**: Sent 8 continuation-style query seeds to coordinator /query with
`generate_response=False` to populate the semantic cache and world model patterns.

Seeds:
- "continue with remaining phase tasks"
- "next steps from last session"
- "resume in-progress work"
- "what is the current phase status"
- "continue the system improvements"
- "pick up outstanding work from last run"
- "what open items remain from previous session"
- "continue from last agent session"

Status: **done** (2026-05-02 — all 8 seeds 200 OK)

---

## Verification Matrix

1. ⏳ `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` — activate downshift fix + P22-004
2. ⏳ `aq-report` §7b → continuation downshift coverage > 0 (24h window post-rebuild)
3. ⏳ `aq-report` §14 → hint injections include coordinator entries
4. ⏳ `aq-report` §3 → cache hit rate improving beyond 28%

---

## Work Queue

### Task: P23-001 ✅ COMMITTED (2026-05-02, pending nixos-rebuild)
- Phase: 23.1 — Continuation downshift gate fix
- Owner: Claude
- File: `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
- Fix: removed redundant `resume_markers` dual-gate; `_is_continuation_query` is sufficient
- Status: **committed** — activate with `sudo nixos-rebuild switch --flake .#hyperd-ai-dev`

### Task: P23-002 ✅ DONE (2026-05-02)
- Phase: 23.2 — Hint tracking in /query synthesis
- Status: **done** (commit 4c976f37)

### Task: P23-003 ✅ DONE (2026-05-02)
- Phase: 23.3 — Cache prewarm continuation seeds
- Status: **done** — 8 seeds sent, all 200 OK

### Task: P23-004
- Phase: 23.4 — Validate and push all Phase 23 commits
- Status: **pending commit**

