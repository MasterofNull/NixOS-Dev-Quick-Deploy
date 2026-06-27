# PROMOTED-BUG-PATTERNS.md
# Shared across ALL agents (Claude, Gemini, Codex, Local/Qwen3)
# SSOT: this file. Derived from 175+ phases of development.
# Rule: bugs that hit 2+ sessions graduate here. All agents read this on session start.

**When to use:** Load at session start, before any coding task, before any service/Nix change.
**Where to find issues under active investigation:** `.agent/memory/issues-backlog.md`
**Where to seed RAG:** `python3 scripts/data/seed-rag-knowledge.py --collection error-solutions`

---

## NixOS / Systemd / Permissions

### ReadWritePaths/ProtectHome does NOT bypass POSIX DAC (CRITICAL)
`ReadWritePaths` + `ProtectHome=read-only` sets up a namespace bind-mount but the kernel still checks inode `uid/gid/mode`. A service UID blocked by a `0700` dir gets `EACCES` regardless of namespace grants. Fix pattern: `users.users.<n>.homeMode = "0711"` (idiomatic NixOS, applied via `install -d` in users activation script on every rebuild). Alternative: move config to `/var/lib/<service>/`. Always verify service access after adding `ReadWritePaths` for paths under `/home/`.

### NixOS non-hyperd service: 3-layer script access failure
Services running as non-hyperd users (ai-hybrid etc.) hitting scripts under /home/hyperd/ fail in three distinct layers: (1) bare `serviceConfig` → missing `ProtectHome` → CHDIR status=200; (2) `ProtectHome="read-only"` + shebang → noexec → EXEC status=203; (3) `${mcp.repoPath}` (live /home/hyperd path, mode 700) → DAC blocks non-hyperd → `[Errno 13]`. Fix for all three: `serviceConfig = commonServiceConfig // {...}` + explicit Nix store interpreter + `${toString repoSource}` script path (Nix store copy, world-readable, in ReadOnlyPaths). Pass `REPO_ROOT=mcp.repoPath` as env var for runtime repo access. Documented in nixos-system SKILL.md §3.

### Nix store EROFS: EVERY Python script running from repoSource needs REPO_ROOT env var (CRITICAL)
`repoSource = builtins.path {...}` produces a read-only Nix store copy. Any script using `Path(__file__).resolve()` to derive `_REPO_ROOT` then writing files (locks, telemetry, configs) gets EROFS. Fix: `REPO_ROOT = Path(os.environ["REPO_ROOT"]) if "REPO_ROOT" in os.environ else Path(__file__).resolve().parent.parent`. Add `REPO_ROOT=${mcp.repoPath}` to the service Environment. Child subprocesses inherit the env but MUST also check the env var themselves. Confirmed victims: aq-drop-daemon, training_ingest.py, aq-health-spider, apparmor-fix-agent.py, attention_queue.py.

### Shared JSONL write permission (CRITICAL)
Telemetry files created by ai-hybrid default to `0644` or `0640` (owner=ai-hybrid, group=ai-stack). When a second writer (e.g., hyperd running race-harness) needs to append, group write (`0664`) is required. Fix: NixOS tmpfiles `z` rule to relabel existing file + `f` rule to create new files with correct mode. Pattern: any JSONL written by 2+ service users needs `0664 owner group`. File: `mcp-servers.nix` tmpfiles block.

### commonServiceConfig ProtectHome=read-only silently blocks service subprocess writes to /home/ (CRITICAL)
Any systemd service using `commonServiceConfig` has `ProtectHome=read-only` — writes to `/home/hyperd/...` fail with EPERM at the namespace level, even when `ATTENTION_QUEUE_DIR` or `REPO_ROOT` env vars are correctly set. Subprocesses (aq-qa, scripts) inherit the mount namespace. Fix: add the specific path to `ReadWritePaths` override. Also add matching AppArmor `rwk` rules. Symptom for qa_check: empty stdout + exit 1.

