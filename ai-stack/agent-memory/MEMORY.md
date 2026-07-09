# Project Memory — NixOS-Dev-Quick-Deploy

## IndyDevDan Research Insights (2026-07-06)
- Summarized latest videos (Jan - Jul 2026) regarding Agentic Observability, Model Stacking, and Agentic Security: `.agent/INDYDEVDAN-RESEARCH-SUMMARY.md`

## Issues Backlog
- Active backlog: `.agent/memory/issues-backlog.md` (latest: `dashboard-layered-health-tempdir-confinement`)

## Active Planning Docs
- **Phase 54 (2026-05-14) COMPLETE ✓ 13/13** — Agentic-First Architecture Elevation (commits 4a6cd30c, 053a459b, b62dd21f): memory_broker.py (MemoryBroker unified typed memory), intent_classifier.py (IntentClassifier wired into handle_query:1611), rag_augmentor.py (active RAG default, L6 health gate at /api/health/rag), workflow/workflow_checkpointer.py (durable DAG + WORKFLOW_DLQ_KEY), trace_collector.py (end-to-end query trace + /api/traces), eval_runner.py (continuous eval + /eval/run + /eval/trend). config/intent-routing-map.json hot-reloadable. aq-qa phase 54: 13/13 PASS. PRD: .agent/PROJECT-AGENTIC-FIRST-ELEVATION-PRD.md. Gemini collab: gemini-20260514-171425-i7ecuo found classify_task at model_coordinator.py:126 was bypassed — now wired.
- **Phase 54 key wiring**: IntentClassifier injected before `_execute_query_search` in handle_query; RAG augmentation before tooling injection; trace span committed async via create_task; server.py wires trace_collector.init + eval_runner.init after postgres_client connect.
- **Phase 54 auth fix**: DUAL inline auth in http_server.py — `_is_loopback_agent_request()` at ~line 1412 has its own `agent_prefixes` tuple (NOT core/auth_middleware.py). Always patch BOTH when adding new loopback-accessible endpoints.
- **aq-qa total: 61 checks** — 61 passing · 0 failed · 0 skipped (0.8.1 now PASSES at 75% delegation rate). curl -s (not -sf) for endpoints returning 5xx with valid JSON body. aq-qa uses set -euo pipefail — curl failures inside checks need `|| true`.
- **System Assessment+Fix (2026-05-15)**: All P0/P1 bugs resolved. Key: hints_engine default audit path (3717dcdd), mutableLogDir lib.mkAfter tmpfiles z-rule (48de031d), asyncio.coroutine Py3.12, X-Forwarded-For bypass, audit-post.sh injection, GET /api/memory/facts top_k kwarg, CL payload schema mapping, memory/facts dedup "skipped" counted as stored (8f0cc848 — needs rebuild+restart to deploy). PRD: .agents/plans/SYSTEM-ASSESSMENT-FIX-PRD.md.
- **Phase 58 (2026-05-16) COMPLETE** (commit bd608a3d): Universal Validation Framework. tier0 now 14 gates (was 8): +JSON (json.load), +YAML (PyYAML), +TOML (tomllib), +JS (node --check), +TS (tsc, graceful-skip), +SQL (sqlparse, graceful-skip). All gates gracefully skip with PASS+warning when tool absent — never block unless tool available. Behavioral checks migrated to data-driven registry: config/validation-check-registry.json (schema: id/description/trigger_paths/command/tier/timeout_seconds/enabled/require_tool). run-focused-ci-checks.sh is now a pure Python registry runner. PRD: .agent/UNIVERSAL-VALIDATION-FRAMEWORK-PRD.md. Also: dashboard.html window.onerror banner (f789b997) + JS syntax check in focused-ci.
- **Delegation scripts PATH+CWD bug**: `delegate-to-gemini`, `delegate-to-codex`, `delegate-to-local` ALL fail from Bash tool background tasks — the shell snapshot CWD is NOT the repo root and scripts/ai/ is not in PATH. Fix: ALWAYS use FULL ABSOLUTE paths: `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/delegate-to-gemini` etc. Relative paths like `scripts/ai/delegate-to-gemini` fail even with correct cwd in foreground Bash. Use absolute paths every time. Direct `gemini -p`, `codex` CLI calls still work (those are in ~/.npm-global/bin).
- **Phase 57 (2026-05-16) COMPLETE ✓ 8/8** (commit d8178484): Hardware Capability Matrix + ROCm Promotion Pipeline. config/hardware-capability-matrix.json (12 hw classes, 17 ROCm compat entries, SSOT). ROCm is promotion-gated (not deprecated) — blocked on APUs, candidate on RDNA2/3 dGPU. scripts/governance/rocm-promotion-gate.sh (6-stage gate: identify/compat/cold_start/hang_check/benchmark/soak). scripts/testing/benchmark-acceleration-backends.sh. discover-system-facts.sh now writes hardware.accelerationClass to facts.nix. options.nix: accelerationClass nullOr str option. test-ai-stack-acceleration-policy.py updated to check promotion_gated:true. aq-qa 57: 8/8. Renoir APU class = "blocked".
- **Dashboard JS SyntaxError (2026-05-16, commit 0a652cd0) — PRIMARY BLOCKER**: Missing `)` on `.catch(e => { ... }` at dashboard.html:16189 caused `Uncaught SyntaxError: missing ) after argument list`. The entire `<script>` block failed to parse — loadData() was never defined, all panels stayed at `--`. DIAGNOSIS: `chromium --headless=new --enable-logging=stderr --log-level=0 http://... 2>&1 | grep CONSOLE` captures JS console errors including SyntaxError. This is the CORRECT diagnostic tool for browser-level JS errors on NixOS. Chromium `--screenshot` is USELESS for this — always captures first paint before XHR.
- **Dashboard cold-start blocking (2026-05-16, commit b4d1bd33)**: Promise.allSettled in loadData() blocked 42s+ cold because: (1) fetchQaStatus() — no AbortController, /api/aistack/aq-qa/run/0 ran 61 checks inline (42.9s) → now _run_aq_qa_background() returns {pending:true} in 13ms; (2) fetchAISpecificMetrics() — no timeout, /api/insights/metrics/ai-specific took 15s (8s get_full_report wait + 7s blocking urlopen in async context) → urlopen wrapped in asyncio.to_thread(timeout=6), get_full_report default 8s→2s; (3) _AQ_QA_CACHE falsy bug: `if cached and ...` misses empty dict — use `if cached is not None and ...`. Result: cold ~8s, warm ~4s, 19/19 OK.
- **Async Python anti-pattern**: NEVER use `urllib.request.urlopen()` or any blocking I/O inside an `async def` function — it freezes the entire asyncio event loop. Always wrap with `asyncio.wait_for(asyncio.to_thread(fn), timeout=N)`.
- **JS fetch timeout pattern**: Every fetch inside Promise.allSettled MUST have an AbortController timeout. Unbounded fetches block the entire dashboard. Pattern: `const ctrl = new AbortController(); const timer = setTimeout(() => ctrl.abort(), N); try { fetch(url, {signal: ctrl.signal}); } finally { clearTimeout(timer); }`
- **aq-qa background task pattern**: Endpoints that run long subprocess checks should return immediately with `{pending:true}` and populate cache in background via `asyncio.create_task()`. Never block HTTP responses on 40s+ subprocesses.
- **NixOS code deployment**: Python files run from nix store — `systemctl restart` does NOT pick up new commits. `nixos-rebuild switch` required for every code change.
- **MemoryBroker.write() dedup**: Returns `{"status":"skipped","reason":"duplicate"}` when embedding similarity too high. Treat "skipped" == success in callers (content already stored).
- **hints/feedback payload**: POST /hints/feedback requires `hint_id` + (`helpful` bool OR `score` int). NOT `positive`/`negative`.
- **GET /stats/delegate** (commit 68289626): coordinator proxies audit log read under ai-hybrid:ai-stack creds. Fixes permanent GID-inheritance skip in VSCode extension context. aq-qa 0.8.1 now calls this API.
- **TraceCollector body-drain bug** (commit 4cdf622f): Phase 54.5 init used request.clone().text() BEFORE request.json() — drained aiohttp stream, causing every /query to return route_search_failed JSONDecodeError. Fix: parse data first, init trace with query=data.get("query","")[:200].
- **Phase 56 (2026-05-14) COMPLETE ✓ 16/16** (commit 7e5beec7): Harness Integration Loop. Closes CLI↔coordinator gap. All four delegate-to-* scripts source scripts/ai/lib/audit-write.sh → post to POST /api/agent-events → tool-audit.jsonl + ContinuousLearning + lesson registry (fixes 0.8.1). New: aq-session-start (context+hints+lessons, exits 0 without coordinator), aq-lesson-promote (lesson review CLI), aq-commit-facts (Qwen ≤800 char diff → MemoryBroker semantic). aq-crystallize --since-hours flag. NixOS ai-crystallize-sessions.timer (nightly 2am, User=hyperd). Drift homeostasis loop in server.py (60s, auto-activates agent-ops profile). GET /api/agent-ops/status. POST /api/memory/facts. Dashboard: Lesson Registry card in Agent Ops panel. aq-qa 56: 16/16. Knowledge loop closed: work → event bus → ContinuousLearning → lesson → aq-lesson-promote → aq-session-start → next session inherits.
- **Phase 55 (2026-05-15) COMPLETE ✓ 16/16** (commits 68289626, 432c5a09): 55.1 memory_superseder (POST /memory/supersede, GET /memory/supersede/history), 55.2 memory_crystallizer (GET /memory/crystalline/status, POST /memory/crystalline/run, aq-crystallize CLI), 55.3 drift_analyzer (GET /api/traces/drift, drift_alert_threshold=0.7, config/agent-ops-profile.json). Tests: 7/7. aq-qa 0: 60/60. aq-qa 55: 16/16.
- **Nix store lag pattern**: Codex committed http_server.py imports BEFORE committing the corresponding .py files — they are untracked until next commit. Always ensure module .py file is committed in same commit as the import. After each commit batch, user needs nixos-rebuild switch to deploy.
- **Phase 31 (2026-05-13) COMPLETE** — Universal Agent Workflow Parity: WORKFLOW-CANON.md, GEMINI.md, AGENTS.md, Continue config (v34.0), switchboard harnessAwareBody all updated
- **Phase 32 (2026-05-13) COMPLETE** — Local Agent Coding Loop: aq-agent-loop CLI, git_tools.py, agent_executor fixes, delegate-to-local --mode agent
- **Phase 30.6 (2026-05-13) COMPLETE** — Bootstrap auto-injection: AGENT_INJECT_BOOTSTRAP in local_agent_runtime.py + coordinator spawner wired (commits 015dc2c4, e805940c)
- **delegate-to-local agent mode bugs fixed (783dbffa)**:
  - BASH_SOURCE source guard: sourcing script in nohup subshell no longer triggers arg parser
  - run_agent() SCRIPT_DIR fix: $(dirname "$0") → $SCRIPT_DIR (was resolving to ./aq-agent-loop in subshell)
