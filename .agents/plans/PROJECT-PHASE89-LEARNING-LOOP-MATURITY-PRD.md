# Phase 89 — Learning Loop Maturity + Capability Gaps PRD

## Status: AUTHORIZED — 2026-05-30
## Orchestrator: Claude (Sonnet 4.6)

---

## Goal

Close the remaining gaps between deployed infrastructure and actual signal flow.
Training loop is now producing samples (36 total, 8/day). This phase wires the
knowledge back into agents (AIDB seeding, constraints hydration, CL payload fix)
and restores capabilities that are deployed but not activating (downshift, skill factory).

Rust refactor: DEFERRED (user decision 2026-05-30).

---

## Slices

### 89.1 — AIDB Skill Namespace Seeding
**Problem**: aq-report shows "Healthy: no (25 missing)" on AIDB checks. 8 skill
namespaces absent: agent-tool-map, apparmor-rules, aq-workflow, async-delegation,
context-efficiency, coordinator-api, domain-shells, escalation-protocol.
Every agent query in those domains returns noise instead of authoritative knowledge.

**Fix**: Extend `scripts/data/seed-rag-knowledge.py` with entries sourced from
the corresponding `.agent/skills/<name>/SKILL.md` files.

**Files**: `scripts/data/seed-rag-knowledge.py`
**Acceptance**: `aq-report | grep "Missing in AIDB"` shows 0 missing namespaces.

---

### 89.2 — aq-session-start Active Constraints Hydration
**Problem**: `GET /control/ai-coordinator/lessons` returns lessons but no `constraints`
array. aq-session-start step 3 pulls lessons but not active procedural constraints —
agents re-test known-bad approaches every session.

**Fix**: Add `constraints` array to the lessons endpoint response. Pull from
MemoryBroker facts tagged `constraint` or `procedural`. Wire aq-session-start
to print constraints section.

**Files**: `ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py`,
`scripts/ai/aq-session-start`
**Acceptance**: `aq-session-start --task test` output includes constraints section.

---

### 89.3 — agent-events CL Payload Schema Gap
**Problem**: System assessment P1 open: agent loop emits events with stripped payload
missing fields ContinuousLearning expects. Events reach the endpoint but CL logic
silently ignores them → learning feedback loop has a hole.

**Fix**: Audit fields emitted vs fields CL reads. Add missing fields at emit site.

**Files**: `ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py` (CL handler),
`scripts/ai/lib/dispatch.py` (emit site)
**Acceptance**: After a local delegate run, `grep agent_step_complete .agents/telemetry/hybrid-events.jsonl | tail -1` shows all required CL fields.

---

### 89.4 — Continuation Downshift Activation Fix
**Problem**: Downshift shows 0/14 (0%) even after denominator fix. The
`_CONTINUATION_QUERY_MARKERS` patterns aren't matching real traffic.

**Fix**: Sample recent hybrid-events to find actual query patterns, extend markers
to match real traffic, verify at least 1 activation in last 24h.

**Files**: `ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py`
**Acceptance**: `aq-report | grep downshift` shows >0% within 1 query cycle.

---

### 89.5 — PAEA Skill Factory Phase 2 Bootstrap
**Problem**: Was blocked on training loop producing samples. Now unblocked (36 samples).
No automated path from training samples → skill distillation → `.agent/skills/`.

**Fix**: Wire `training_ingest.py` gap_patterns into a skill candidate generator.
High-frequency gap patterns (≥3 occurrences) become draft skill stubs in
`.agent/skills/auto-generated/`. Requires human review before promotion.

**Files**: `ai-stack/local-agents/training_ingest.py`, new `scripts/ai/aq-skill-factory`
**Acceptance**: Running `aq-skill-factory --dry-run` shows ≥1 skill candidate from current gap_patterns.

---

### 89.6 — Dashboard Parity (AIDB Health Panel)
**Problem**: Dashboard AIDB health card shows "no (25 missing)" — blanks degrade
operator situational awareness. Covered by 89.1 seeding but dashboard panel
needs a route if not already reporting the count correctly.

**Fix**: Verify `/api/aistack/aidb/health` reflects updated AIDB counts after 89.1.
No separate code change needed if seeding resolves it.

**Files**: Verification only post-89.1.
**Acceptance**: Dashboard AIDB health card shows green after seeding.

---

## Execution Order

```
89.1  AIDB seeding         ← Python only, no rebuild
89.2  constraints hydration ← Python only, no rebuild
89.3  CL payload fix       ← Python only, coordinator restart needed
89.4  downshift fix        ← Python only, coordinator restart needed
89.5  skill factory        ← Python only, no rebuild
89.6  dashboard verify     ← verification only (after 89.1)
```

## Out of Scope
- Rust refactor (deferred by user decision)
- ACCELERATE ROCm hardware benchmark (88.5, separate session)
- Role enforcement runtime (low priority, doc-only)