### NoNewPrivileges=true blocks AppArmor Ux/Px (CRITICAL)
`NoNewPrivileges=true` in a systemd unit causes ALL AppArmor profile transitions (`Ux`, `Px`, `Cx`) to return EPERM before AppArmor fires. The only working mode is `ix` (inherit parent profile). Error surfaces as `EPERM` (errno 1), NOT `EACCES` (errno 13). Fix: change `Ux` → `ix` and add explicit `ix` rules for each subprocess binary. Applies to any service using `NoNewPrivileges=true`.

### Nix store path generalization
`path.split("/")` → parts = `["", "nix", "store", "hash-name", ...]`. `parts[3:]` gives everything after the hash-name. `parts[2:]` incorrectly keeps the hash-name in the wildcard rule. Correct: `"/nix/store/**/" + "/".join(parts[3:])`.

---

## AppArmor

### AppArmor `c` mode = parse failure (CRITICAL)
`c` is NOT a valid AppArmor profile file mode keyword — it's only an internal kernel audit mask. Using `rwkc` causes `apparmor_parser` to abort with `syntax error, unexpected TOK_ID`. The reload silently fails, leaving the old (wrong) profile active. File creation is covered by `w`. Correct SQLite rule: `rwk` (read+write+lock). Always verify profile loads: check `journalctl -u apparmor.service` after rebuild for `syntax error` lines.

### AppArmor SQLite needs `k` (file_lock)
Any SQLite DB path in an AppArmor profile needs `k` in addition to `rw`. Without `k`, `sqlite3.connect()` → `CREATE TABLE` → file lock fails with DENIED, making `_can_open_writable_db()` return False and cascading to wrong fallback paths.

### AppArmor glob dedup in fix-agent
Regex extracting existing rule paths from Nix source must use `/[a-zA-Z@_][^\s\"]*` not `/[^\s\"]*`. The looser pattern matches `/**` fragments from Nix interpolations like `${var}/**`, making every path falsely appear covered.

### AppArmor service /tmp directory access pattern
AppArmor rules for service paths must cover DIRECTORIES explicitly if the service uses `mkdir()`. `/tmp/*.db rwk` only covers files matching that pattern — NOT `mkdir("/tmp/workflow-templates")`. Directory creation blocked with EPERM even if read/write is allowed for files in that dir. Fix: redirect service paths to `/var/lib/<service>/` (already in ReadWritePaths + AppArmor rwk rules) rather than /tmp subdirs.

### apparmor-fix-agent must not crash on EPERM before attention queue push
When spawned from a service running as a non-owner user (e.g., ai-hybrid), NIX_FILE (mcp-servers.nix, owned hyperd:hyperd 644) write will fail with EPERM. REPO_ROOT env var fix makes NIX_FILE point to live repo (resolves EROFS) but does NOT grant write permission. Wrap `NIX_FILE.write_text()` in try/except OSError so execution always reaches the attention queue `push()` with `human_gate` + `rules_proposed` payload. File: `scripts/automation/apparmor-fix-agent.py` (f02281e8).

---

## Local Inference (Qwen3 / llama.cpp)

### role:"function" silent drop (CRITICAL)
Qwen3-35B chat template only knows `role:"tool"`. `role:"function"` is silently dropped — model never sees tool results, hallucinates on every subsequent turn. Always use `role:"tool"` for tool result messages in the agent loop.

### mixed prose+JSON parse break
`json.loads(full_response)` fails when model prepends prose before the JSON call. Use `rfind('{"function"')` to extract JSON. Pattern is in `tool_registry.parse_tool_call_from_llama`.

### frequency_penalty truncates dense JSON/code output (CRITICAL)
`frequency_penalty` in llama.cpp applies a cumulative penalty proportional to each token's total occurrence count in the entire context. In dense JSON schemas where `"` appears 300+ times, the logit penalty reaches `0.05 × 300 = 15.0`, making `"` effectively unprintable and causing early EOS at ~59-61 lines. Fix: set `frequency_penalty=0.0`. Loop protection is preserved by `repeat_penalty` + `repeat_last_n` (sliding window, not cumulative). Applies to ALL structured output tasks. File: `scripts/ai/lib/dispatch.py build_llama_payload`.

### local delegate 504 = token budget too large
Qwen3-35B at 1 tok/s floor. `delegated_response_budget()` cap=0 fallthrough → unbounded generation → 211s timeout. Fix: `_LOCAL_MAX_TOKENS_HARD_CEILING=180` (180s budget headroom). 256 also too large at 1 tok/s.

