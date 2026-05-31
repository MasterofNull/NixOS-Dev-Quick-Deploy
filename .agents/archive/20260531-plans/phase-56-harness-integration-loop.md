# Phase 56 — Harness Integration Loop
# Status: PLANNED
# Depends on: Phase 55 COMPLETE (commits 432c5a09, 55d84744)
# PRD: .agents/plans/PROJECT-AI-HARNESS-EVOLUTION-PRD.md

## Objective

Close the gap between the coordinator layer (all Phase 40–55 capabilities)
and the CLI layer (where actual development work happens). Every tool,
module, and data store we've built should be exercised by real workflow
events — not just aq-qa smoke tests.

Design principle: **automation and tooling carry the integration weight**.
The local Qwen agent is given small, bounded, async tasks where its
90–120s time horizon is an asset rather than a liability. Remote agents
(Gemini, Codex, Claude Code) stay light. The coordinator becomes the
connective tissue.

---

## The Integration Gap (Diagnosis)

| Capability | Built | Wired to real workflow? |
|---|---|---|
| IntentClassifier | YES | Only /query traffic — not agent invocations |
| RagAugmentor | YES | Only /query — agents start cold each session |
| TraceCollector | YES | Only /query — delegation calls invisible |
| MemoryBroker | YES | No writer during dev work |
| DriftAnalyzer | YES | Reads query_traces — sees 0 delegation traffic |
| WorkflowCheckpointer | YES | No multi-agent task uses it |
| MemoryCrystallizer | YES | aq-crystallize never run — session knowledge evaporated |
| Switchboard profiles | YES | Nothing activates them automatically |
| MCP blueprints x12 | YES | No task is routed through them |
| Delegation audit (0.8.1) | YES | registry.jsonl ≠ tool-audit.jsonl — two separate ledgers |

Root cause: `delegate-to-*` scripts write to `.agents/delegation/registry.jsonl`.
The coordinator's `/stats/delegate` reads `/var/log/ai-audit-sidecar/tool-audit.jsonl`
filtering on `tool_name == "ai_coordinator_delegate"`. These ledgers never intersect.

---

## Local Agent Role Design

The local Qwen3.6-35B agent should be assigned tasks that are:
- **Input-bounded**: small context, specific files or JSON blobs (not entire repo)
- **Output-structured**: returns JSON, not prose essays
- **Async-safe**: 90–120s response is fine for background work
- **Idempotent**: re-running on already-processed input is a no-op
- **Feeds the coordinator**: output lands in AIDB, MemoryBroker, or trace log

Ideal local agent roles:
- Distill session logs → structured episodic facts (crystallization)
- Extract key decisions from a commit diff → semantic memory entries
- Validate a spec diff against its aq-qa check IDs → structured pass/fail
- Rank RAG candidates by relevance to a query → re-ranking signal

NOT appropriate for local agent:
- "Implement feature X" across multiple files (too large)
- Anything requiring real-time interactive response
- Tasks needing >3 tool calls (risks timeout cascade)

---

## Execution Order DAG

56.1 ──► 56.2 ──► 56.3
              └──► 56.4 (parallel with 56.3)
56.3/56.4 ──► 56.5

---

## Slice 56.1 — Delegation Audit Bridge

### Problem
`delegate-to-*` scripts write only to `.agents/delegation/registry.jsonl`.
The coordinator's `/stats/delegate` reads `/var/log/ai-audit-sidecar/tool-audit.jsonl`
for entries with `tool_name == "ai_coordinator_delegate"`. These never meet.
Check 0.8.1 will always skip.

### Deliverables

1. Shared audit-write helper `scripts/ai/lib/audit-write.sh`:
   - `audit_write_delegate <agent> <task_id> <outcome> <latency_ms>`
   - Appends JSON line to `TOOL_AUDIT_LOG_PATH` (default:
     `/var/log/ai-audit-sidecar/tool-audit.jsonl`) with:
     `{"tool_name":"ai_coordinator_delegate","timestamp":"...","outcome":"success|error",
      "latency_ms":N,"parameters":{"agent":"gemini|codex|claude|local","task_id":"..."}}`
   - Graceful no-op if log path unwritable (does not kill script)

