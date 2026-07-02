# Codebase Wiki — Navigation Index

Auto-generated from `knowledge-graph.json` (2026-07-01T16:10:40Z).  
**Do not edit manually.** Refresh: `aq-wiki --update`

## Quick Reference

```bash
aq-wiki --section <name>    # print a section
aq-wiki --status            # freshness check
aq-wiki --update            # differential refresh after code changes
aq-wiki --seed-aidb         # push to AIDB for semantic search
```

## Subsystem Sections

| Section | Nodes | Description |
|---------|-------|-------------|
| [`hybrid-coordinator`](hybrid-coordinator.md) | 685 | AI request routing, tool execution, intent classification, progressive disclosure |
| [`switchboard`](switchboard.md) | 1 | Profile-based model routing, circuit breakers, remote/local delegation |
| [`local-agent`](local-agent.md) | 71 | Local Qwen3-35B agent runtime, outer loop, grounding, task state management |
| [`agent-runtimes`](agent-runtimes.md) | 2 | Agent runtime implementations: slot scheduling, local_agent_runtime |
| [`aidb`](aidb.md) | 95 | AIDB RAG server, Qdrant collections, knowledge ingestion, semantic retrieval |
| [`nix-modules`](nix-modules.md) | 70 | NixOS module declarations for all AI stack services and options SSOT |
| [`nix-hosts`](nix-hosts.md) | 16 | Per-host NixOS configuration, deploy options, secrets wiring (gitignored) |
| [`ai-scripts`](ai-scripts.md) | 225 | Agent CLI scripts: aq-loop, aq-wiki, delegate-to-*, aq-qa, aq-hints, aq-agent-loop |
| [`governance`](governance.md) | 79 | Pre-commit gates, tier0 validation, repo structure linting |
| [`configuration`](configuration.md) | 111 | System config: progressive disclosure domains, doc schema, switchboard profiles |
| [`testing`](testing.md) | 689 | Test harness scripts, inference budget tests, slot scheduling tests |

## Agent Usage Pattern (OpenWiki-style)

Agents load wiki sections **on demand by path** — not embedded in context:

```bash
# Before architecture work on the coordinator:
cat .understand-anything/wiki/hybrid-coordinator.md

# Before switchboard profile changes:
aq-wiki --section switchboard

# Before NixOS module work:
aq-wiki --section nix-modules

# Before delegation script changes:
aq-wiki --section ai-scripts
```

## Progressive Disclosure Integration

Wiki sections are wired into `config/progressive-disclosure-domains.json`.
At `standard` and `full` disclosure levels, the relevant wiki section is
automatically referenced in domain context. Agents can also query AIDB:

```bash
# Semantic search across wiki sections (after --seed-aidb):
aq-hints 'how does switchboard route requests' --source wiki-sections
```
