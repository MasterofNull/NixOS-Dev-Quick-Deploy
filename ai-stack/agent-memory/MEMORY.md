# Project Memory — NixOS-Dev-Quick-Deploy

## Key Documents
- `AI-STACK-IMPROVEMENT-PLAN.md` — primary cross-session task tracker (15+1 phases, 60+ tasks)
- `SYSTEM-UPGRADE-ROADMAP.md` — NixOS-level issue tracker (NIX-ISSUE-NNN format)
- `KNOWN_ISSUES_TROUBLESHOOTING.md` — resolved issues with recovery steps

## Agent Coordination Model — DEFAULT (hardcoded in CLAUDE.md §8)
- **Claude = Planner / Coordinator / Delegator / Auditor** — NOT bulk coder
- **Codex** → new modules, inline logic (>30 lines or new file) — QUOTA EXHAUSTED as of 2026-02-26; falls back to Claude writing directly
- **Qwen** → multi-file refactors, architecture analysis, deep code understanding; `qwen -y "..."` for auto-approve
- **Gemini** → web lookups only (free tier, limited quota)
- All three CLIs at `~/.npm-global/bin/` — prepend `export PATH="$HOME/.npm-global/bin:$PATH"` (codex 0.104.0, qwen 0.10.5, gemini 0.29.5)
- Verify all Qwen output: Grep/Read spot-check + py_compile/bash -n before commit

## Architecture Constraints (always enforce)
1. NixOS-first, flake-based — no bare pip install, no manual systemctl
2. Minimal footprint — DynamicUser, PrivateTmp, ProtectSystem, MemoryMax per tier
3. Hardware-tier aware — nano/micro/small/medium/large tiers
4. Platform-portable — x86_64, aarch64, SBC, embedded
5. **NEVER hardcode port numbers or service URLs.** Single source of truth: `nix/modules/core/options.nix`. Python services read URLs from env vars. Shell scripts use `${PORT:-default}`. NixOS modules reference options, never literal integers.
6. **Qwen/codex output MUST be verified before use.** Cross-check every file path/API ref with Grep/Read. Validate with py_compile/bash -n. Never blindly accept structural claims.

## Phase Completion Summary (2026-02-26)
- Phases 1–8: ALL COMPLETE (eval infra, routing, feedback, caching, harness)
- Phase 9: COMPLETE — disk pressure guard, telemetry rotation, PID lockfile, reload-model endpoint
- Phase 14.1.3: COMPLETE — HIGH_RISK_TOOL_KEYWORDS augmented
- Phase 14.2.1-2: COMPLETE — TieredRateLimiter
- Phase 15.x: COMPLETE — PromptInjectionScanner, ingestion rate limiting, secrets redaction
- Phase 12.1.x: COMPLETE — AppArmor profiles for llama-cpp (ai-llama-cpp) + MCP base (ai-mcp-base)
- Phase 12.3.x: COMPLETE — audit sidecar socket, syslog forwarding, audit JSONL
- Phase 12.4.x: COMPLETE — MCP integrity check + process watchdog (every 15 min)
- Phase 13.x: COMPLETE — SSRF protection, loopback isolation, outbound allowlist
- Phase 11.1.1: PARTIAL — lock files for ralph-wiggum/health-monitor/hybrid; aidb compiling; aider-wrapper version invalid
- Phase 14.1.1: COMPLETE — bubblewrap sandbox for aider subprocess (AI_AIDER_SANDBOX=true)
- Phase 16.x: COMPLETE — hardware-tier classifier, tier-aware models, platform guards, mkHardenedService, SBC host
- TC3: ALL PASS (TC3.1–TC3.5 except TC3.5.3)

## Key File Locations
- `ai-stack/mcp-servers/hybrid-coordinator/server.py` — live MCP server (~779 lines)
- `ai-stack/mcp-servers/aidb/server.py` — AIDB MCP server (main entry)
- `ai-stack/mcp-servers/aidb/settings_loader.py` — Settings class with env var loading
- `ai-stack/mcp-servers/shared/tool_audit.py` — structured audit log (Phase 12.3.1)
- `ai-stack/mcp-servers/shared/ssrf_protection.py` — SSRF validation for user-supplied URLs
- `ai-stack/mcp-servers/shared/telemetry_privacy.py` — secrets redaction for telemetry
- `ai-stack/mcp-servers/hybrid-coordinator/prompt_injection.py` — scanner + sanitize_query
- `ai-stack/mcp-servers/hybrid-coordinator/mcp_handlers.py` — dispatch_tool() + audit wiring
- `nix/modules/roles/ai-stack.nix` — main AI stack NixOS module
- `nix/modules/services/mcp-servers.nix` — MCP server systemd units + timers
- `nix/modules/core/options.nix` — all port options (single source of truth)
- `nix/modules/core/network.nix` — DNS, resolved, NM, captive portal detection (Phase WiFi fix)
- `scripts/testing/check-mcp-integrity.sh` — hourly source file integrity check
- `scripts/security/update-mcp-integrity-baseline.sh` — run after each deploy to refresh baseline

