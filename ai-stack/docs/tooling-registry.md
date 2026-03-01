# AI Stack Tooling Registry

Single source of truth for all tools, MCP servers, CLI scripts, agents, skills,
hooks, and integrations available to local and remote AI agents on this system.
Imported into AIDB as project=tooling-registry. Query via vector search to
discover what tools are available for a given task.

---

## MCP Servers (HTTP REST — running as systemd units)

| Name | Port | Auth | Key Endpoints | When to Use |
|------|------|------|---------------|-------------|
| **hybrid-coordinator** | 8003 | X-API-Key | POST /query, POST /augment_query, POST /memory/store, GET /memory/recall, GET /hints, POST /feedback, POST /harness/eval, GET /discovery/capabilities | Route queries between local/remote LLM; semantic search; agent memory; workflow hints; eval harness |
| **aidb** | 8002 | X-API-Key | POST /documents, GET /documents, POST /vector/search, POST /query, GET /health | Import/search documents; vector similarity search; knowledge base queries |
| **ralph-wiggum** | 8004 | X-API-Key (shared with aidb) | POST /tasks, GET /tasks/{id}, GET /health | Async task orchestration; multi-step agentic workflows |
| **aider-wrapper** | 8006 | — | POST /tasks, GET /tasks/{id}, GET /health | Code editing tasks via aider; sandboxed file modifications; AI-assisted development |
| **nixos-docs** | 8096 | optional | GET /health, GET /sources, POST /search, POST /sync | NixOS/nixpkgs documentation search; home-manager docs; nix.dev reference |
| **switchboard** | 8085 | — | POST /v1/chat/completions, GET /v1/models | OpenAI-compatible proxy; routes to local llama.cpp or remote; use as default model endpoint |

## MCP Servers (Claude Code — registered in ~/.claude/settings.json)

| Name | Transport | Capabilities |
|------|-----------|--------------|
| **filesystem** | stdio (npx) | Read/write files in project directory |
| **git** | stdio (npx) | Git operations, log, diff, status |
| **fetch** | stdio (npx) | HTTP fetch for web content |
| **memory** | stdio (npx) | Persistent key-value memory across sessions |
| **postgres** | stdio (npx) | Direct SQL queries to mcp database (port 5432) |
| **github** | stdio (npx) | GitHub API — PRs, issues, repos |
| **mcp-nixos** | stdio (nix run) | NixOS options search, package lookup, home-manager options |

## Infrastructure Services (not MCP but used by AI stack)

| Name | Port | Purpose |
|------|------|---------|
| **llama.cpp** | 8080 | Local LLM inference — Qwen3-4B-Instruct; OpenAI-compatible /v1/ API; tool calling enabled (--jinja) |
| **llama-cpp-embed** | 8081 | Embedding server — Qwen3-Embedding-4B; POST /embedding; 2560-dim, 4096 ctx |
| **PostgreSQL** | 5432 | Primary DB — aidb schema; query_gaps, imported_documents, eval_results tables |
| **Redis** | 6379 | Cache layer; semantic cache for hybrid-coordinator; session state |
| **Qdrant** | 6333 | Vector DB; collections: nixos_docs, documents, agent_memory |
| **Prometheus** | 9090 | Metrics scraping; hybrid_llm_backend_selections_total; hybrid_requests_total |
| **Grafana** | 3000 | Metrics dashboards |

---

## CLI Tools (in ~/Documents/NixOS-Dev-Quick-Deploy/scripts/)

| Command | Purpose | Key Flags |
|---------|---------|-----------|
| `scripts/aq-report` | 9-section AI stack performance digest | `--since=7d`, `--format=text\|json`, `--aidb-import` |
| `scripts/aq-hints` | Query workflow hints from hybrid-coordinator | `--format=json\|text\|shell-complete`, `--agent=TYPE`, `-q QUERY` |
| `scripts/aq-qa` | Phase-based QA runner for entire AI stack | `aq-qa 0` (all checks), `aq-qa 1` (infra), `aq-qa 2` (inference) |
| `scripts/aq-prompt-eval` | Evaluate prompt registry against canonical tests | `--strategy LABEL`, `--aidb-import` |
| `scripts/aq-gap-import` | Auto-import knowledge for top recurring query gaps | `MIN_OCCURRENCES=N`, `MAX_GAPS=N`, `SKIP_QDRANT_REBUILD=1` |
| `scripts/aq-optimizer` | Agentic self-optimization: reads aq-report JSON, applies safe routing/knowledge actions autonomously | `--dry-run`, `--since=Nd` |
| `scripts/run-eval.sh` | Full eval harness run | `--strategy LABEL` |
| `scripts/rebuild-qdrant-collections.sh` | Re-embed all AIDB documents into Qdrant | — |
| `scripts/check-mcp-health.sh` | Health check all 12 MCP services | `--optional` |
| `scripts/seed-routing-traffic.sh` | Send test queries to bootstrap metrics | `--count N` |
| `scripts/import-agent-instructions.sh` | Push CLAUDE.md/AGENTS.md/registry into AIDB | — |
| `scripts/sync-agent-instructions` | Regenerate AGENTS.md/.aider.md/.gemini/context.md from CLAUDE.md | — |
| `scripts/export-ai-behavior-snapshot.sh` | Export eval/hint/gap snapshots to ai-stack/snapshots/ | — |
| `scripts/seed-fresh-deploy.sh` | Full post-deploy knowledge seeding | — |
| `scripts/update-mcp-integrity-baseline.sh` | Refresh MCP source file hash baseline | — |

---

## Agent CLI Tools (in ~/.npm-global/bin/)

