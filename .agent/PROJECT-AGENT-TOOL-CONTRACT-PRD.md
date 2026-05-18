# PRD: Agent Tool Contract Hardening

**Date:** 2026-05-18  
**Owner:** Codex  
**Related program:** Phase 58A capability-expansion foundation

## Problem

The harness already teaches agents to use token-efficient Agentic CLI tools such as `agrep`, `als`, `acat`, and `asum`, but the runtime isolation defaults still advertise older low-level tools such as `rg`, `cat`, and `ls`. When an agent lane cannot access the preferred tool it expects, it spends tokens discovering the mismatch, emits fallback chatter, retries failed calls, and may drift into less efficient workflows.

The recent Gemini `Ripgrep is not available. Falling back to GrepTool.` event exposed the wider issue: the system lacks one explicit cross-agent tool contract that says which tools are guaranteed, which are preferred, and what the bounded fallback order is.

## Goal

Create a lean, canonical agent tool contract that:

1. defines the minimum universal tool surface every coding/research lane should expose,
2. states preferred tool order and one-step fallbacks,
3. aligns instruction surfaces with runtime isolation allowlists,
4. reduces token waste from avoidable missing-tool discovery and repeated retries,
5. gives future capability expansion a stable baseline instead of accumulating per-agent exceptions.

## Scope

### In scope
- Canonical tool-contract documentation.
- Preferred discovery/read/structured-data fallback order.
- Alignment of canonical workflow docs and Gemini generated context.
- Alignment of runtime isolation profile allowlists with the preferred Agentic CLI surface.
- Planning linkage back into Phase 58A architecture work.

### Out of scope
- Installing every language-specific compiler, formatter, or linter into every lane.
- Redesigning Gemini CLI internals or proprietary native tools.
- Replacing native MCP/tool APIs when they are the best path for a task.
- Full capability-profile packaging for all future engineering domains; that belongs to the larger Phase 58 program.

## Canonical baseline

### Universal low-friction tools

| Capability | Preferred tools |
|---|---|
| repo search | `agrep`, with `rg` as the first raw fallback |
| repo listing / path discovery | `als`, then `fd` |
| bounded file reads | `acat`, then native read tools or `sed -n` |
| structural overview | `asum` |
| structured text | `jq`, `yq` |
| execution glue | `bash`, `python3`, `git` |

### Validation helpers

`curl` and `shellcheck` should be available in practical coding environments, but they are not part of the minimal readonly contract because network policy and task class can vary by lane.

### Fallback discipline

1. Use the preferred repo-native tool first.
2. If it is unavailable, use exactly one documented fallback.
3. If the fallback is also unavailable, record the missing capability once and continue with the approved equivalent for that lane; do not rediscover the same failure repeatedly.
4. Never retry an unchanged failed tool call without a changed hypothesis.

## Acceptance criteria

1. There is one explicit canonical tool-contract document referenced from the workflow docs.
2. The documented default tool order is consistent across all touched instruction surfaces.
3. Runtime isolation defaults include the preferred Agentic CLI tools they instruct agents to use.
4. Gemini-generated context includes the same bounded fallback logic as the canonical workflow.
5. Phase 58A planning records this as an enabling foundation slice, then returns to the canonical-kernel work.

## Security and operational requirements

- Preserve least privilege: adding non-mutating discovery tools must not broaden filesystem write or network permissions.
- Keep network access controlled by lane policy rather than accidentally implying it through tool presence.
- Avoid hardcoding host-specific binary paths in instructions.
- Treat all agent outputs as untrusted despite improved tool access.

## Success signal

Agents stop wasting turns on predictable tool mismatches and use the same small, reliable discovery/read workflow regardless of model lane.
