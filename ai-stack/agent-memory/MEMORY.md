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
- `scripts/check-mcp-integrity.sh` — hourly source file integrity check
- `scripts/update-mcp-integrity-baseline.sh` — run after each deploy to refresh baseline

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
Run `scripts/update-mcp-integrity-baseline.sh` to seed integrity baseline after first clean deploy.

## Phase 18 — COMPLETE (2026-02-27, commits f92ad3e + bfcb549)
All 18.1–18.5 tasks done except 18.2.3 (strategy_tag in tool_audit.jsonl, open).

## Key Phase 18 Files
- `scripts/aq-report` — 8-section digest: tool perf, routing, cache, eval trend, strategy leaderboard, recommended prompts, gaps, recommendations
- `scripts/aq-prompt-eval` — evaluates registry prompts vs canonical tests, updates mean_score
- `ai-stack/prompts/registry.yaml` — 6 vetted prompt templates (route_search_synthesis, gap_detection_score, memory_recall_contextualise, aider_task_systems_code, eval_scorecard_analysis, query_expansion_nixos)
- `run-eval.sh --strategy LABEL` — tags eval runs for leaderboard tracking
- MOTD: mySystem.aiStack.motdReport = true → /etc/profile.d/ai-report-motd.sh
- Timer: ai-weekly-report.timer (Sunday 08:00) + ai-weekly-report.service (--aidb-import)

## Phase 19 — COMPLETE (2026-02-27, commits e934c65 + 9105286)
- 19.1–19.2–19.3–19.4.1–19.4.4: ALL COMPLETE
- 19.4.5–19.4.6: PENDING (AIDB import of CLAUDE.md, local LLM system prompt)

## Key Phase 19 Files
- `ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py` — HintsEngine: 3 sources
- `scripts/aq-hints` — CLI: --format=json|text|shell-complete, --agent=TYPE
- `scripts/aq-completions.sh` — bash/zsh tab-complete; NixOS: mySystem.aiStack.shellCompletions
- `ai-stack/continue/config.json` — Continue.dev: aq-hints + llama.cpp + Ollama + Gemini + Claude
- `POST /hints` + `GET /hints?q=` — hybrid-coordinator; Continue.dev detects fullInput body
- `AI_HINTS_ENABLED=true` in aider-wrapper — prepends top hint to --message; hint-audit.jsonl tracking
- `aq-report §9` — Hint Adoption section (hint_adoption() reads hint-audit.jsonl)
- `AGENTS.md` — project rules injected for Codex/Qwen/OpenAI CLIs (sync-agent-instructions)
- `.aider.md` — aider-specific conventions (auto-loaded by aider CLI)
- `.gemini/context.md` — Gemini CLI project context (auto-loaded)
- `scripts/sync-agent-instructions` — regenerates agent files from CLAUDE.md

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

## Remaining High-Priority Open Work
- Phase 11.1.1: aider-wrapper lock (aider-chat version invalid in requirements.txt)
- Phase 11.1.3: pre-deployment hash check in NixOS module
- Phase 12.2.2: Prometheus egress metrics
- Phase 18.2.3: strategy_tag in tool_audit.jsonl from route_handler.py
- Phase 19.4.5: AIDB import of CLAUDE.md + MEMORY.md for local LLM RAG
- Phase 19.4.6: local LLM system prompt with top-3 CLAUDE.md rules (AI_LOCAL_SYSTEM_PROMPT=true)
- **Phase 20 (NEW)**: Full QA plan tracked in `AI-STACK-QA-PLAN.md` — 10 phases, ~65 discrete tests covering smoke, features, reasoning, context engineering, security, monitoring, self-improvement, E2E workflows