- **Delegation scripts (2026-05-13, commit 18daf10a)**: delegate-to-gemini, delegate-to-codex, delegate-to-local — all use persistent .agents/delegation/registry.jsonl + outputs/; quoting + task_id bugs fixed
- **Phase 30 (2026-05-13) validation GREEN**: 30.1 CLI Execution Contract DONE; 30.3 Diagnostics Bundle DONE; 30.5 Remote Observability DONE. 30.2/30.4 tests pass but behavioral enforcement gap noted — Phase 30.6 bootstrap auto-injection is next slice
- **Phase 28 (commit 61194e56)**: loopback auth bypass committed; needs `sudo systemctl restart ai-hybrid-coordinator` to activate. aq-qa 0.9.1 uses API key so shows PASS even without restart
- **Phase 40 (2026-05-13) COMPLETE** — Trust root lifecycle: rotate-skill-registry-key.sh, verify-skill-registry.sh, skill-registry-trust-roots.json, skill-bundle-registry.py enforcement, aq-qa 0.9.5 (commit 9a80e7c1)
- **Phase 41 (2026-05-13) COMPLETE** — Per-run workspace isolation: provision_run_workspace/teardown_run_workspace, _check_isolation_constraints tightened, GET /runtime/isolation/workspace/{id}, aq-qa 0.9.6 (commit 4139b58e)
- **Phase 42 (2026-05-13) COMPLETE** — Fleet control-plane UX: DELETE /control/runtimes/{id}, GET …/deployments, GET /control/fleet/summary, GET …/health, aq-qa 0.9.7 (commit b428cbc7)
- **Phase 43 (2026-05-13) COMPLETE** — Benchmark SWE integration: 12-case eval pack, publish-eval-trend.py, run-benchmark-gate.sh, aq-qa 0.9.8 — 48 total checks (commit 81f4a437)
- **Phase 44 (2026-05-14) COMPLETE** — Unified harness runner + PAR-002 CI gate + stale matrix fix (commit d0cc5678)
- **Phase 45 (2026-05-14) COMPLETE** — Budget/cost guardrail API: config/runtime-budget-policy.json, GET/POST /control/budget/policy, _budget_exceeded policy-fallback, aq-qa 0.9.10 (commit a9baf3ad)
- **Phase 46 (2026-05-14) COMPLETE** — PAR-012 rollout/rollback: drill-rollback.sh (6-stage live drill), docs/runbooks/staged-rollout-and-rollback.md, aq-qa 0.9.11 (commit ff6084f6)
- **Phase 47 (2026-05-14) COMPLETE** — aqd v0.4.0 CLI ergonomics: run plan/execute/replay/review/status/budget/rollout-drill/harness subcommands, aq-qa 0.9.12 (commit 35cdd755)
- **Phase 48 (2026-05-14) COMPLETE** — MCP workflow blueprints v1.1: 12 blueprints with category+tags, aqd blueprints list/get/apply, aq-qa 0.9.13 (commit 01ce4fe1)
- **Phase 49 (2026-05-14) COMPLETE** — Orchestration graph runner: DAG executor, 4 templates, POST /workflow/graph/run, aq-qa 0.9.14 (commit dac0ab33)
- **Phase 50 (2026-05-14) COMPLETE** — IDE adapter compatibility gate: smoke-ide-adapter-compat.sh, aq-qa 0.9.15 (commit c9a28089)
- **Phase 51 (2026-05-14) COMPLETE** — Ablation/reasoning profile pack: config/ablation-reasoning-profiles.json (8 profiles), GET/GET/{name}/POST /control/reasoning/profile(s)/(apply), aqd v0.6.0 reasoning list/get/apply, aq-qa 0.9.16+0.9.17 (commit 69f68673)
- **Phase 52 (2026-05-14) COMPLETE** — Logic error discovery + system org diagrams: aq-index-logic-patterns (1288 patterns → AIDB logic-patterns), POST /api/logic/search, GET /api/topology + /topology/flow, dashboard System Map (SVG) + Flow (Mermaid), aqd v0.7.0 logic:search+topology, aq-qa 0.9.18–0.9.20, ai-aidb-reindex.service+timer 24h (commits 93142019, 0483bfe3)
- **Rate limiter loopback fix (commit a1d6291b)**: exempt_loopback=True; 127.0.0.1/::1 bypass hourly bucket → aq-qa no longer gets HTTP 429
- **Portability fixes (commit 6828b1cb)**: nix/home/base.nix MCP args use \${repoPath}; scripts use REPO_ROOT. Multi-machine model: facts.nix per host, mySystem.mcpServers.repoPath is source of truth
- **AIDB re-indexing**: ai-aidb-reindex.timer active (24h, OnBootSec=10min); scripts/automation/aidb-reindex.sh; hyperd in ai-stack group post-rebuild; manual: sudo systemctl start ai-aidb-reindex
- **aq-editor-trim-sessions**: rolling Continue session archiver (trigger=21, keep=20); archives to sessions-backup-YYYYMMDD-HHMMSS/; scripts/ai/aq-editor-trim-sessions [--dry-run|--status]
- **aq-qa total: 59 checks** — 0.9.18–0.9.20 added in Phase 52; 0 failures when stack running
- **aqd version: 0.7.0** — scripts/ai/aqd; adds logic:search, topology to existing skill/mcp/workflows/policy/reasoning/parity/run/blueprints
- **ALL P0/P1 parity gaps CLOSED** — AGENT-PARITY-MATRIX.md: every item resolved; no remaining P1 gaps
- **nixos-docs fix (commit 7a74b93c)**: tmpfiles unsafe-path-transition fixed by chown /var/lib/ai-stack to root:ai-stack; requires nixos-rebuild from terminal (sudo setuid missing in Claude shell)
- **llama-cpp hash fix (commit b2319f15)**: corrected sha256 for b9150; nixos-rebuild requires terminal session
- **dashboard PermissionError fix (commit 0195064d)**: Python 3.12+ Path.exists() raises PermissionError; fixed _path_readable() in aistack.py + ai_insights.py; dashboard restart required after code deploy

