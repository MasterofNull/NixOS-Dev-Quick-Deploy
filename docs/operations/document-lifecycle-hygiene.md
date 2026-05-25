# Document Lifecycle Hygiene

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-25

## Purpose

The harness is moving quickly enough that stale PRDs, phase plans, handoffs, and scratchpad files can become operational hazards. This policy defines how documents stay readable, findable, and historically useful without letting old work masquerade as current instructions.

The goal is not to delete history. The goal is to keep active work small and indexed while preserving historical context in cold storage.

## Lifecycle States

Every active PRD, plan, runbook, or architecture document should declare one state near the top.

| State | Meaning | Agent behavior |
|---|---|---|
| `Active` | Current operating authority or current implementation plan | Use first, keep updated |
| `Draft` | Proposed but not accepted | Use as input only; validate before implementation |
| `Reference` | Historical rationale or strategic context | Read on demand; do not implement directly |
| `Superseded` | Replaced by a newer document | Follow `Superseded-By`; do not use as authority |
| `Archived` | Cold historical record | Searchable history only |
| `Quarantined` | Known incorrect, unsafe, or misleading | Do not use except for incident/root-cause analysis |

Recommended header:

```text
# Title

Status: Active
Owner: AI Stack Maintainers
Last Updated: YYYY-MM-DD
Supersedes: path/or/none
Superseded-By: path/or/none
```

## Active Work Locations

| Kind | Active location | Cold location |
|---|---|---|
| Architecture authority | `docs/architecture/` | `docs/archive/` |
| Operations/runbooks | `docs/operations/` | `docs/archive/` |
| Implementation plans | `.agents/plans/` | `.agents/plans/archive/` or `docs/archive/` for durable summaries |
| Project PRDs | `.agent/PROJECT-*.md` | `.agent/archive/` or `docs/archive/` after summarization |
| Scratch context | `.agents/scratchpad/` | `.agents/scratchpad/archive/` |
| Collaboration state | `.agent/collaboration/` | current only; summarize to plans/handoff before truncating |

## Readability Standards

1. Start with the decision state: what is active, what is blocked, and what is superseded.
2. Keep the first screen useful: status, owner, last updated, canonical links, and next action.
3. Prefer indexes over long preambles.
4. Link to source docs instead of copying long sections.
5. Use concrete file paths for authority and evidence.
6. Mark conflicts explicitly; do not hide contradictions by rewriting history.
7. Keep implementation slices small enough that an agent can validate and retire them.

## Retirement Rules

Use these rules at the end of a slice or when a plan has not been touched for two sessions.

1. If the work shipped, mark the plan `Reference` and add the commit or validation evidence.
2. If a newer doc replaces it, mark it `Superseded` and set `Superseded-By`.
3. If it is no longer useful for active work, move it to an archive path and leave a pointer from the nearest index.
4. If it is wrong or dangerous, mark it `Quarantined` before moving or editing it.
5. Do not delete historical plans unless they contain secrets, generated garbage, or duplicated build artifacts.

## Agent Workflow

Before opening broad docs:

1. Check an index first:
   - `docs/architecture/agent-behavior-parity-index.md`
   - `.agents/plans/README.md`
   - relevant domain or phase index if present
2. Load only the active authority for the current slice.
3. Load reference docs only when they answer a specific question.
4. At slice close, update the plan status and either keep it active or retire it.

## Validation

The lightweight validation hook is `scripts/governance/check-doc-lifecycle-hygiene.py`.

It verifies:

- canonical behavior/parity index exists;
- lifecycle policy exists;
- key active authority docs exist;
- plan README points agents toward the lifecycle policy and behavior index;
- new lifecycle docs carry required metadata.

This check is intentionally narrow. It prevents the index from disappearing, but it does not replace judgment or periodic human cleanup.

