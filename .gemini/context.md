# Project Context — NixOS-Dev-Quick-Deploy

<!-- Phase 19.4.3 — <!-- sync-agent-instructions: auto-generated section --> -->
<!-- Last synced: 2026-05-18 21:36 UTC from CLAUDE.md -->
<!-- Auto-loaded by Gemini CLI from .gemini/context.md -->

## What This Project Is

A NixOS-first, fully declarative AI development stack on an AMD ThinkPad P14s Gen 2a.
Provides: local LLM inference (llama.cpp/ROCm + Ollama), hybrid query routing,
vector database (AIDB + Qdrant), MCP servers, workflow hints (aq-hints), and
Continue.dev integration.

## Port Policy (NON-NEGOTIABLE)

**NEVER hardcode ports or URLs in Python or shell.** Single source of truth: `nix/modules/core/options.nix`.
- Python reads from env vars; shell scripts use `${PORT:-default}`.
- Current defaults: llama.cpp=8080, llama-embed=8081, AIDB=8002, hybrid-coordinator=8003,
  switchboard=8085, cli-bridge=8089, dashboard=8889, ralph=8004.

## Key Service URLs (from config/service-endpoints.sh)

Source this file before any script that needs URLs:
```bash
source config/service-endpoints.sh
curl "$HINTS_URL?q=nixos+conflict"
```

## Hardware

AMD ThinkPad P14s Gen 2a — Renoir APU (Radeon RX Vega 7 iGPU, 4 GB shared VRAM).
- GPU layers ceiling: **`--n-gpu-layers 12` maximum** — never suggest higher.
- `--flash-attn [on|off|auto]` — bare `--flash-attn` flag eats the next arg as value.
- Total usable RAM: 27 GB. Model VRAM budget: 22.5 GB model / 1.0 GB KV / 3.0 GB OS reserve.
- `enable_thinking: false` in EVERY llama.cpp request — thinking tokens cause empty responses.

## Recurring Errors

- **logger NameError in switchboard**: switchboard.py uses `print(..., file=sys.stderr)`, NOT a logger object.
- **Async blocking**: NEVER synchronous file I/O inside `async def` aiohttp/FastAPI handlers.
- **JS fetch timeout**: Every fetch in Promise.allSettled needs AbortController.
- **Duplicate inline auth**: `http_server.py` has `_is_loopback_agent_request()` at ~line 1412 with its own
  `agent_prefixes` tuple — patch BOTH sites when adding loopback endpoints.
- **Coverage gap**: if a service has 0 aq-qa checks AND 0 dashboard panels it breaks silently.
  Governance: aq-qa + dashboard panel required before any feature/service is "done".



## Using Gemini CLI Here

Gemini may code, but only on **bounded, reviewable slices** with explicit integration proof.
For large or ambiguous work, prefer research/review first and require Claude/Codex review before acceptance.
Do NOT send full files unless the analysis task is >100KB.

### Search Before Read

- Never guess repo paths and then call `read_file`.
- Before opening any unconfirmed file, verify the exact path with `agrep`, `als`, or a targeted shell existence check.
- If a read fails with `File not found`, do not try nearby guesses. Search for the filename or concept, choose the confirmed path, then read once.
- Follow `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`: `agrep → rg`, `als → fd`, `acat → native read/sed -n`.
- If a preferred tool is unavailable, use one documented fallback and move on; do not spend multiple turns rediscovering the same missing tool.
- For harness architecture work, start from these confirmed entrypoints:
  - `docs/agent-guides/00-SYSTEM-OVERVIEW.md`
  - `docs/architecture/front-door-routing.md`
  - `.agent/MASTER-DEVELOPMENT-PROMPT.md`
  - `.agent/PROJECT-AGENTIC-FIRST-ELEVATION-PRD.md`
  - `.agents/plans/PROJECT-AI-HARNESS-EVOLUTION-PRD.md`
  - `nix/modules/roles/ai-stack.nix`
  - `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`

```bash
# Good: doc lookup
gemini -p "NixOS 25.11 xdg-desktop-portal-gnome missing gnome-shell workaround"

# Good: large codebase analysis
gemini -p "@ai-stack/mcp-servers/ Summarize the MCP server architecture"

# Bad: small targeted task (use direct file read instead)
# gemini -p "@scripts/ai/aq-hints show me the first 20 lines"
```

Before declaring implementation complete:
- verify every new import/file is tracked by git
- compare producer/consumer schemas for cross-boundary changes
- avoid placeholder or future telemetry in production endpoints
- confirm intended tests are collected by pytest
- validate deployment-sensitive paths under runtime conditions
