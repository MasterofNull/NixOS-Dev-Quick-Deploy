---
title: Context Sandbox Parity Routing
doc_type: prd
id: context-sandbox-parity-routing
status: active
owner: agent-runtime
last_updated: 2026-06-29
---

# Context Sandbox Parity Routing

## Problem

Recent parity research identified context window bloat as a high-value gap. The harness already has local context-management and switchboard output compaction primitives, but agent-facing tool discovery does not consistently surface them when prompts mention large logs, browser snapshots, raw command dumps, or token-heavy outputs.

## Goals

- Teach the tooling manifest to route high-payload context tasks to existing local context compaction/offload tools.
- Keep this slice repo-local; do not install `context-mode` or any external MCP server.
- Make the selected tool contract explicit enough for agents to prefer compact summaries and artifact pointers.
- Add regression coverage so future manifest changes do not hide the context-sandbox path.

## Non-Goals

- Import or run external `context-mode` code.
- Change switchboard compaction implementation.
- Add new runtime services.

## Acceptance

- Context-heavy prompts select a context sandbox/offload tool.
- The generated manifest includes the tool and places it in relevant workflow phases.
- Existing tooling manifest tests pass.
- Tier0 pre-commit gate passes.