### Local agent synthesis truncated at 512 tokens (CRITICAL)
`agent_executor._call_llama()` used `AGENT_TOOL_CALL_MAX_TOKENS=512` for ALL model calls. Final synthesis after tool calls capped at 512 tokens → result=null, status=failed despite successful tool calls. Fix: two-phase budget — 512 for `tool_call_count==0`, `AGENT_TASK_MAX_TOKENS=1200` for `tool_call_count>0`. Files: `agent_executor.py` (b84528aa, cf9ff3fb).

### Local agent context overflow at 5+ tool calls
Tool results serialised without size cap → context exceeds n_ctx=8192. Fix: (1) `format_tool_result()` caps at 3000 chars with truncation notice; (2) per-iteration message pruning drops oldest assistant+tool pair when chars > 24768. File: `agent_executor.py`, `tool_registry.py` (b29e5983).

### local agent instruction file self-injection (token waste)
Local agent (Qwen3) may write OTHER agents' instruction files into its own LOCAL-AGENT.md via write_file tool. Separator: "--- Newly Discovered Project Context ---". Result: ~4300 extra tokens per session. Fix: truncate at the separator. Prevention guard added to WORKFLOW-CANON.md Step 7.

### llama.cpp flag syntax
`--flash-attn [on|off|auto]` — bare `--flash-attn` eats next arg as value. Always use `--flash-attn on` (explicit).

---

## Switchboard / Delegation

### Switchboard forces stream=True for local targets (CRITICAL)
`switchboard.py` lines 2598-2607 override `stream: false` → `stream: true` for all local chat/completions. But the override happens AFTER `is_stream = payload.get("stream") is True` (line 2609) so httpx uses the non-streaming path → truncated 2-chunk SSE (no usage, no [DONE]). Explicit `stream: true` from caller produces full 5-chunk SSE including usage. Fix chain (Ph107.2-107.3, Ph109.1): (1) `_parse_sse_response_body(text)` at all 3 parse sites; (2) `stream_options:{include_usage:True}` in delegate payload; (3) explicit `stream:True` in `_post_delegate()` for local profiles (Phase 109.1, 97ca8c94).

### retry_with_backoff infinite loop on 429/402 (CRITICAL)
`shared/retry_backoff.py` original implementation made RECURSIVE `return await retry_with_backoff(...)` calls on 402/429+Retry-After responses, resetting attempt counter to 0 → infinite loop. Any remote 402 (Payment Required) with Retry-After header caused the coordinator delegate handler to hang forever. Fix (Phase 108.2): replaced recursion with `continue` statements on the existing `for attempt` loop. 402 removed from retry-eligible codes. File: `ai-stack/mcp-servers/shared/retry_backoff.py`.

### mcp-bridge workflow tools contaminate harness repo on --target . (CRITICAL)
`retrofit_workflow`, `primer_workflow`, `brownfield_workflow`, `project_init_workflow` all called `_run_local(argv)` with no `cwd` arg, defaulting to `REPO_ROOT`. When external agents (Gemini CLI etc.) pass `--target .`, it resolves to the NixOS harness root — overwrites `.claude/CLAUDE.md`, `.agents/plans/README.md`, `.agent/` files. Fix: `_resolve_workflow_target()` normalises target to absolute path; all four dispatchers pass `cwd=abs_target`. External agents must always pass absolute path to their project, never `--target .`. File: `scripts/ai/mcp-bridge-hybrid.py` (f2530fe4).

### aq-agent-loop tool registration gap (CRITICAL)
`build_registry()` only registered file/shell/git tools by default — AI coordination tools (query_aidb, store_memory, get_hint, mesh_discovery, 10 more) were NEVER registered. Agents had 0 harness access. Fix (Phase 162A): add `from ai_coordination import register_ai_coordination_tools; register_ai_coordination_tools(registry)` to `build_registry()`. ALSO: `store_memory_handler` was a placeholder; `collective_memory_search_handler` called non-existent `/documents/search` → fix to `/vector/search`. Pattern: always verify tool count with `--list-tools` after adding a new tool module.