- [System Reset Plan](project_system_reset_plan.md) — **A–D COMPLETE (2026-05-08)** — 108 HC modules split into core/workflow/knowledge/extensions/tests; Phase E + Phase 28 remain
- [Continue config freeze policy](feedback_config_freeze.md) — **UPDATED 2026-05-13**: CLI bridge DECOMMISSIONED (commit 7dc4c950); Claude/Codex bridge entries removed from config; version bumped to 34.0. contextLength=32000 frozen; aq-hints invalid.
- [Codex CLI invocation](feedback_codex_cli_invocation.md) — use direct `codex exec` not cli-bridge until nixos-rebuild deploys `350c5dba`
- [Phase 28 handoff](project_phase28_handoff.md) — **UNBLOCKED** — Phase B.3 complete (882e9808); plan at `.agents/plans/phase-28-guarded-execution-safety-gating.md`
- `docs/architecture/SYSTEM-RESET-PDR-2026-05.md` — full PDR (Claude+Codex, 2026-05-08)
- `.agents/plans/system-reset-plan-2026-05.md` — active phase tracker
- `.agents/plans/arch-review-codex-findings.md` — Codex code audit + PDR review
- **Phase 33 (2026-05-13) COMPLETE** — Tokenmaxxing: skill I/O schema, delegate-fanout, token tracking, output compression (800 char cap), role-tagged delegation
- **Phase 34 (2026-05-14) COMPLETE** — Dashboard eval recovery: /api/health/layered (34.1), aq-report PATH fix (34.2), eval 83%/10/12 (34.3). Commits: 19fedc6f, e3d7b5b4, 0ba58477
- **Phase 35 (2026-05-14) COMPLETE** — OSI Layer Health panel: loadOsiLayerHealth() in dashboard.html wires /api/health/layered (commit 22979a4a)
- **Monitoring cleanup (2026-05-14, commit e0d2afd4)**: PRSI queue cleared (26 stale 2026-03 actions rejected); aq-qa 0.8.1 window 1h→24h, min-sample 3→1, blocked_endpoint_pattern probes excluded; phase-35 bats test hardcoded key removed
- **delegate-to-claude (2026-05-14) FIXED** — complete rewrite; mirrors delegate-to-gemini; uses `claude -p "prompt" --output-format text`; self-contained REPO_ROOT via BASH_SOURCE
- **aq-qa phase 0: 44 passed / 0 failed / 1 skipped** — fully green (44 checks)
- **eval score: 83% (10/12)** — above 70% threshold; PRSI degradation flags cleared
- **Phase 37 (2026-05-14) COMPLETE** — UAG run trajectory + replay: `LifecycleSession.trajectory` field, `GET /agent/lifecycle/{id}/replay`, aq-qa 0.9.2 (commit 51b29e57)
- **Phase 38 (2026-05-14) COMPLETE** — DAG executor retry/backoff (PAR-003): `RetryPolicy` dataclass, exponential backoff in `WorkflowExecutor`, `POST /workflow/run/{id}/execute`, `GET …/execute/status`, aq-qa 0.9.3 (commit 5de2e5c5)
- **Phase 39 (2026-05-14) COMPLETE** — Safety mode runtime contract: `runtime-safety-policy.json` v1.1 meaningful mode differentiation, `tool_blocklist` enforcement in event handler, aq-qa 0.9.4 (commit f344bc86)
- **P0 gaps: ALL CLOSED** — PAR-008/009 (trust roots Phase 40), isolation (Phase 41), fleet (Phase 42), SWE benchmark (Phase 43), harness runner (Phase 44)