| Command | Role | Best For | Context |
|---------|------|----------|---------|
| `qwen` | Multi-file refactor, deep code analysis | >30 lines new code, architecture analysis | Large context window; use `-y` for auto-approve |
| `codex` | Pattern detection, security audit, test gen | Single module creation, inline fixes | QUOTA EXHAUSTED as of 2026-02-26; falls back to Claude |
| `gemini -p` | Web search, doc lookup | Quick reference checks, release notes | Free tier, limited quota; search-only |
| `pi` | Minimal terminal coding agent (read/write/edit/bash) | Bounded code editing tasks, file transforms, targeted fixes | Routes to switchboard; 4 tools only; fastest for small bounded tasks; `pi --provider openai` |

Use `@path/to/file` syntax to include files. Use `@dir/` for entire directories.

---

## Claude Code Skills (in ~/.claude/skills/)

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `/ai-stack-qa` | `/ai-stack-qa` | Run full AI stack health check suite (aq-qa phases 0-2) |
| `/commit` | `/commit` | Structured git commit with Co-Authored-By |
| `/review-pr` | `/review-pr NUM` | PR review workflow |
| `/pdf` | `/pdf` | PDF manipulation toolkit |
| `/mcp-builder` | `/mcp-builder` | Build new MCP servers |
| `/webapp-testing` | `/webapp-testing` | Playwright browser testing |
| `/nixos-deployment` | `/nixos-deployment` | NixOS deployment workflow |

---

## Systemd Timers (automated loops)

| Timer | Schedule | Action |
|-------|----------|--------|
| `ai-weekly-report.timer` | Sunday 08:00 | Run aq-report --aidb-import; MOTD refresh |
| `ai-import-agent-instructions.timer` | Monday 00:03 | Import CLAUDE.md/AGENTS.md/registry.yaml into AIDB |
| `ai-gap-import.timer` | Saturday 03:00 | PRSI: import knowledge for top recurring gaps → Qdrant rebuild |
| `ai-optimizer.timer` | Daily 06:00 | PRSI: aq-optimizer reads structured_actions → applies routing/knowledge overrides autonomously |
| `ai-sync-knowledge-sources.timer` | Monday weekly | Fetch and import enabled knowledge sources into AIDB |
| `ai-prompt-eval.timer` | Wednesday 02:00 | Run aq-prompt-eval; update prompt leaderboard in AIDB |
| `ai-security-audit.timer` | Monday 00:23 | pip-audit + npm audit; results to AIDB |
| `ai-mcp-integrity-check.timer` | Every 30 min | Validate MCP source file hashes |
| `ai-mcp-process-watch.timer` | Every 15 min | Monitor MCP process tree health |
| `ai-amdgpu-metrics-exporter.timer` | Hourly | AMD GPU metrics to Prometheus |

---

## Hooks and Feedback Loops

| Hook | Location | Trigger | Action |
|------|----------|---------|--------|
| Pre-commit syntax check | .githooks/pre-commit | git commit | bash -n, py_compile, nix-instantiate |
| Hint injection | aider-wrapper | Every aider task | Prepends top hint from /hints to prompt; writes hint-audit.jsonl |
| Hint adoption tracking | hint-audit.jsonl | Post-task | Records hint_id, accepted, task_id for aq-report §9 |
| Tool audit | tool-audit.jsonl | Every MCP tool call | Structured log: tool, args, duration, outcome |
| Eval harness | run-eval.sh | Manual / weekly timer | Scores prompts, updates leaderboard in AIDB |

---

## Prompt Registry (ai-stack/prompts/registry.yaml)

Pre-vetted prompt templates for common tasks. Use via aq-hints or direct AIDB query.

| Template | Purpose |
|----------|---------|
| `route_search_synthesis` | Combine local search results with LLM synthesis |
| `gap_detection_score` | Score query gaps and suggest documentation |
| `memory_recall_contextualise` | Recall agent memory and contextualise for current task |
| `aider_task_systems_code` | Systems-level code tasks for aider |
| `eval_scorecard_analysis` | Analyse eval scorecard and recommend improvements |
| `query_expansion_nixos` | Expand NixOS-specific queries for better retrieval |

---

## Agent Instruction Files (auto-generated by sync-agent-instructions)

| File | Used By | Contains |
|------|---------|---------|
| `AGENTS.md` | Codex, Qwen, OpenAI CLIs | Project rules, port policy, NixOS conventions |
| `.aider.md` | aider CLI (auto-loaded) | Aider-specific conventions, port policy |
| `.gemini/context.md` | Gemini CLI (auto-loaded) | Project context for web-search tasks |
| `CLAUDE.md` | Claude Code (auto-loaded) | Full project intelligence, agent coordination model |

Always run `scripts/sync-agent-instructions` after updating CLAUDE.md, then
`scripts/import-agent-instructions.sh` to push changes to AIDB.

---

## Key Architectural Rules for Agents

1. **Port policy**: Never hardcode ports. All ports in `nix/modules/core/options.nix`.
   Python reads from env vars. Shell uses `${PORT:-default}`.
2. **Tool selection**: Local llama.cpp for fast/offline tasks. Remote (Claude/Gemini)
   for complex reasoning. Hybrid-coordinator routes automatically via /query.
3. **Code changes >30 lines**: Delegate to Qwen (`qwen -y "..."`), not inline.
4. **Verify all Qwen/Codex output**: grep/read spot-check + py_compile/bash -n before commit.
5. **NixOS changes**: Use `lib.mkIf`, never `//` for conditional options.
6. **Secrets**: Always via sops, never hardcoded. Read from `*_FILE` env var paths.