2. Wire audit-write into all four delegation scripts:
   - `delegate-to-gemini`: record start (status=running) + completion (outcome)
   - `delegate-to-codex`: same
   - `delegate-to-claude`: same
   - `delegate-to-local`: same for all modes (agent/hybrid/direct/ralph)

3. No coordinator changes needed — `/stats/delegate` already reads this format.

### aq-qa checks (1.2.1–1.2.3)
- 1.2.1: `scripts/ai/lib/audit-write.sh` present and sources cleanly
- 1.2.2: `delegate-to-gemini` contains `audit_write_delegate` call
- 1.2.3: `delegate-to-local` contains `audit_write_delegate` call

---

## Slice 56.2 — Automated Session Crystallization

### Problem
`aq-crystallize` exists but is never called. Every Gemini PRD pass, Codex
implementation cycle, and Continue session closes and the knowledge is trapped
as raw JSON. The MemoryCrystallizer and AIDB episodic collection are empty.

### Deliverables

1. `systemd.services.ai-crystallize-sessions` in `nix/modules/services/mcp-servers.nix`:
   - ExecStart: `${mcp.repoPath}/scripts/ai/aq-crystallize --session-dir /home/hyperd/.continue/sessions/`
   - User: `hyperd` (needs home access)
   - Environment: inherits HYBRID_COORDINATOR_URL
   - Type: oneshot
   - After: ai-hybrid-coordinator.service

2. `systemd.timers.ai-crystallize-sessions`:
   - OnCalendar: `*-*-* 02:00:00` (nightly 2am)
   - OnBootSec: `15min` (catch up on boot)
   - Persistent: true

3. **Local agent role**: The actual distillation work inside `aq-crystallize`
   already calls the coordinator's `POST /memory/crystalline/run` which routes
   to Qwen via llama.cpp. This IS the local agent working — bounded input
   (one session JSON per call), structured output (episodic facts), fully async.
   No change needed to the crystallizer; the timer just ensures it runs.

4. `scripts/ai/aq-crystallize`: add `--since-hours N` flag (default 24) so
   nightly run only processes sessions newer than last run.

### aq-qa checks (1.2.4–1.2.6)
- 1.2.4: `ai-crystallize-sessions.timer` present in NixOS config (grep mcp-servers.nix)
- 1.2.5: `aq-crystallize` accepts `--since-hours` flag without error
- 1.2.6: `GET /memory/crystalline/status` returns `sessions_processed > 0` after
          running `aq-crystallize --dry-run` (dry-run path: count only, no POST)

---

## Slice 56.3 — Pre-Task Context Hydration Script

### Problem
`aq-context-bootstrap` and `aq-hints` are in CLAUDE.md session-start
requirements but nothing enforces or automates them. Agents start each
session with no AIDB context — re-deriving facts that have been stored
for months.

### Deliverables

1. `scripts/ai/aq-session-start`:
   - Usage: `aq-session-start --task "description" [--format brief|full]`
   - Calls `aq-context-bootstrap --task "$task"` → captures relevant AIDB docs
   - Calls `aq-hints "$task" --format json` → captures ranked hints
   - Writes combined output to `.agents/scratchpad/session-context-$(date +%Y%m%d).md`
   - Prints a 5-line summary to stdout (agent-friendly, not wall of text)
   - Non-blocking: if coordinator down, emits warning and exits 0

2. Document in AGENTS.md: `aq-session-start` is the mandatory first command
   for any multi-step task. Replaces the separate aq-context-bootstrap +
   aq-hints calls in the session-zero workflow.

3. **Local agent role (optional)**: If `--summarize` flag passed, pipes the
   combined context through `delegate-to-local --mode direct` asking Qwen to
   produce a 3-bullet task brief. Async, bounded (context is already small
   after bootstrap filtering), structured output.

### aq-qa checks (1.2.7–1.2.8)
- 1.2.7: `aq-session-start` present, executable, exits 0 with `--task "test"`
          even when coordinator unavailable (graceful)
- 1.2.8: output file written to `.agents/scratchpad/session-context-*.md`

---

## Slice 56.4 — Commit-Time Fact Extraction (Local Agent)

### Problem
Significant architectural decisions, bug fixes, and design choices are locked
in commit messages and diffs — never surfaced to AIDB semantic memory.
Future sessions (and agents) re-derive known facts from scratch.

