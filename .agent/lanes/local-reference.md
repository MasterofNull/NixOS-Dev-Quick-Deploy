# local lane reference (moved from .agent/LOCAL-AGENT.md; on-demand, not always-on)

Sections moved verbatim to keep the always-on file small. Nothing here was deleted.

Contents: Progressive disclosure and fetch-on-demand; Service Ports (defaults — canonical SSOT: `nix/modules/core/options.nix`); Operating Philosophy; NixOS System Contract (MANDATORY — read before any system change); Skill Index; Objective Discovery (when no task is given); Self-Improvement Workflow (MANDATORY — do not invent work); Current Model Config (tail); Capability Amplification — Overcoming Limits; Required Shared Knowledge (load at session start); Role & Mode (tail); The 8-Step Canonical Workflow; Service Ports; File Placement Contract; Key Paths & Resources; On-Demand Context.

## Progressive disclosure and fetch-on-demand

- Keep the always-on prompt to role/authority, active objective, owned paths, acceptance criteria, and stop/validation constraints.
- Fetch `aq-resume`, then task hints and at most 2–3 matching skills; use `lean-ctx` outlines/signatures before bounded reads of exact symbols.
- Load domain instructions, memory topics, and full policy sections only when their task trigger or pointer requires them.
- Pass delegation pointers and slice criteria, never parent history, full transcripts, whole files, or full skill bodies; persist the active envelope in `RESUME.json`.

## Service Ports (defaults — canonical SSOT: `nix/modules/core/options.nix`)
```
llama:8080  embed:8081  aidb:8002  hybrid:8003  ralph:8004  swb:8085  dash:8889
```
All curl examples in this file use these defaults. Actual values come from the NixOS config at
runtime via env vars — never hardcode ports in code or shell scripts.

---

## Operating Philosophy

**You are a locally hosted model on constrained APU hardware.
The harness is your force multiplier. Use it.**

A constrained model with full tool access — RAG, persistent memory, knowledge graph, hints,
delegation, and session continuity — outperforms a much larger model working blind. Every feature
of this harness exists to extend your effective reasoning beyond what fits in context. The
hardware is the floor. The stack is the ceiling.

**When you feel constrained, the answer is always: use more harness, not more context.**

---

## NixOS System Contract (MANDATORY — read before any system change)

This system is **NixOS-first and flake-based**. All package, service, and config changes go through the declarative Nix config. No exceptions.

| Want to… | Correct path | NEVER do |
|-----------|-------------|----------|
| Add a Python package | `python3.withPackages [...]` in `nix/home/base.nix` | `pip install` |
| Add a Node.js tool | `nodePackages.*` in nixpkgs | `npm install -g` |
| Add a system service | `nix/modules/services/` or `nix/modules/roles/` | `systemctl enable` |
| Change a port/URL | `nix/modules/core/options.nix` SSOT → injected env var | hardcode in scripts |
| Enable a feature | `nix/modules/profiles/ai-dev.nix` | runtime boolean env vars |
| Update all packages | `nix flake update` → rebuild | version-pin in code |

**Package lookup**: `nix search nixpkgs#<name>` before concluding something isn't available.

**Rebuild commands** (run from repo root, requires `sudo`):
```bash
sudo nixos-rebuild switch --flake .#hyperd-ai-dev   # full system
home-manager switch --flake .#hyperd                # user packages only
```

**Nix file locations**:
- System packages/services: `nix/modules/`
- User packages/tools: `nix/home/base.nix`
- Per-host overrides: `nix/hosts/hyperd/`
- Port/URL constants: `nix/modules/core/options.nix` (single source of truth)
- AI stack config: `nix/modules/roles/ai-stack.nix`
- Feature flags: `nix/modules/profiles/ai-dev.nix`

**Do NOT propose** changes to flake.nix, overlays, or NixOS modules without first checking that the change is within your assigned slice. Nix eval errors fail the build — always verify with `nix eval` before committing.

## Skill Index

Before starting any task, auto-select and test relevant local skills. Skills save context by putting
the right knowledge in view without loading the full codebase.

```bash
scripts/ai/aq-skill-auto "<task or user prompt>" --agent local --json --test
```

Load the returned `reference_skills` before planning or editing. If the selector is unavailable, fall back to the skill index.

**Scan** (MCP tool): `hybrid_search` query "skill <topic>" in `skills-patterns` collection
**Or read**: `.agent/SKILL_INDEX.md` then load `.agent/skills/<name>/SKILL.md`

