# Capability Integration — no derelict capabilities (MVP)

Owner directive 2026-10-08: every implementation, tool and feature is integrated into the agents' working memory, workflows and repertoire. None may be derelict, unused, stale, dead, or unavailable. Enabled is not done: activation is MVP testing, and development continues.

## Measure (deterministic, repeatable)
`scripts/ai/aq-capability-audit` (read-only, no LLM). It classifies every catalog entry, aq-* script, skill, MCP tool, nix unit/timer and artifact from evidence: telemetry, delegation, wiring, discovery sources and tests.

Baseline 2026-10-08 (30d, 461 caps): ACTIVE 172 · UNUSED-AVAILABLE 96 · UNDISCOVERABLE 112 · STALE-CLAIM 12 · DEAD-CANDIDATE 69 · BROKEN 0.

Success = UNDISCOVERABLE, STALE-CLAIM and DEAD-CANDIDATE each trend to 0, and UNUSED-AVAILABLE shrinks each pass. Each remaining item is either wired into a workflow or archived (Rule 12, never deleted).

## Workstreams
1. **Measure.**
   - Restore aq-* usage logging (aq-usage.jsonl has been dead since July), so use is logged rather than inferred.
   - Run the audit on a timer.
   - RSI records regressions (class transitions to worse).
2. **Discover.** Generate an agent-loaded capability index from the audit plus each tool's `--help` first line, so agents can find all 112 UNDISCOVERABLE items. Wire it into the tooling manifest, aq-hints and progressive disclosure.
3. **Honest claims.** Correct the 12 STALE-CLAIM catalog entries to their true state, or wire them. Catalog/tracker claims must match evidence. Re-review agent-recorded "acceptances" (proposed to the owner; never revoked unilaterally).
4. **Triage dead.** For each of the 69 DEAD-CANDIDATE items: revive and wire, or archive. Every decision is recorded with evidence.
5. **Wire unused.** Attach the 96 UNUSED-AVAILABLE items to workflows: hints rules, blueprints, dispatch context, skills routing.
6. **Flagship gaps.**
   - Vector DB integrity and routing (#437, #V2).
   - understand-anything full integration: graph refresh (local Q4 overnight), staleness check plus timer, graph query endpoint and agent tool, live dashboard card, Nix pin.
   - meta-optimization migrations.
   - query-expansion consumer.

## Rules
- Deterministic tools for bulk measurement; cheapest-eligible implementers for slices.
- Security/isolation activation stays deferred.
- Status is PROJECTED (Rule 20); acceptance is the owner's.
