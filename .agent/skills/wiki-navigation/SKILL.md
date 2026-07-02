---
name: wiki-navigation
description: "Query structured wiki sections in .understand-anything/wiki/ for subsystem overviews, architecture, and function discovery — before reading raw files"
metadata:
  type: skill
  version: 1.0.0
  created: 2026-07-01
  agents: [claude, gemini, codex, local]
---

# Wiki Navigation

## Tags
wiki, knowledge-graph, architecture, subsystem, overview, understand-anything, codebase-map, function-discovery, dependency-tracing, context-efficient

## When to Use

Use this skill **before reading raw files** when you need:
- Subsystem overview ("what files handle X?")
- Function discovery ("where is Y defined?")
- Dependency tracing ("what does Z import? what does it call?")
- Change impact scoping ("what will be affected if I modify W?")
- Architecture orientation at session start

The wiki is an aggregated, pre-computed view of `knowledge-graph.json` (6,257 nodes, 1,870 edges).
Reading one wiki section costs ~200-400 tokens vs scanning 50+ source files.

## Available Sections

| Section | Covers | CLI |
|---------|--------|-----|
| `hybrid-coordinator` | Request routing, intent classification, tool dispatch | `aq-wiki --section hybrid-coordinator` |
| `switchboard` | Profile routing, circuit breakers, remote/local delegation | `aq-wiki --section switchboard` |
| `local-agent` | Qwen3-35B runtime, outer loop, task state | `aq-wiki --section local-agent` |
| `agent-runtimes` | Slot scheduling, local_agent_runtime, SlotWaitTimeout | `aq-wiki --section agent-runtimes` |
| `aidb` | AIDB RAG server, Qdrant collections, knowledge ingestion | `aq-wiki --section aidb` |
| `nix-modules` | NixOS module declarations, options SSOT | `aq-wiki --section nix-modules` |
| `nix-hosts` | Per-host config, deploy options, secrets wiring | `aq-wiki --section nix-hosts` |
| `ai-scripts` | aq-loop, aq-wiki, delegate-to-*, aq-qa, aq-hints | `aq-wiki --section ai-scripts` |
| `governance` | Pre-commit gates, tier0 validation, repo linting | `aq-wiki --section governance` |
| `configuration` | Progressive disclosure, doc schema, switchboard profiles | `aq-wiki --section configuration` |
| `testing` | Test harness, inference budget, slot tests | `aq-wiki --section testing` |

## Usage Pattern (OpenWiki-style)

Load sections **on demand by path** — never embed full sections in delegation prompts.

```bash
# Quick orientation before architecture work:
aq-wiki --section hybrid-coordinator

# Or read directly (same content):
cat .understand-anything/wiki/hybrid-coordinator.md

# Check freshness before relying on wiki:
aq-wiki --status

# List all available sections with descriptions:
aq-wiki --list

# Semantic search across wiki (after --seed-aidb):
aq-hints 'how does switchboard route requests' --source wiki-sections
```

## Differential Refresh

After code changes, run differential update so wiki stays current:

```bash
aq-wiki --update       # only regenerates sections touched by recent commits
aq-wiki --init --force # full regeneration from knowledge-graph.json
```

This is part of Step 7 (DOC-UPDATE) in the canonical workflow.

## Graph Freshness

The wiki derives from `.understand-anything/knowledge-graph.json`.
If you've made significant code changes and the graph is stale:

```bash
# Refresh knowledge graph first, then wiki:
/understand    # (Claude Code — regenerates knowledge-graph.json)
aq-wiki --init --force
```

Wiki staleness check: `aq-wiki --status` shows `STALE` when graph generation timestamp
doesn't match the section's recorded `graph_generated` timestamp.

## Integration with Progressive Disclosure

At `standard` and `full` disclosure levels, the `ai-harness` and `documentation` domain
contexts automatically surface the relevant wiki section path. Agents can then decide
to read it on demand rather than it being pre-loaded.

At `full` level, AIDB semantic search on `wiki-sections` collection is also available:

```bash
aq-hints "<architectural question>" --source wiki-sections
```

## AIDB Seeding

After wiki generation, push sections to AIDB for semantic search:

```bash
aq-wiki --seed-aidb
```

Note: Requires `wiki-sections` to be in `ALLOWED_COLLECTIONS` in AIDB config
(`nix/modules/core/options.nix` → `services.aidb.allowedCollections`).

## Agent-Specific Notes

**Claude Code**: Wiki sections are in `.understand-anything/wiki/`. Use `Read` or `cat` directly.  
**Gemini/Codex/Local**: Use `aq-wiki --section <name>` via `run_shell_command` / `run_command`.  
**All agents**: Reference by path in delegation prompts — never inline full section content.