**Token budget constraint**: local model input = 3500 tokens (`local-agent` profile).
**Load max 2 skills per task.** Each SKILL.md ≈ 400-1000 tokens.
**Tool call budget**: 40 calls per session (`LOCAL_TOOL_CALL_LIMIT`). Active schemas: 12. GC threshold: 5000 chars.
**Context compression**: `run_command` auto-wraps with RTK when available — shell output is compressed 60-90% before entering context. Check savings with `run_command "rtk gain"`.

**Critical local-agent skills** (load for applicable work):
- `self-improvement` — **load first** when asked to "run a self-improvement slice" or "improve the harness" — full workflow: discover priority from issues-backlog/PRDs/reports → announce target → implement autonomously → validate → commit
- `llm-config` — mandatory: `enable_thinking` in chat_template_kwargs, build_llama_payload SSOT
- `rag-operations` — RAG queries via :8003, collection names, BGE-M3 threshold 0.45
- `coordinator-api` — auth, loopback exemptions, key routes
- `context-efficiency` — RESUME.json authoring, sub-agent slicing, compaction recovery
- `python-async` — async handler patterns, asyncio.to_thread for blocking I/O

**In `--mode direct`** (no tool access): reasoning/analysis only. Cannot query live services.
Reference skills by name for the orchestrator to load — don't claim to have called a tool.

---

## Objective Discovery (when no task is given)

If the user starts a session without a specific task, or explicitly asks "what should we work on?",
call the `discover_objectives` tool. It will:

1. Check `RESUME.json` for in-flight work (highest priority)
2. Scan `issues-backlog.md` for open/critical items
3. Query AIDB for relevant error patterns
4. Read the last PULSE.log entry for session context

**After calling `discover_objectives`**:
- Present the returned ranked list as a numbered proposal to the user
- For each objective show: **title**, source, priority, reasoning
- Show `context.relevant_files` — files the user will likely need to review
- Show `context.recent_errors` — any matching error events from telemetry
- Show `context.prsi_items` — pending automation actions related to this objective
- Show `constraints` — inferred boundaries (validation gate, rebuild needed, etc.)
- End with: *"Please reply with a number to select, or describe a different goal."*
- **Do NOT call any other tools or take any action until the user confirms.**

The `discover_objectives` tool is a research-and-propose tool, not an execution tool.
The user's confirmation is the gate. No approval → no action.

---

## Self-Improvement Workflow (MANDATORY — do not invent work)

When asked to run a "self-improvement slice", "improve the harness", or "run autonomously":

**Preferred path — use `aq-loop` for full autonomous execution:**
```bash
aq-loop --list-open                               # see what's actionable
aq-loop --from-backlog --dry-run                  # preview grounded prompt
aq-loop --from-backlog                            # execute autonomously (fan-out enabled by default)
aq-loop --intent "implement X"                    # explicit task with retry loop
aq-loop --intent "task" --no-fanout              # skip parallel probes (local only, faster)
aq-loop --intent "task" --fanout-timeout 60      # shorter probe wait (default 120s)
aq-loop-queue --max 5                             # sequential queue runner (anytime — not just overnight)
```
`aq-loop` handles: backlog claim/release, hint grounding, retry on incomplete COMPLETED: signal,
tool-manifest auto-selection (self-improvement=8 tools), LOOP_STATE.json for compaction survival.

**Multi-agent fan-out (enabled by default in aq-loop):**
- GROUND phase: local agent (Qwen3-35B) receives research probe via `delegate-to-local --mode agent`;
  antigravity (Gemini) receives architecture probe via `delegate-to-antigravity --mode architect`.
  Both fire in background; results collected within fanout_timeout (120s default).
- VERIFY phase: completed output dispatched to `delegate-to-antigravity --mode reviewer` for
  acceptance review. REJECTED verdict re-queues with findings for next iteration.
- As local agent, you will receive research probes from aq-loop's GROUND phase. Respond with
  concise analysis (≤600 words): relevant code, known failure patterns, recommended approach.
  Do NOT emit file edits or COMPLETED: in probe responses — analysis only.

**Manual path — use when inside an aq-loop iteration or outer loop unavailable:**

**NEVER** start with documentation cleanup or hypothetical planning. Always:

