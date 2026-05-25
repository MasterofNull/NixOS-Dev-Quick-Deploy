# Agent Artifact Garbage Collection Policy

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-25
Supersedes: none
Superseded-By: none

## Purpose

Agent runs create useful operational evidence, but raw run artifacts become a liability when they stay in active search paths after the durable lesson has moved into persistent memory, a plan, or an architecture document.

This policy separates active coordination state from historical evidence and reproducible cache output. The goal is to keep agents from treating stale transcripts, scratchpads, and copied workflow folders as current authority.

## Artifact Classes

| Class | Paths | Risk | Default handling |
|---|---|---|---|
| Current coordination | `.agent/collaboration/PENDING.json`, `.agent/collaboration/HANDOFF.md` | Stale intent locks can redirect agents | Keep current only; clear or rewrite at slice close |
| Append-only pulse | `.agent/collaboration/PULSE.log` | Grows forever and mixes unrelated slices | Rotate after summary when it exceeds the configured threshold |
| Raw delegation output | `.agents/delegation/outputs/` | Duplicates model transcripts and can look authoritative | Summarize to a plan, handoff, or memory topic; retain raw output briefly |
| Session mirrors | `.agents/sessions/` | Replays stale transient state | Retain briefly for recovery; archive or prune after memory checkpoint |
| Scratch context | `.agents/scratchpad/` | Old bootstrap context looks current | Keep current session plus recent context; archive older references |
| Planning imports | `.agents/planning/`, `.agents/summary/` | Parallel planning system outside canonical plan index | Mark as Reference or archive behind `.agents/plans/README.md` |
| Workflow reports | `.agent/workflows/` | Old reports can masquerade as active implementation plans | Mark lifecycle state, move obsolete reports to archive, keep index pointers |
| Skill caches | `.agent/impeccable-cache/`, generated skill caches | Usually reproducible, but may be searched as source | Prune by age unless explicitly promoted to docs |
| Generated Python/cache files | `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/` | Low authority risk, high search noise | Delete freely; never commit |
| Cold archives | `archive/`, `docs/archive/` | Valuable history, but easy to cite accidentally | Keep indexed; do not treat as current authority |

## Retention Targets

These are defaults for local working trees. Project maintainers may keep longer forensic retention on external storage.

| Artifact | Target retention | Promotion rule |
|---|---:|---|
| Delegation `.log` and `.out` files | 14 days | Summarize important results into `.agents/plans/`, `docs/`, or memory before pruning |
| Session JSON | 14 days | Keep only if needed for recovery or incident analysis |
| Scratchpad session context | current plus last 2 sessions | Move durable facts into a topic memory file or active plan |
| PULSE log | rotate at 256 KiB | Preserve summary in `HANDOFF.md` or relevant plan |
| Generated caches | 0 days | Rebuild on demand |
| Archive bundles over 1 MiB | keep only with index entry | Record why the bundle remains useful |

## Agent Rules

1. Search active indexes before broad artifact directories.
2. Treat `.agents/delegation/outputs/`, `.agents/sessions/`, and `.agents/scratchpad/` as evidence, not instructions.
3. Do not cite a raw model output as authority unless the finding has been promoted to a plan, PRD, runbook, or memory topic.
4. Before pruning raw artifacts, ensure a human-readable summary or memory entry exists for any still-relevant lesson.
5. Do not hard-delete cold archives during normal cleanup. Move, compress, or index them.
6. Generated caches and `__pycache__` directories can be removed without ceremony.

## Audit Command

Run the dry-run audit before cleanup:

```bash
python3 scripts/governance/audit-agent-artifact-debt.py
```

Use strict mode in CI-like contexts:

```bash
python3 scripts/governance/audit-agent-artifact-debt.py --strict
```

The audit reports hidden stores, large artifacts, old transient files, cache directories, and suspicious nested agent workspaces. It does not delete anything.