### Delegate success rate: classify failure modes before scoring (CRITICAL for scorecard accuracy)
Do NOT treat all `outcome=error` delegate failures uniformly. Separate: (1) `infra_startup_500` — coordinator crashed during nixos-rebuild restart; (2) `provider_error` — upstream 429/402/503; (3) `local_timeout` — hardware-bound local model. For `completion_reliability`, exclude (1) and (2) from denominator. Fix: `_compute_delegate_breakdown()` in `scripts/ai/aq-report` (1bfc427c). Before: 24h 80.0% → warn. After: 24h adj 92.3% → pass.

---

## Python / Backend

### Async blocking (CRITICAL)
NEVER synchronous file I/O inside `async def` aiohttp/FastAPI handlers. Pattern: extract to `_do_sync()`, call via `asyncio.to_thread(_do_sync, ...)`. Affects ANY large file read (audit logs, JSONL). Applies to ALL coordinator service handlers.

### psycopg3 `r._mapping` silent failure (CRITICAL)
psycopg2 used `RealDictRow._mapping`; psycopg3 returns plain tuples — `.mapping` raises `AttributeError`. Any `dict(r._mapping)` pattern with bare `except Exception: return []` silently returns empty results. Fix: `cols=[d.name for d in cur.description]; rows=[dict(zip(cols,r)) for r in cur.fetchall()]`. Hit `read_query_gaps()` in `aq-report` — query_gaps was silently [] for many sessions despite 657 rows in DB.

### store_agent_memory fire-and-forget returns "queued" not "stored" (CRITICAL)
`memory_manager.store_agent_memory()` is fire-and-forget (async background task via `asyncio.create_task`). Returns `{"status": "queued"}`, NOT `{"status": "stored"}`. Any code checking `status in {"stored", "skipped"}` will get stored=0. Fix: add `"queued"` to the accepted status set. Affects `memory_service.py`, fallback in `http_server_impl.py`.

### telemetry file rotation → stale checkpoint → 0 patterns (CRITICAL)
`continuous_learning.py _process_telemetry_file()` had no rotation detection. After log rotation, checkpoint pos > file size → `f.seek(past_EOF)` → `readline()` returns empty → 0 patterns per batch indefinitely. Fix (Phase 108.1): `os.path.getsize()` check before seek; reset to 0 if stale. File: `extensions/continuous_learning.py`.

### DUAL inline auth
`http_server.py` has `_is_loopback_agent_request()` at ~line 1412 with its own `agent_prefixes` tuple. Patch BOTH sites when adding loopback endpoints (not just core/auth_middleware.py).

### Coordinator endpoint 401 from loopback agents = missing LOOPBACK_AGENT_PREFIXES entry
When a local agent tool calls a coordinator endpoint and gets `{"error":"unauthorized","mode":"api-key"}`, the path is NOT in `LOOPBACK_AGENT_PREFIXES` in `middleware/auth.py`. Fix: add the prefix to the tuple, nixos-rebuild. Pattern: every new coordinator endpoint used by local tools needs an explicit entry. Affected path: `/search/` (Phase 162C fix 9b66c679).

### training_ingest quality score too harsh for structured outputs
`_quality_score()` uses keyword coverage — structured/code responses don't repeat query terms verbatim. `is_structured` base was 0.40; raise to 0.50. `agent_step_complete` events (verified DirectRunner outputs) should use floor 0.40, not 0.65. Without this, `samples_added=0` on every ingest run.

### journalctl --since needs local time
`datetime.fromtimestamp(ts, tz=timezone.utc).strftime(...)` produces UTC timestamp string. journalctl `--since` expects LOCAL time. Use `datetime.fromtimestamp(ts).strftime(...)` (no tz arg). UTC format returns no results silently.

---

## AIDB / RAG / Vector Search