1. **Auto-select skills**: run `scripts/ai/aq-skill-auto "<task>" --agent local --json --test`, then load `.agent/skills/self-improvement/SKILL.md` if selected
2. **Scan authoritative sources** for open P1/P2 work:
   - `memory/issues-backlog.md` — open bugs and blockers (highest signal)
   - `.agent/collaboration/RESUME.json` — in-flight objective
   - `.agent/collaboration/HANDOFF.md` — recent session context
   - `.agents/plans/*.md` — active implementation plans
   - Quick health: `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 timeout 90 scripts/ai/aq-qa 0 2>&1 | tail -20`
3. **Select the single highest-priority OPEN item** — state in one sentence what you are fixing
4. **Implement immediately** — write_file / run_command; one issue, no scope-creep
5. **Validate**: `scripts/governance/tier0-validation-gate.sh --pre-commit` + `aq-qa 0` if runtime changed; fix failures
6. **Commit**: `git add <specific files>` + `git commit -m "type(scope): ...\n\nCo-Authored-By: AQ <noreply@harness.local>"`
7. **Report** what changed, what passed, what to review

This workflow exists because the harness has extensive existing plans, backlogs, and roadmaps.
Ignoring them produces redundant or low-impact work. Always derive improvement from authoritative sources.
**Execute all steps without stopping** — the operator reviews the commit, not pre-approves each step.

---

## Current Model Config (continued)

**Phase 172 — Safe Thinking Mode (via `llm_config.py` task profiles):**

| Profile | `task_type=` | `enable_thinking` | `thinking_budget` | Use case |
|---------|-------------|-------------------|-------------------|----------|
| agent (default) | `"agent"` | False | None | Tool calls, harness ops |
| research | `"research"` | **True** | 100 tokens | PRSI cycles, root-cause analysis |
| deep_reasoning | `"deep_reasoning"` | **True** | 150 tokens | Architecture, multi-hop planning |

Safe thinking: `thinking_budget` caps the thinking phase at N tokens (N seconds at 1 tok/s).
Total `max_tokens` covers both thinking + content. At 1 tok/s: research = max 900s, deep_reasoning = max 1150s.

Activation:
```bash
aq-agent-loop --task "..." --task-type research     # PRSI / discovery
aq-agent-loop --task "..." --task-type deep_reasoning   # architecture planning
python3 scripts/automation/prsi-orchestrator.py agent   # autonomous PRSI cycle
```

For coordinator-spawned agents (`local_agent_runtime.py`): set `AGENT_TASK_TYPE=research` env var.

### Inference Delivery Resilience (Phase 173)

`local_agent_runtime._post_completion_with_fallback()` retries once on transient switchboard
failures before falling back to direct llama.cpp:

1. Attempt 0: POST to switchboard (30s connect timeout). On failure → sleep 2s → retry.
2. Attempt 1: Retry switchboard. On second failure → fallback to llama.cpp direct.

`agent_registry.py` lessons/evaluations registries use a 60-second TTL in-memory cache
and async executor-based file I/O to avoid blocking the event loop.

### Model Swap Checklist

When deploying a new locally hosted model, verify:

- [ ] Update "Currently running" header in this file
- [ ] Update `## Current Model Config` table above
- [ ] Check if new model has a "thinking/reasoning" mode — add suppression knob if so
- [ ] Check new model's native context window — update context budget guidance
- [ ] Update `ai-stack.nix` `defaultModelCatalog` entry
- [ ] Update `facts.nix` model entry for this host
- [ ] Run `aq-qa 0` after rebuild to verify inference endpoint responds
- [ ] Check MTP/speculative decoding compatibility — not all models support it
- [ ] Verify `enable_thinking: false` equivalent for the new model or remove if not applicable
- [ ] Re-check `SAFE_COMMANDS` in `shell_tools.py` — no model-specific paths should be hardcoded

### Agent Executor Token Budget (Phase 159)

`agent_executor.py` uses a two-phase token budget in `_execute_with_tools()`:

| Phase | Condition | Max tokens | Rationale |
|-------|-----------|-----------|-----------|
| Tool call | `tool_call_count == 0` | 512 (`AGENT_TOOL_CALL_MAX_TOKENS`) | Model emits tool call JSON (~100 tok); EOS fast |
| Synthesis | `tool_call_count > 0` | 1200 (`AGENT_TASK_MAX_TOKENS`) | Final answer may be large JSON/prose; 512 was cutting it off |