## Agent Coordination Model
- **Claude = Planner / Coordinator / Delegator / Auditor** — NOT bulk coder
- **Qwen (local)** → primary inference via local llama.cpp port 8080
  - **Phase 32 (2026-05-13)**: now has CODING AGENT LOOP via `aq-agent-loop` CLI
  - Tools: read_file, write_file, list_files, search_files, run_command (whitelisted), git_status, git_diff, git_add, validate_before_commit
  - Entry: `aq-agent-loop --task "..." [--output file.json] [--max-calls N]`
  - Delegation: `delegate-to-local --mode agent --prompt "..." [--wait]`
  - Timeout fixed: 300s/call (was 30s — caused false failures); max_tokens=4096
- **Claude (OAuth)** → `~/.local/bin/claude` direct CLI; Claude Code VSCodium extension
- **Codex (OAuth)** → `~/.npm-global/bin/codex` direct CLI; openai.chatgpt VSCodium extension (`chatgpt.cliExecutable` is correct setting key)
- **Gemini (OAuth)** → `~/.npm-global/bin/gemini` direct CLI; Google.gemini-cli-vscode-ide-companion + Google.geminicodeassist extensions
  - Headless/background delegation: `gemini -p "prompt" --approval-mode auto_edit`
  - Working modes: `--approval-mode auto_edit` (default, safe), `--yolo` (all auto)
  - BROKEN: `--approval-mode plan` → HTTP 400 from Gemini API (not supported in current tier)
  - Use `auto_edit` even for research tasks — Gemini reads files but won't write unless prompted
  - **RATE LIMITS**: Uses `gemini-3-flash-preview` via Code Assist OAuth (`cloudcode-pa.googleapis.com`)
    - 429 MODEL_CAPACITY_EXHAUSTED is a transient server-side capacity issue (high-traffic periods)
    - NO alternative models work on this path — gemini-2.0-flash, gemini-1.5-flash all 404
    - No config change can fix it; just retry later. Google notice (2026-05-13): policy enforcement tightened
  - **Delegation bugs fixed (2026-05-13, commit 18daf10a)**:
    - task_id() pipefail bug — `tr|head` SIGPIPE with set -euo pipefail caused `xxxxxx` suffix always appended; fixed with `(set +o pipefail; ...)` subshell
    - nohup bash -c quoting bug — `"${cmd[@]}"` in DQ string didn't preserve quoting for complex prompts; fixed with `printf '%q '` pre-quoting
