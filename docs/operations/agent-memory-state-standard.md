# Agent Memory And State Standard

Status: Active
Owner: AI Stack Governance
Last Updated: 2026-06-09

This standard separates agentic mind data by authority level. It prevents local
session state, raw telemetry, old planning notes, and curated collective memory
from being mixed together as if they were the same source of truth.

Registry: `config/agent-memory-surface-registry.json`

## Canonical Surfaces

| Surface | Authority | Tracking | Use |
| --- | --- | --- | --- |
| Local live state | Current session only | Ignored | Resume/recovery for this machine |
| Coordination templates | Bootstrap contract | Tracked | Shape for new deployments |
| Durable collective memory | Curated operational memory | Tracked | Stable lessons, issues, and pointers |
| Curated PRDs/plans/prompts | Active planning record | Tracked | Reviewed planning and handoff prompts |
| RAG/database facts | Retrieval memory | Database | Searchable learned facts via coordinator |
| Raw learning feedback | Evidence only | Runtime or ignored | Scorecards, reports, and promotion inputs |
| Reference-only archives | Historical reference | Tracked or archived | Past decisions and deprecated notes |

## Local Live State

These files are local-only and must not be committed:

- `.agent/collaboration/RESUME.json`
- `.agent/collaboration/PENDING.json`
- `.agent/collaboration/HANDOFF.md`
- `.agent/collaboration/PULSE.log`
- `.agent/comms/*`
- `.agents/attention/*`
- `.agents/delegation/registry.jsonl`
- `.agents/telemetry/*.jsonl`
- `nix/hosts/*/facts.nix`

Use them to resume active work, inspect the latest handoff, or recover after
context loss. Promote anything durable into a tracked memory topic, PRD, doc,
test, or RAG fact before it is treated as collective knowledge.

## Durable Collective Memory

`ai-stack/agent-memory/MEMORY.md` is the hot index. Keep it pointer-only and
under the line budget in the registry. Do not paste phase dumps or raw logs into
it.

`.agent/memory/*.md` files are warm memory topics. Use them for issue backlog
entries, stable operational constraints, recurring bug patterns, and durable
lessons. Stale topic files should be archived only after running the archive
reference scan required by project policy.

## RAG And Database Facts

Agents must not write directly to AIDB or Qdrant during normal operations. Use
the hybrid coordinator path:

- `POST /memory/facts` for single promoted facts
- `/query` for retrieval
- `scripts/ai/aq-commit-facts` for recent-work extraction
- `scripts/data/seed-rag-knowledge.py` for reviewed batches

Promote facts into the appropriate collection:

- `error-solutions` for bug patterns and fixes
- `best-practices` for durable architecture and workflow decisions
- `skills-patterns` for reusable agent/tool patterns
- `logic-patterns` and `codebase-context` for indexed code understanding

Raw telemetry is not a fact until it has been reviewed, deduplicated, and given
source metadata.

## Reference-Only Surfaces

The following paths are historical evidence unless a current PRD or task
explicitly promotes them:

- `.agents/archive/**`
- `.agent/archive/**`
- `.agents/planning/**`
- `.agents/summary/**`
- `docs/archive/**`

Agents may inspect them to understand history, but they must not treat them as
active workflow authority. If useful content remains valid, move the distilled
lesson into `.agent/memory`, an active PRD, a governance doc, or a test.

## Promotion Rule

Before persistent data becomes portable collective knowledge, perform all of the
following:

1. Remove host-local paths, secrets, transient timestamps, and raw tool dumps.
2. Identify the target surface: memory topic, PRD/plan, operational doc, test,
   or RAG fact.
3. Add or update validation for any workflow rule that should stay enforced.
4. Keep live state ignored and commit only curated, portable artifacts.

## Dashboard And Feedback Loop Rule

Learning loops are complete only when their outputs are measurable. Raw events
should flow into reports, scorecards, or dashboard surfaces before they influence
automation. If an agent outcome changes a workflow contract, it needs a visible
metric or QA gate in the same slice.