`_call_llama()` now accepts a `max_tokens` parameter (default=512 for backwards compat).
Import: `from shared.llm_config import build_llama_payload, AGENT_TOOL_CALL_MAX_TOKENS, AGENT_TASK_MAX_TOKENS`.

### Phase 163 — Fix qa_check 0% failure: coordinator attention queue write access (2026-06-11, requires rebuild)

`run_qa_check` MCP tool was returning empty stdout + exit_code=1 on every call. Root cause: `_aq-qa-bash` check 86.2 calls `attention_queue.push()` which tries to write `ATTENTION_ARCHIVE.jsonl` under `${mcp.repoPath}/.agents/attention/`. The coordinator service runs with `ProtectHome=read-only` (from `commonServiceConfig`) which blocks writes to `/home/hyperd/...` even though `ATTENTION_QUEUE_DIR` is correctly set. Fix: added `"${mcp.repoPath}/.agents/attention"` to `ReadWritePaths` override in the coordinator service config, plus matching AppArmor `rwk` rules. Requires nixos-rebuild.

### Phase 162C — Fix query_aidb 401: /search/ in LOOPBACK_AGENT_PREFIXES (2026-06-11, requires rebuild)

`query_aidb_handler` posts to coordinator `/search/tree` which was not in `LOOPBACK_AGENT_PREFIXES`.
Loopback requests without an API key were rejected with `{"error": "unauthorized", "mode": "api-key"}`.
Fix: added `"/search/"` to `LOOPBACK_AGENT_PREFIXES` in `middleware/auth.py`. Requires nixos-rebuild.

### Phase 162B — Coordinator git_tools, injectHints, local-first routing (2026-06-11, requires rebuild)

- `ai-stack/local-agents/__init__.py`: `initialize_builtin_tools()` now calls `register_git_tools()` — coordinator MCP protocol exposes git tools.
- `ai-stack/switchboard/switchboard.py`: `injectHints: True` only for context-aware agent/tool profiles; `continue-local` remains hint-free for compact editor latency and config parity.
- `config/routing-policy.yaml`: `default_prefer_local: true` — callers without an explicit profile route local by default.
- `ai-stack/meta-optimization/meta_optimizer.py` + `ai-stack/autoresearch/local_model_optimizer.py`: `build_llama_payload()` migration; both are imported by coordinator endpoints.

### Phase 162A — AI Coordination Tools Now Registered (2026-06-11)

`aq-agent-loop` `build_registry()` previously only registered file/shell/git tools. As of Phase 162A:
- `register_ai_coordination_tools()` is now called — adds `query_aidb`, `store_memory`, `get_hint`, `get_working_memory`, `mesh_discovery`, `delegate_to_remote`, `harness_health`, `query_context`, and 6 more tools.
- `store_memory_handler` wired to coordinator `/memory/store` (was returning placeholder error).
- `collective_memory_search_handler` fixed: endpoint `/documents/search` → `/vector/search`, `collection="knowledge"`.
- 5 additional LLM callers migrated to `build_llama_payload()` SSOT (`claude-local-wrapper.py`, `model-client.py`, `llm_code_reviewer.py`, `trigger_engine.py`, `mcp_client.py`).

### AppArmor: coreutils-full multi-call binary (Phase 160)

`ai-hybrid-coordinator` AppArmor profile blocked `coreutils-full` exec — 4 denials on 2026-06-11.
`pkgs.coreutils-full` ships a single multi-call binary at `/nix/store/.../bin/coreutils`.
Per-tool rules (`cat`, `ls`, etc.) don't cover it. Fix: added `/nix/store/**/bin/coreutils ix,`
plus additional common tools (`ls`, `mkdir`, `cp`, `mv`, `rm`, `tr`, `cut`, `echo`) to profile.
File: `nix/modules/services/mcp-servers.nix`. Requires `nixos-rebuild switch` to activate.

### Context Guard (Phase 159.2)

Two runtime defences against context overflow (n_ctx=8192 ceiling on Renoir APU):

1. **Tool result cap** (`tool_registry.format_tool_result()`): raw result serialised to string, hard-capped at **3000 chars** (~750 tokens). Truncation suffix appended so model knows data was clipped.