### Deliverables

1. `scripts/ai/aq-commit-facts`:
   - Usage: `aq-commit-facts [--since COMMIT_SHA] [--dry-run]`
   - Gets diff + commit message(s) since SHA (default: last commit)
   - Trims to ≤800 chars (token budget for local agent — see Phase 33 cap)
   - Calls `delegate-to-local --mode direct --wait --prompt "..."` with
     structured extraction prompt:
     ```
     Given this git diff summary, extract 2-4 facts as JSON array:
     [{"fact": "...", "scope": "coordinator|nix|scripts|dashboard",
       "confidence": 0.8, "source_commit": "SHA"}]
     Only include decisions, constraints, or patterns that future agents
     should know. No implementation detail noise.
     ```
   - Parses JSON response, POSTs each fact to `POST /api/memory/facts`
     (new lightweight endpoint) or directly to MemoryBroker semantic store
     via existing coordinator route

2. `POST /api/memory/facts` endpoint in http_server.py:
   - Body: `{"facts": [{"fact": str, "scope": str, "confidence": float, "source_commit": str}]}`
   - Writes each to MemoryBroker with type=`semantic`, `valid_from=now()`
   - Returns `{"stored": N}`
   - Auth: loopback exempt (both auth layers)

3. Wire into commit discipline:
   - Add `aq-commit-facts` as optional post-commit step in CLAUDE.md and AGENTS.md
   - Not enforced in tier0 gate (async, local model might be slow)
   - Runs in background: `aq-commit-facts --since HEAD~1 &`

### Local agent task profile
- Input: ≤800 char diff summary + commit message (fits in one llama.cpp call)
- Output: JSON array of 2-4 facts (≤200 tokens)
- Time horizon: 90–120s is fine — runs async post-commit
- Mode: `direct` (llama.cpp raw completion, no tool loop overhead)

### aq-qa checks (1.2.9–1.2.11)
- 1.2.9: `aq-commit-facts` present and executable
- 1.2.10: `POST /api/memory/facts` registered (returns valid JSON)
- 1.2.11: `POST /api/memory/facts` in both auth prefix lists

---

## Slice 56.5 — Drift-Aware Profile Auto-Activation

### Problem
DriftAnalyzer computes drift_score and sets `alert_triggered` but nothing
acts on it. The agent-ops switchboard profile exists but is never activated.
The "immune system" has sensors but no effectors.

### Deliverables

1. Coordinator drift poll loop in `server.py`:
   - Background task, runs every 60s
   - Calls `drift_analyzer.get_analyzer().compute_drift(window=20)`
   - If `drift_score > drift_alert_threshold` AND current profile is not `agent-ops`:
     - Sets a coordinator-scoped hint key `active_profile_override = "agent-ops"`
     - Logs to TraceCollector as a system event
   - If score drops back below threshold: clears override

2. `handle_query` respects `active_profile_override` when selecting switchboard profile:
   - Already has profile selection logic; just check the override key first

3. `GET /api/agent-ops/status` — new endpoint:
   - Returns `{drift_score, profile_override, alert_active, since}`
   - Lets dashboard and aq-qa confirm the loop is live

### aq-qa checks (1.2.12–1.2.13)
- 1.2.12: `GET /api/agent-ops/status` registered and returns valid JSON
- 1.2.13: `drift_score` in response is null or float 0–1 (graceful)

---

---

## Slice 56.6 — Agent Event Bus (Shared Signal Log)

### Problem
Every module — TraceCollector, DriftAnalyzer, ContinuousLearning, LessonEffectivenessTracker —
captures signals from `/query` traffic only. Remote agent completions, delegation errors,
architectural decisions, and error resolutions are invisible to all of them.
The learning pipeline has no input from the actual development cycle.

The existing `POST /control/ai-coordinator/delegate` endpoint already writes to tool-audit.jsonl
and integrates with the learning pipeline — but `delegate-to-*` scripts never call it.
The fix is not to rebuild the bus; it's to route signals through the one that exists.

### Deliverables