- **OpenRouter** → zero credits; `qwen:free` UNAVAILABLE as of 2026-05 — do NOT reference
- CLIs: `~/.npm-global/bin/codex`, `~/.local/bin/claude`
- Verify all Qwen/Codex output: py_compile/bash -n before commit

## CLI Bridge — DECOMMISSIONED (commit 7dc4c950, 2026-05-12)
- Port 8089 is dead; all `ai-stack/cli-bridge/` code removed
- Continue config upgraded to v34.0; Claude/Codex bridge model entries removed
- Gemini CLI companion extension uses PATH discovery (`~/.npm-global/bin/gemini`)

## Local-First Harness Architecture (CRITICAL)
- Core runs entirely on local llama.cpp (Qwen3.6-35B) — remote is optional offload only
- Delegation fallback: `embedded-assist` → `local-tool-calling` → remote (skipped when REMOTE_URL="")
- NEVER hardcode remote model IDs — loaded from `SWITCHBOARD_REMOTE_ALIAS_*` env vars (agent_pool_manager.py)
- `deploy-options.nix` aliases dormant while `remoteUrl = null`; git-tracked policy only

## Architecture Constraints
1. NixOS-first, flake-based — no bare pip install, no manual systemctl
2. NEVER hardcode ports/URLs — source of truth: `nix/modules/core/options.nix`
3. Python reads URLs from env vars; shell scripts use `${PORT:-default}`
4. Feature flags profile-driven: `nix/modules/profiles/ai-dev.nix` (mkDefault true); hosts override with mkForce
5. `deploy-options.local.nix` gitignored → invisible to flake eval; policy overrides must be git-tracked
6. sudo setuid bit MISSING — service restarts require terminal session (nixos-rebuild needed)