## API Corrections (verified against live codebase)
- AIDB ingest: `POST /documents` — fields: content, project, relative_path, title
- Hybrid query: `POST /query` — fields: query, mode, prefer_local, limit
- `force_remote` param does NOT exist; use `prefer_local=false`
- `backend` field in /query response = search route type, not "local"/"remote"
- Missing query → HTTP 400 (aiohttp, not FastAPI — not 422)

## Hardware (ThinkPad P14s Gen 2a — "large" tier)
- AMD Ryzen, 27 GB RAM, AMD iGPU (ROCm), NVMe nvme0n1
- `k10temp` driver, no thermald (Intel-only)
- systemd-boot, EFI UUID 8D2E-EF0C

## Critical SSRF Defect Fixed (2026-02-26)
- `create_ssrf_safe_http_client` was incorrectly applied to llama_cpp_client and aidb_client
- Both use plain HTTP to localhost — default policy blocks both → service startup failure
- Fixed: server.py uses plain httpx.AsyncClient for service clients; SSRF only for user-supplied URLs

## Deploy Status (2026-02-27)
All accumulated changes deployed successfully. System is healthy (12/12 MCP services pass health check).
Run `scripts/security/update-mcp-integrity-baseline.sh` to seed integrity baseline after first clean deploy.

## Phase 18 — COMPLETE (2026-02-27, commits f92ad3e + bfcb549)
All 18.1–18.5 tasks done except 18.2.3 (strategy_tag in tool_audit.jsonl, open).

## Key Phase 18 Files
- `scripts/ai/aq-report` — 8-section digest: tool perf, routing, cache, eval trend, strategy leaderboard, recommended prompts, gaps, recommendations
- `scripts/ai/aq-prompt-eval` — evaluates registry prompts vs canonical tests, updates mean_score
- `ai-stack/prompts/registry.yaml` — 6 vetted prompt templates (route_search_synthesis, gap_detection_score, memory_recall_contextualise, aider_task_systems_code, eval_scorecard_analysis, query_expansion_nixos)
- `run-eval.sh --strategy LABEL` — tags eval runs for leaderboard tracking
- MOTD: mySystem.aiStack.motdReport = true → /etc/profile.d/ai-report-motd.sh
- Timer: ai-weekly-report.timer (Sunday 08:00) + ai-weekly-report.service (--aidb-import)

## Phase 19 — COMPLETE (2026-02-27, commits e934c65 + 9105286)
- 19.1–19.2–19.3–19.4.1–19.4.4: ALL COMPLETE
- 19.4.5–19.4.6: PENDING (AIDB import of CLAUDE.md, local LLM system prompt)

## Key Phase 19 Files
- `ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py` — HintsEngine: 3 sources
- `scripts/ai/aq-hints` — CLI: --format=json|text|shell-complete, --agent=TYPE
- `scripts/ai/aq-completions.sh` — bash/zsh tab-complete; NixOS: mySystem.aiStack.shellCompletions
- `ai-stack/continue/config.json` — Continue.dev: aq-hints + llama.cpp + Ollama + Gemini + Claude
- `POST /hints` + `GET /hints?q=` — hybrid-coordinator; Continue.dev detects fullInput body
- `AI_HINTS_ENABLED=true` in aider-wrapper — prepends top hint to --message; hint-audit.jsonl tracking
- `aq-report §9` — Hint Adoption section (hint_adoption() reads hint-audit.jsonl)
- `AGENTS.md` — project rules injected for Codex/Qwen/OpenAI CLIs (sync-agent-instructions)
- `.aider.md` — aider-specific conventions (auto-loaded by aider CLI)
- `.gemini/context.md` — Gemini CLI project context (auto-loaded)
- `scripts/data/sync-agent-instructions` — regenerates agent files from CLAUDE.md

## NixOS Error Patterns — New (2026-02-27, commit 15d3db5)
| Error | Root Cause | Fix |
|---|---|---|
| Infinite recursion in `nixpkgs.overlays` | `pkgs.stdenv.hostPlatform.*` used inside overlay condition | Use `config.nixpkgs.hostPlatform.*` (pure NixOS option, no pkgs dep) |
| `security.apparmor.policies.<n>.enable` doesn't exist | Option renamed in nixpkgs | Use `state = "enforce"` (or "complain"/"disable") |
| AppArmor `HOMEDIRS` undeclared | Profile missing `#include <tunables/global>` before profile block | Add `#include <tunables/global>` as first line of `profile = ''` |
| `DynamicUser` service: Permission denied reading `/home/<user>` | Ephemeral UID can't traverse `0700` home dir | Use `User = svcUser; Group = svcGroup;` for any service needing repo access |
| systemd `Environment=` splits space-separated value | Unquoted spaces → separate tokens | Escape inner quotes: `"KEY=\"val1 val2\""` |
| Port conflict (Open WebUI vs Grafana both on 3000) | Grafana default is 3000; OWU was hardcoded | Added `ports.openWebui = 3001` in options.nix; OWU uses `ports.openWebui` |
| HM `programs.git.extraConfig` warning | Option renamed to `settings` | Use `programs.git.settings = { ... }` |