1. `POST /api/agent-events` — lightweight event ingest endpoint in http_server.py:
   - Body:
     ```json
     {
       "event_type": "task_completed|error_resolution|lesson|decision|delegation_start|delegation_end",
       "agent": "gemini|codex|claude|local|coordinator",
       "outcome": "success|error|skip",
       "summary": "...",  // ≤400 chars — what happened
       "tags": ["phase-56", "routing"],
       "latency_ms": 0,
       "task_id": "optional-delegation-task-id"
     }
     ```
   - Writes one JSON line to tool-audit.jsonl (same format `/stats/delegate` reads)
     → `{"tool_name":"ai_coordinator_delegate", "timestamp":"...", "outcome":"...", "latency_ms":N, "parameters":{...}}`
   - If `event_type` in `{task_completed, error_resolution}`: also appends to
     `continuous_learning` pipeline (existing `_process_event()` path)
   - If `event_type == lesson`: creates entry in agent-lesson registry
     (existing `_save_agent_lessons_registry()` path)
   - Returns `{"accepted": true, "event_type": "...", "agent": "..."}`
   - Auth: loopback exempt (both auth layers)
   - Degrades gracefully: write failure → log warning, still return 200

2. `GET /api/agent-events?limit=20&event_type=lesson` — recent event feed:
   - Reads last N lines from tool-audit.jsonl filtered by event_type
   - Returns `{"events": [...], "total_in_window": N}`
   - Used by `aq-session-start` and the dashboard

3. `scripts/ai/lib/audit-write.sh` (from 56.1) calls `POST /api/agent-events`
   instead of writing directly to the log file — coordinator owns the write path.

### aq-qa checks (1.2.14–1.2.15)
- 1.2.14: `POST /api/agent-events` registered and returns `{"accepted":true}`
- 1.2.15: `GET /api/agent-events` registered and returns valid JSON

---

## Slice 56.7 — Remote Agent Outcome Capture

### Problem
When Gemini completes a PRD pass, Codex finishes an implementation cycle, or a
delegation fails mid-task, that outcome is written only to `.agents/delegation/registry.jsonl`.
The continuous learning pipeline, lesson registry, and AIDB never see it.
Future sessions re-encounter the same failure modes.

### Deliverables

1. Extend `scripts/ai/lib/audit-write.sh`:
   - `audit_event_start <agent> <task_id> <summary>` → POSTs `delegation_start` event
   - `audit_event_end <agent> <task_id> <outcome> <latency_ms> <summary>` → POSTs `task_completed` or `error_resolution`
   - If outcome=error: summary is trimmed output of the delegation (first 400 chars)
     — fed to continuous_learning as an error resolution event for pattern extraction

2. All four delegation scripts wire both calls:
   - `audit_event_start` immediately after `registry_append`
   - `audit_event_end` in both wait and background completion paths
   - Background mode: nohup subshell calls `audit_event_end` after exit_code evaluation

3. `scripts/ai/aq-commit-facts` (from 56.4) posts a `decision` event after
   each successfully stored fact — creates a trail of architectural decisions
   in the event bus independently of the lesson registry.

4. Local agent (`delegate-to-local`) — **special bounded role**:
   When `outcome=error` on any remote delegation, optionally route a compressed
   error summary to Qwen for pattern labeling:
   - `delegate-to-local --mode direct --prompt "Label this error in ≤10 words as JSON: {error_type, likely_cause}"`
   - Resulting label attached to the event before it enters continuous_learning
   - Async, non-blocking, ≤100 token output
   - Only invoked if `QWEN_ERROR_LABELING=true` env var is set (off by default)

### aq-qa checks (1.2.16–1.2.17)
- 1.2.16: `delegate-to-gemini` calls `audit_event_start` and `audit_event_end`
- 1.2.17: `delegate-to-local` calls `audit_event_start` and `audit_event_end`

---

## Slice 56.8 — Cross-Agent Lesson Feed at Session Start

### Problem
`GET /control/ai-coordinator/lessons` already returns the full lesson registry —
promoted lessons, pending review, effectiveness stats. But nothing reads it at
session start. Every agent begins cold, unaware of lessons learned from previous
sessions by other agents.

### Deliverables

1. Extend `scripts/ai/aq-session-start` (from 56.3):
   - Adds a third pull: `GET /control/ai-coordinator/lessons` → extracts
     `active_lesson_refs` (max 5, already filtered to promoted/crystallized only)
   - Formats as a "recent lessons" brief block in `session-context-YYYYMMDD.md`:
     ```
     ## Lessons (promoted, last 7d)
     - [lesson_key] summary — source: <agent>, validated: <date>
     ```
   - If no promoted lessons: skips the block silently (no noise)