2. **Message pruning** (`_execute_with_tools()` loop start): when message history exceeds `(8192-2000)*4 = 24768 chars`, the oldest assistant+tool pair is dropped (indices 2+3, after system+user). System message and user task are always preserved. Fires per-loop-iteration so it can prune multiple old pairs before a call.
At 1 tok/s on Renoir APU: 512 tok = ~8 min worst case; 1200 tok = ~20 min worst case.
Tool calls EOS naturally at ~100 tokens regardless of budget ceiling.

**Root cause** (Phase 159, 2026-06-11): local agent local-20260611-110819-8ed7p8 ran 4 tool calls
successfully but result=null, status=failed — final synthesis response truncated at 512 tokens.

---

## Capability Amplification — Overcoming Limits

### 1. Context Constraints → Use RAG + Memory + Hints Instead of Loading Everything

The context window is not your knowledge limit. The harness holds:
- **AIDB (8,220+ vectors, 10 collections)**: pull targeted knowledge by semantic query
- **Knowledge graph (21,549 triples)**: BFS-2 entity expansion for rich domain context
- **Logic patterns (1,288+)**: indexed code/architecture patterns searchable by concept
- **MemoryBroker**: episodic/semantic/procedural memory across sessions — retrieve specific facts
- **Hints engine**: ranked workflow guidance for the current task — replaces reading full docs

**Pattern — before reading a file, ask the harness:**
```bash
run_command "curl -s 'http://localhost:8003/hints?q=<task keyword>'"
run_command "curl -s -X POST http://localhost:8003/query 
  -H 'Content-Type: application/json' 
  -d '{"query":"<concept>","max_tokens":200}'"
run_command "curl -s -X POST http://localhost:8003/api/knowledge/graph/search 
  -H 'Content-Type: application/json' 
  -d '{"q":"<entity>"}'"
run_command "curl -s -X POST http://localhost:8003/api/logic/search 
  -H 'Content-Type: application/json' 
  -d '{"query":"<code concept>","top_k":5}'"
```
**All search goes through the coordinator at :8003 — never curl AIDB at :8002 directly (blocked).**

### 2. Memory Loss Between Calls → Session Continuity Tools

Each inference call starts cold. Use these to carry state forward:
- **`aq-session-start --task "<task>"`** at session start: hydrates context with prior lessons and hints
- **`.agent/collaboration/PULSE.log`**: append checkpoints after every file write — your breadcrumbs
- **`.agent/collaboration/HANDOFF.md`**: read first on resume — last known state from prior session
- **MemoryBroker write**: after completing significant work, store key facts:
  ```bash
  run_command "curl -s -X POST http://localhost:8003/api/memory/facts 
    -H 'Content-Type: application/json' 
    -d '{"content":"<what you learned>","memory_type":"semantic"}'"
  ```
- **`aq-commit-facts`** (if available): extracts institutional memory from git diff automatically

### 3. Reasoning Depth → Structured Decomposition + Profile Selection

Without extended thinking tokens (must be disabled on current model), deepen reasoning through structure:
- **Decompose before acting**: write a 3-line plan in `PULSE.log` before touching any file
- **Use reasoning profiles**: check `http://localhost:8003/control/reasoning/profiles` — select
  the profile matching your task type (coding, review, synthesis)
- **Chain small steps**: one edit → validate → one edit — don't batch edits without checking
- **Verbalize your constraints**: if a task is ambiguous, write out your interpretation first

### 4. Tool Access Limits → API Endpoints + Delegation

When a shell command isn't on `SAFE_COMMANDS`, use the coordinator's API instead:
```bash
run_command "curl -s http://localhost:8003/api/agent-events"
run_command "curl -s http://localhost:8003/api/traces"
run_command "curl -s http://localhost:8003/control/fleet/summary"
run_command "curl -s http://localhost:8889/api/ai/metrics"
```
For tasks requiring broader capabilities (web search, external API, complex shell work),
**delegate to Claude or Codex** via the orchestrator — that is not failure, that is correct architecture.

### 5. Knowledge Gaps → Coordinator Search (NOT direct AIDB curl)

**Direct AIDB curl to :8002 is blocked by SAFE_COMMANDS policy. Always use :8003.**

```bash
run_command "curl -s -X POST http://localhost:8003/query 
  -H 'Content-Type: application/json' 
  -d '{"query":"<your question>","max_tokens":300}'"
```

### 6. Speed Constraints → Speculative Decoding + Caching

- **MTP speculative decoding** (current model only; verify for swapped models): helps with structured/
  repetitive output like JSON, boilerplate, docstrings
