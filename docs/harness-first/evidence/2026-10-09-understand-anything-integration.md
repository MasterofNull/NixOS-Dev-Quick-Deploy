# Harness-First Task Evidence

Date: 2026-10-09
Task ID: HF-20261009-040

## Objective
- Plan item ci-9, excluding graph regeneration, which needs an LLM run and waits for local inference to be free. Understand-anything was catalogued as "integrated" but its graph was 100 days and 1271 commits stale and nothing queried it.
- Added:
  - a declared refresh limit (config/understand-anything.json);
  - `--check` staleness in aq-understand-anything / aq-wiki;
  - a WARN-class phase-0 check (0.10.59, registered in both harnesses);
  - read-only `aq-graph-query` (search/symbol/neighbors/impact/types/staleness) with type normalisation (30 raw spellings → 16 types);
  - an MCP `graph_query` tool, plus local-agent allowlist entries;
  - a dashboard `GET /api/understand/summary` route, with a live module card and tile dot (yellow when stale);
  - an upstream pin (rev 54754a6, verified match).
- The catalog and intake entries are set to "partial".

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer; the orchestrator reviewed.

## Commands Executed
```bash
python3 scripts/testing/test-graph-query.py; test-system-capability-catalog; test-capability-intake; test-enabled-external-mcp-candidates; aq-capability-catalog check-doc   # all PASS
aq-graph-query search switchboard   # ranked hits; impact on a nix file returns 0 dependents (the stale graph is sparse)
aq-understand-anything status --check   # exit 1: STALE 100d / 1271 commits
```

## Validation Evidence
- Live read-only queries work against the existing graph. Staleness is now visible on the dashboard and in QA, instead of a hard-coded green dot.

## Rollback Plan
- Revert. Restarting the dashboard backend picks up the route (no rebuild).

## Residual Risk
- Graph regeneration is still pending; impact analysis stays shallow until then (1870 edges for 6257 nodes). capability_audit.py keeps its own 14-day constant (follow-up). The local_agent_runtime allowlist is not updated.

## Hint Feedback
- None.