2. `scripts/ai/aq-lesson-promote` — new CLI:
   - Usage: `aq-lesson-promote --key LESSON_KEY --reviewer "claude" [--comment "..."]`
   - Wraps `POST /control/ai-coordinator/lessons/review` with `state=promoted`
   - Lets any agent or human quickly promote a candidate lesson to active
   - Exit 0 on success, prints confirmation

3. Dashboard Agent Ops panel (from Phase 55) — extend `loadAgentOps()`:
   - Pull `GET /control/ai-coordinator/lessons` and surface:
     - `pending_review` count (needs human/agent review)
     - `promoted` count (active in session starts)
     - `highly_effective` lessons by success rate
   - Add to existing Drift Score card as a "Lessons" sub-row

4. **Organism loop complete**: agent works → outcome captured via event bus →
   continuous_learning extracts pattern → lesson candidate created → promoted
   via `aq-lesson-promote` → `aq-session-start` feeds it to next session →
   that session starts with institutional memory, not a blank slate.

### aq-qa checks (1.2.18–1.2.20)
- 1.2.18: `aq-session-start` output includes `active_lesson_refs` block when lessons present
- 1.2.19: `aq-lesson-promote` present, executable, exits 0 with valid API response
- 1.2.20: dashboard `loadAgentOps()` calls `/control/ai-coordinator/lessons`

---

## Spec-Driven Constraints (All Slices)

1. `audit-write.sh` must be source-safe (no `exit`, no `set -e` propagation).
2. `aq-commit-facts` prompt to local agent must be ≤800 chars total.
3. All new coordinator endpoints: dual auth gate (both auth layers).
4. Crystallization timer: `User = "hyperd"` (needs ~/.continue access).
5. `aq-session-start` must exit 0 even when coordinator is down.
6. `aq-commit-facts` runs async — must not block the commit workflow.
7. `POST /api/agent-events` write failure must NOT crash the calling script — log only.
8. Lesson feed in `aq-session-start` is read-only — never promotes/mutates state automatically.
9. Qwen error labeling (`QWEN_ERROR_LABELING`) is opt-in — default off to avoid latency on every delegation failure.
10. DUAL AUTH GATE: all new endpoints in both `LOOPBACK_AGENT_PREFIXES` and inline `agent_prefixes` ~line 1412.

---

## Validation Gate

```bash
aq-qa 56       # 20 new checks (1.2.1–1.2.20)
aq-qa 0        # no regression (60 checks)
aq-qa 55       # 16/16 still passing
```

After 56.1+56.6 deployed + one delegation call:
```bash
delegate-to-gemini --prompt "health check ping" --wait
aq-qa 0        # 0.8.1 should now PASS instead of SKIP
GET /api/agent-events?limit=5  # delegation event visible
GET /control/ai-coordinator/lessons  # lesson registry accessible
```

Commit format: `feat(integration): phase 56 — harness integration loop + institutional memory`

---

## Local Agent Promotion Roadmap (Beyond Phase 56)

Phase 56 gives Qwen three bounded, async roles:
1. Session crystallization (via MemoryCrystallizer — already wired)
2. Commit fact extraction (new, 800-char input, JSON output)
3. Optional session-start brief (--summarize flag, 3-bullet output)

The path to a more prominent Qwen role:
- **Phase 57**: Qwen as RAG re-ranker — coordinator sends top-5 AIDB results
  to Qwen for relevance scoring before injecting into context. Bounded (5 snippets),
  structured output (ranked list), improves every /query call.
- **Phase 58**: Qwen as workflow step validator — given a DAG step's output and
  its acceptance criteria, Qwen scores pass/fail. Checkpointer uses this score
  before advancing the DAG. Bounded, idempotent, async.
- **Phase 59**: Qwen as intent classifier fallback — when IntentClassifier
  confidence < 0.6, escalate to Qwen for richer classification. <200 token
  input, single-token + confidence output.

Each phase increases Qwen's role without overwhelming it or cutting it out
when it's slow. The local model earns centrality by handling progressively
more critical path decisions at its natural time horizon.