- **Embedding cache** (91%+ hit rate): semantic searches on familiar queries are near-instant
- **Redis KV cache**: coordinator response cache means repeated queries are sub-millisecond
- For creative/novel tasks, accept that generation is slower — don't set timeouts too tight

---

## Required Shared Knowledge (load at session start)

All agents share these canonical references — read before any non-trivial task:
- `.agent/PROMOTED-BUG-PATTERNS.md` — 35+ critical patterns from 175+ phases; prevents rediscovery of known failures
- `.agent/INFRASTRUCTURE-CONSTRAINTS.md` — hardware limits, service ports, delegation status, NixOS error patterns

---

## Role & Mode (continued)

**Tool surface (local agent loop — `aq-agent-loop`):**

| Action | Tool | Notes |
|--------|------|-------|
| Read a file | `read_file` | Always read before editing |
| Write/overwrite | `write_file` | Prefer `edit_file` for in-place changes |
| Edit in-place | `edit_file` | Provide exact old/new string |
| List directory | `list_files` | Do not use shell `ls` |
| Search contents | `search_files` | grep-equivalent, returns matches |
| Run whitelisted commands | `run_command` | SAFE_COMMANDS whitelist; RTK auto-compresses output when installed (`"compressed": true` in response) |
| Reach a tool not on PATH | `run_command('aq-tool <pkg> [args]')` | Live, no restart — resolves `<pkg>` from the pinned nixpkgs (`flake.lock`). No manifest/permission gate; the capability manifest is a record, never a runtime gate (Rule 16 parity). |
| Consult codebase mapping | `run_command('aq-wiki --section <name>')` | understand-anything subsystem wiki (hybrid-coordinator, switchboard, aidb, local-agent, governance, …); `--list`/`--status` for coverage. Use BEFORE scanning raw source for orientation. Now whitelisted in SAFE_COMMANDS. |
| Git status/diff | `git_status`, `git_diff` | Read-only git introspection |
| Stage files | `git_add` | Only stage specific files |
| Validate before commit | `validate_before_commit` | MANDATORY before any commit |

Shell commands not on `SAFE_COMMANDS` will be rejected. Use API endpoints as substitutes.
Workspace boundary: all file tools scoped to repo root. Use coordinator APIs for `/var/lib/`, `/run/`.

---

## The 8-Step Canonical Workflow

Follow this for every non-trivial task. Full contract: `.agent/WORKFLOW-CANON.md`.

### Step 1 — ORIENT (use the harness, not your parameters)
```bash
run_command "aq-session-start --task '<task>'"
run_command "curl -s 'http://localhost:8003/hints?q=<task>'"
```
If resuming: read `.agent/collaboration/HANDOFF.md` first.

### Step 2 — RESEARCH (pull, don't pre-load)
```bash
search_files "<keyword>"
run_command "curl -s 'http://localhost:8003/hints?q=<keyword>'"
run_command "curl -s -X POST http://localhost:8003/query 
  -H 'Content-Type: application/json' 
  -d '{"query":"<concept>","max_tokens":150}'"
read_file <confirmed_path>
```
- Use coordinator hints + RAG before reading raw files
- Direct AIDB curl (:8002) is blocked for most endpoints — always use :8003 endpoints
- Exception — these AIDB endpoints ARE accessible without auth:
  - `GET :8002/health` — service health
  - `GET :8002/health/detailed` — circuit breakers, RAG status
  - `GET :8002/history` — recent interactions (list)
  - `GET :8002/history/stats` — total_interactions, outcomes breakdown
  - `POST :8002/vector/search` — semantic search (body: `{"query":"...","collection":"...","limit":N}`)
  - `GET :8002/openapi.json` — full endpoint list (always check this before guessing paths)

**Qdrant collection routing (CRITICAL — use the correct collection or you get MCP-registry noise):**
| Purpose | Collection |
|---------|-----------|
| Error patterns / bug fixes | `error-solutions` (319 seeded records) |
| Best practices / patterns | `best-practices` |
| Agent workflow skills | `skills-patterns` |
| Solved harness issues | `solved_issues` (MCP registry catalog — NOT for error patterns) |
| DO NOT use `solved_issues` for error lookups — it returns irrelevant MCP-registry results (distance>0.95) |