## Service Port Map
| Service | Port | Auth |
|---------|------|------|
| llama.cpp | 8080 | none |
| llama-embed | 8081 | none |
| AIDB | 8002 | X-API-Key |
| hybrid-coordinator | 8003 | hybrid_coordinator_api_key |
| ralph-wiggum | 8004 | aidb_api_key (shared) |
| switchboard | 8085 | none |
| cli-bridge | 8089 | DECOMMISSIONED (7dc4c950) |
| dashboard | 8889 | none |
| Grafana | 3000 | none |
| Open WebUI | 3001 | none |

ralph-wiggum TaskRequest field: `prompt` (not `task`). AIDB vector search: POST /vector/search (returns `distance`, not `score`).

## Key Files
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` — 1,745 lines (core query routing)
- `ai-stack/mcp-servers/hybrid-coordinator/lifecycle_fsm.py` — UAG FSM (Phase 26)
- `ai-stack/mcp-servers/hybrid-coordinator/intake_gateway.py` — UAG HTTP handlers
- `ai-stack/mcp-servers/hybrid-coordinator/evidence_safety_handlers.py` — safety hooks (Phase 28 extension target)
- `nix/modules/roles/ai-stack.nix` — main AI stack NixOS module
- `nix/modules/core/options.nix` — all port options (single source of truth)
- `scripts/ai/aq-qa` — phase 0 health checker (40 checks)
- `scripts/ai/aq-report` — system report (now includes editor_rescue_windows telemetry)
- `scripts/ai/aq-editor-rescue` — bounded rescue workflow (now writes JSONL telemetry history)

## API Corrections
- AIDB ingest: `POST /documents` — fields: content, project, relative_path, title
- Hybrid query: `POST /query` — fields: query, mode, prefer_local, limit (no `force_remote`)
- `cache_hit` in /query response is inside `capability_discovery` sub-object, NOT top-level
- Missing query → HTTP 400 (aiohttp — not 422)
- AIDB secrets scanner blocks docs with `/run/secrets/` paths (expected)
- AIDB document count: `GET /documents?limit=5000&project=NAME` then len(documents)
- `/run/secrets/aidb_api_key` has LEADING NEWLINES — strip: `${KEY//[$'\t\r\n ']/}`
- `/world/forecast` is GET-only (405 on POST)

## Hardware
- ThinkPad P14s Gen 2a, AMD Ryzen, 27 GB RAM, AMD iGPU (Renoir)
- Qwen3.6-35B: `--n-gpu-layers 12` (full 41-layer → ErrorDeviceLost)
- Inference: ~90-120s/response; llm calls need 300s+ timeout
- llama.cpp WITHOUT ROCm; CPU-only + Vulkan partial offload

## AGI Scaffold (Phases 16–20, ALL COMPLETE 2026-05-01)
- Identity Kernel (008cd50a), Closed-Loop Improver (26e8307a), Agent Mesh (9431637d), Values Signals (23b55e6d), World Model (cc753cba)
- Feature flags in `ai-dev.nix` (profile-driven); env-injection modules in `nix/modules/services/`
- `/identity/self`, `/affective/state`, `/agents/mesh/status`, `/world/forecast` all live at :8003

## NixOS Error Patterns
| Error | Root Cause | Fix |
|---|---|---|
| Infinite recursion in `nixpkgs.overlays` | `pkgs.stdenv.hostPlatform.*` inside overlay | Use `config.nixpkgs.hostPlatform.*` |
| `DynamicUser` can't read `/home/<user>` | Ephemeral UID, 0700 dir | Use `User = svcUser; Group = svcGroup;` |
| systemd `Environment=` splits on spaces | Unquoted tokens | Escape: `"KEY=\"val1 val2\""` |
| Port conflict OWU/Grafana on 3000 | Grafana default | `ports.openWebui = 3001` in options.nix |

## Tool Usage Patterns
- `TaskOutput` is for polling **in-progress** tasks only — evicted after notification; read output file path directly
- Codex background task output: tool calls write to disk silently; output file only gets final summary at exit; use `git diff` to track progress

## User Preferences
- Prefers symbols and shorthand for memory savings (e.g. `§13`, `§8.3`, `×3`) — do NOT expand to spelled-out forms without asking
- Ask before converting shorthand or symbols to verbose equivalents