### AIDB ALLOWED_COLLECTIONS stale — every vector search failed (CRITICAL)
`aidb/query_validator.py` ALLOWED_COLLECTIONS had 6 stale names (`nixos_docs`, `solved_issues`, `skill_embeddings`, `telemetry_patterns`, `system_registry`, `tool_schemas`) — NONE exist in Qdrant. All 14 real Qdrant collections (`error-solutions`, `skills-patterns`, `best-practices`, `codebase-context`, etc.) returned HTTP 400 "Unknown collection". Fix (Phase 175, 6f4c6b40): (1) `query_aidb_handler` detects 400 "Unknown collection" → falls back to embed-via-llama-embed(8081) + Qdrant-direct(6333); (2) `query_validator.py` ALLOWED_COLLECTIONS expanded; (3) ralph-wiggum `collection="solved_issues"` → `"error-solutions"`. **Pattern: verify AIDB collection names against `curl http://127.0.0.1:6333/collections` before assuming searches work. Use `error-solutions` not `solved_issues`.**

### AIDBClient stale /aidb/* endpoints (CRITICAL)
`shared/hybrid_client.py` had three stale /aidb/ prefixes: `vector_search→/aidb/search` (correct: `/vector/search`), `store_interaction→/aidb/interactions` (correct: `/history/record`), `health_check→/aidb/health` (correct: `/health`). Pattern: when adding new AIDB endpoints, search for `/aidb/` refs in `shared/hybrid_client.py` and callers.

### RAG collection empty = silent zero results
`error-solutions`/`skills-patterns`/`best-practices` were 2-36 pts of wrong-type content. Fix: `python3 scripts/data/seed-rag-knowledge.py --clear-wrong-type`. Re-run after adding new bug patterns to this file.

### score_threshold hardcoded (CRITICAL)
`http_server_impl.py` (3 sites) + `server.py` (3 sites) had `score_threshold=0.7` overriding `Config.AI_SEARCH_SCORE_THRESHOLD`. Always use `Config.AI_SEARCH_SCORE_THRESHOLD`. BGE-M3 calibrated default = 0.45 (options.nix). Low scores in sparse collections = content problem, not threshold problem — seed the collections.

### tool_security /control/* over-broad block
Default policy `blocked_endpoint_patterns: ["/control/*"]` blocks `ai_coordinator_delegate` + `impeccable_audit` (legitimate coordination tools). Fix: `endpoint_exempt_tools` in default policy. `danger_tool` must stay blocked — security test fixture.

---

## Dashboard / Frontend

### Dashboard JS SyntaxError
Use `chromium --headless=new --enable-logging=stderr --log-level=0 URL 2>&1 | grep CONSOLE` to diagnose. `--screenshot` is useless (first paint before XHR).

### JS fetch timeout
Every fetch in Promise.allSettled needs AbortController. Unbounded fetches block dashboard.

### Race view winner_detail agent_id/variant null
`_run_summary()` reads `agent_id` and `spec_variant` from events only. Race-run records from `race-runs.jsonl` carry `agent_id` and `variant` keys but these weren't enriched onto the summary. Fix: `setdefault` enrichment from `race_record` in both `list_agent_runs` and `get_agent_runs_race`. File: `dashboard/backend/api/routes/aistack.py`.

---

## Governance / Workflow

### Coverage gap → silent breakage
If a service has 0 aq-qa checks AND 0 dashboard panels it will break silently for days. **Governance contract: aq-qa + dashboard panel required before any feature/service is "done".** Check `ralph-wiggum/aider-wrapper/local_agent_runtime` pattern for future services.

### stray control chars in regexes
ASCII `\x08` (backspace) injected by editors corrupts regex patterns silently. Always verify regex with a test match after pasting.

### pre-archive-scan.sh required before mv
`scripts/governance/pre-archive-scan.sh <file>` exits 1 if any tracked file links to `<file>`. Run this BEFORE any `mv <file> .agent/archive/...` to prevent broken-link CI failures.

### VSCodium colorTheme stripped post-rebuild
`enforceVSCodiumTheme` activation hook patches `workbench.colorTheme` but if VSCodium is running it overwrites settings.json from in-memory state afterward. Fix: close VSCodium before `nrs`/`hms`. Manual recovery: `jq '.["workbench.colorTheme"]="Activate SCARLET protocol (beta)"' settings.json > tmp && mv tmp settings.json`.

---

*Last updated: 2026-06-26 | Maintained by all agents | Seed to RAG after adding patterns*