## Phase 11 — Agent Knowledge Portability (2026-02-27, commit 64cc7b5)
- 11.0.1 DONE: `_ensure_imported_documents_schema()` added to MCPServer — ALTER TABLE migrates source_trust_level + source_url on startup
- 11.0.2 DONE: MonitoringServer line 1607 fixed — `self._tiered_rate_limiter` → `self.mcp_server._tiered_rate_limiter`
- 11.1 DONE: `ai-stack/agent-memory/MEMORY.md` git-tracked; `scripts/data/import-agent-instructions.sh` created
- 11.0.3 + 11.2 PENDING: Requires `sudo systemctl restart ai-aidb.service` then `bash scripts/data/import-agent-instructions.sh`

## AIDB git hooks pre-commit rule (important)
`.githooks/pre-commit` blocks shell scripts (`.sh`) that use `echo "...${UPPERCASE_VAR}..."` without `-e` flag.
Use `printf 'msg %s\n' "${VAR}"` in all new shell scripts to avoid false positives.
Custom hooks path: `git config core.hookspath=.githooks`

## Phase 21 — Dev Tooling (DONE, commit a1d6256 + 7994d74)
- `scripts/ai/aq-qa`: phase runner — `aq-qa 0` → 26 pass / 0 fail / 2 skip (AppArmor needs --sudo)
  - Phase 0: all service/port/inference checks in one call
  - Phase 1: redis/postgres/qdrant/aidb/hybrid in one call
  - Unit name: llama-cpp-embed.service (not ai-embeddings.service)
- `.githooks/pre-commit`: run_syntax_check() added — bash -n / py_compile / nix-instantiate
- `~/.claude/skills/ai-stack-qa/SKILL.md`: Claude skill with port reference and token-efficient patterns
- `import-agent-instructions.sh`: now imports QA plan + 10 custom scripts under project=dev-tools
- All QA plan phases annotated with their primary tool (aq-qa, aq-report, aq-hints, etc.)

## Service Port Map (verified 2026-02-27)
| Service | Port | Auth Key Secret |
|---------|------|-----------------|
| Redis | 6379 | none |
| PostgreSQL | 5432 | /run/secrets/postgres_password (user=aidb) |
| Qdrant | 6333 | none |
| llama.cpp | 8080 | none |
| llama-embed | 8081 | none |
| AIDB | 8002 | /run/secrets/aidb_api_key (X-API-Key, 6 chars) |
| hybrid-coordinator | 8003 | /run/secrets/hybrid_coordinator_api_key |
| ralph-wiggum | 8004 | /run/secrets/aidb_api_key (SHARED with AIDB) |
| switchboard | 8085 | none (routing proxy) |
| Open WebUI | 3001 | none |
| Grafana | 3000 | none |
| Prometheus | 9090 | none |
Note: /run/secrets/ dir is not listable but individual files are readable by hyperd user.
ralph-wiggum TaskRequest field is `prompt` (not `task`).
AIDB POST /documents needs X-API-Key; GET /documents is open.
AIDB vector search endpoint: POST /vector/search (not /search).

## Phase 2 QA Status (2026-02-27, session ongoing)
- 2.1.x inference/embedding: ALL PASS
- 2.2.1-2 AIDB ingest/list: PASS (use X-API-Key for POST)
- 2.2.3 AIDB vector search: BLOCKED pending ai-aidb.service restart (embed URL fix in 6cffb83)
- 2.3.x hybrid coordinator: ALL PASS
- 2.4.x ralph-wiggum tasks: PASS (AIDB key shared, prompt field)
- 2.5.2 cosine similarity: PASS (0.714, strings from QA plan)

## Remaining High-Priority Open Work
- **Phase 21.4**: MCP tool `run_qa_check` in hybrid-coordinator (requires deploy)
- **Phase 21.5**: Post-deploy auto Phase 0 via `aq-qa 0` in nixos-quick-deploy.sh
- Phase 11.0.3 + 11.2: Run import after `sudo systemctl restart ai-aidb.service`
- Phase 11.1.1: aider-wrapper lock (aider-chat version invalid in requirements.txt)
- Phase 11.1.3: pre-deployment hash check in NixOS module
- Phase 12.2.2: Prometheus egress metrics
- Phase 18.2.3: strategy_tag in tool_audit.jsonl from route_handler.py
- Phase 19.4.5: AIDB import of CLAUDE.md + MEMORY.md for local LLM RAG (blocked on restart + 11.2)
- Phase 19.4.6: local LLM system prompt with top-3 CLAUDE.md rules (AI_LOCAL_SYSTEM_PROMPT=true)
- **Phase 20**: Full QA plan tracked in `AI-STACK-QA-PLAN.md` — 10 phases, ~65 discrete tests