### Step 3 — PRD / PLAN (write 3 lines before touching code)
Write to `.agent/collaboration/PULSE.log`:
```
[LOCAL PLAN] task=<task> | target_files=<list> | approach=<1 sentence> | risk=<1 sentence>
```

### Step 4 — MEMORY CHECKPOINT
```bash
run_command "curl -s -X POST http://localhost:8003/api/memory/facts 
  -H 'Content-Type: application/json' 
  -d '{"content":"TASK: <task> | PLAN: <summary> | FILES: <list>","memory_type":"procedural"}'"
```

### Step 5 — EXECUTE (one edit at a time)
- Read all target files before editing — never edit blind
- After each file write: `[LOCAL WRITE] <filename> — <what changed>` → PULSE.log
- Validate after each logical unit — don't batch edits before checking syntax
- No "while I'm here" additions — stay in the slice

### Step 6 — VALIDATE
1. **Live test** changes — run the changed component in the actual system to catch runtime errors
2. Fix issues found
3. Run gates:
```bash
validate_before_commit
run_command "python3 -m py_compile <changed files>"
run_command "bash -n <changed shell scripts>"
```
Do NOT run `aq-qa 0` inline — it takes 40+ seconds and blocks the event loop. Leave QA to orchestrator.

### Step 7 — DOC-UPDATE + MEMORY WRITE
After every code/config change:
- Report to orchestrator what changed and any new patterns discovered
- POST completed-task fact to MemoryBroker:
```bash
run_command "curl -s -X POST http://localhost:8003/api/memory/facts \
  -H 'Content-Type: application/json' \
  -d '{\"content\":\"COMPLETED: <task> | KEY LEARNING: <1 sentence>\",\"memory_type\":\"semantic\"}'"
```
- Append to `.agent/collaboration/PULSE.log` and `.agent/collaboration/RESUME.json`
- Note any new bug patterns for orchestrator to seed to RAG

### Step 8 — COMMIT PROPOSAL
```bash
validate_before_commit
git_add <specific files>
```
Propose commit to orchestrator. Format: `type(scope): description`. Do NOT self-commit without orchestrator review.

---

## Service Ports
```
llama:8080  embed:8081  aidb:8002  hybrid:8003  ralph:8004  swb:8085  dash:8889
```
Source of truth: `nix/modules/core/options.nix`. Never hardcode.

---

## File Placement Contract

1. PRD / rules / workflow evidence → `.agent/`
2. Phase / slice plans → `.agents/plans/`
3. No workflow artifacts in repo root
4. Validate: `scripts/governance/repo-structure-lint.sh --staged`

---

## Key Paths & Resources

- **Canonical workflow**: `.agent/WORKFLOW-CANON.md`
- **Session start**: `scripts/ai/aq-session-start`
- **Harness insights**: `scripts/ai/aq-insights` (local model analysis of latest aq-report snapshot)
- **Hints engine**: `http://localhost:8003/hints?q=<query>`
- **RAG query**: `http://localhost:8003/query` (POST — full retrieval + memory recall)
- **Graph search**: `http://localhost:8003/api/knowledge/graph/search`
- **Memory write**: `http://localhost:8003/api/memory/facts`
- **Logic search**: `http://localhost:8003/api/logic/search`
- **Coordinator**: `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
- **Port options**: `nix/modules/core/options.nix`
- **Role matrix**: `docs/architecture/role-matrix.md`
- **IPM/thermal**: `ai-stack/mcp-servers/hybrid-coordinator/inference_param_manager.py`
- **MLFQ scheduler**: `ai-stack/mcp-servers/hybrid-coordinator/mlfq_scheduler.py`
- **Model config (Nix)**: `nix/modules/roles/ai-stack.nix` → `defaultModelCatalog`
- **Model config (facts)**: `nix/facts/hyperd.nix` (per-host model overrides)

---

## On-Demand Context

| Topic | File / Endpoint |
|-------|-----------------|
| Canonical workflow | `.agent/WORKFLOW-CANON.md` |
| Full policy | `AGENTS.md` |
| Physical limits | `docs/architecture/canonical-kernel-declaration.md` |
| Port options | `nix/modules/core/options.nix` |
| AI stack wiring | `nix/modules/roles/ai-stack.nix` |
| Role matrix | `docs/architecture/role-matrix.md` |
| System metrics | `http://localhost:8889/api/ai/metrics` |
| Thermal state | `http://localhost:8889/api/hardware/state` |
| Active hints | `http://localhost:8003/hints?q=<task>` |
| Working memory | `http://localhost:8003/api/memory/facts` |
| Reasoning profiles | `http://localhost:8003/control/reasoning/profiles` |
| **Wiki & Knowledge Graph** | |
| Wiki index | `.understand-anything/wiki/README.md` |
| Subsystem wiki sections | `aq-wiki --list`  ·  `aq-wiki --section <name>` |
| Wiki freshness check | `aq-wiki --status` |
| Maintenance guide | `docs/agent-guides/48-WIKI-MAINTENANCE.md` |
| **Domain Instructions** | |
| osint-systems | `.agent/OSINT-SYSTEMS-INSTRUCTIONS.md` |
| trading-agents | `.agent/TRADING-AGENTS-INSTRUCTIONS.md` |
| mlops-engineering | `.agent/MLOPS-ENGINEERING-INSTRUCTIONS.md` |
| qa-automation | `.agent/QA-AUTOMATION-INSTRUCTIONS.md` |
| mobile-web | `.agent/MOBILE-WEB-INSTRUCTIONS.md` |
| security-systems | `.agent/SECURITY-SYSTEMS-INSTRUCTIONS.md` |
| systems-software | `.agent/SYSTEMS-SOFTWARE-INSTRUCTIONS.md` |
| gis-systems | `.agent/GIS-SYSTEMS-INSTRUCTIONS.md` |
| embedded-hardware | `.agent/EMBEDDED-HARDWARE-INSTRUCTIONS.md` |
| scientific-research | `.agent/SCIENTIFIC-RESEARCH-INSTRUCTIONS.md` |

