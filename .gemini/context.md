# Project Context — NixOS-Dev-Quick-Deploy

<!-- Phase 19.4.3 — <!-- sync-agent-instructions: auto-generated section --> -->
<!-- Last synced: 2026-05-18 02:29 UTC from CLAUDE.md -->
<!-- Auto-loaded by Gemini CLI from .gemini/context.md -->

## What This Project Is

A NixOS-first, fully declarative AI development stack on an AMD ThinkPad P14s Gen 2a.
Provides: local LLM inference (llama.cpp/ROCm + Ollama), hybrid query routing,
vector database (AIDB + Qdrant), MCP servers, workflow hints (aq-hints), and
Continue.dev integration.

## Port Policy (NON-NEGOTIABLE)



## Key Service URLs (from config/service-endpoints.sh)

Source this file before any script that needs URLs:
```bash
source config/service-endpoints.sh
curl "$HINTS_URL?q=nixos+conflict"
```

## Hardware



## Recurring Errors



## Using Gemini CLI Here

Gemini may code, but only on **bounded, reviewable slices** with explicit integration proof.
For large or ambiguous work, prefer research/review first and require Claude/Codex review before acceptance.
Do NOT send full files unless the analysis task is >100KB.

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