## Local thermal table (moved from lane region, 2026-10-10, delivery-workflow budget trim)

**Thermal gates** (automatic, but be aware):

| Tier | Temp | Effect |
|------|------|--------|
| `optimal` | ≤70°C | Full operation |
| `warm` | ≤85°C | Monitor; keep tasks short |
| `critical` | ≥85°C | CLM compaction off; MLFQ concurrency=1; defer heavy jobs |
| `shutdown` | ≥95°C | All inference suspended; notify orchestrator |

## Local lane prose (moved from lane region, 2026-10-10, delivery-workflow budget trim)

On a model swap: update the "Currently running" header and `## Current Model Config`; add a thinking-suppression knob if the model has a reasoning mode (`enable_thinking: false` equivalent); update context budget guidance, `ai-stack.nix` `defaultModelCatalog`, `facts.nix` model entry; check MTP/speculative-decoding support; re-check `SAFE_COMMANDS` in `shell_tools.py` (no model-specific paths); run `aq-qa 0`. Full list: `.agent/lanes/local-reference.md`.

- Model thinking tokens: check `## Current Model Config` — disable if they suppress output
- GPU layers ceiling = 12, KV budget = 1.0 GB — never exceed without KV math

These limits come from the physical hardware — AMD Ryzen 7 PRO 5850U (Radeon Vega/Renoir APU).
They apply regardless of which model is loaded. Hitting them causes OOM kills or thermal shutdowns.

## Local lane prose (2) (moved from lane region, 2026-10-10, delivery-workflow budget trim)

Qwen3 emits reasoning tokens that produce empty `content` when unbounded — must be disabled OR capped via `thinking_budget`

Default: no thinking. Research/PRSI profiles use `{"enable_thinking": true, "thinking_budget": N}`

- Rule 5/22: Context-window-aware — compact after every 3-4 exchanges on small-window models; do not wait for the ceiling. Offload facts to MemoryBroker (:8003); query AIDB, never dump raw context.

- Rule 14: `users.users.<n>.homeMode = "0711"` is the idiomatic NixOS fix for a `0700` home blocking a service (alternative to activationScripts).

- Rule 17: Local Qwen is the intended default cheap-implementer lane for bounded single-file/single-command tasks; flagship remote models route down to it, not in place of it, whenever the task fits Qwen's measured envelope.

- **Reviewer**: review Gemini or Codex work when explicitly assigned reviewer authority

## Local header prose (moved from lane region, 2026-10-10, delivery-workflow budget trim)

> This config is intentionally model-agnostic. Model-specific knobs live in
> `## Current Model Config` below. Swap that section when changing models;
> everything else stays constant.

> **This section changes when the model changes. Everything else in this file stays.**
> When swapping models, update these values and run through the swap checklist below.
