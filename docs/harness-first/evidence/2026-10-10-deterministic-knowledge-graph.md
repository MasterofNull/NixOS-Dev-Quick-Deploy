# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-050

## Objective
- Owner: "I want the whole system", a complete knowledge graph so agents can fully understand and improve it. The LLM-generated understand-anything graph was 100 days stale (6,257 nodes / 1,870 edges); regenerating it took about 300 LLM batches (millions of tokens, or over a week on local inference).
- New `aq-graph-build` builds the same schema DETERMINISTICALLY (stdlib static analysis, no LLM). It covers Python modules/classes/functions with imports/calls/extends; shell scripts and tool invocations; Nix modules, import trees, 151 systemd units with ExecStart→script edges and 388 mySystem options; docs→file documents edges; tests↔files edges; and capability-index tags.
- Result: 24,811 nodes and 62,943 edges in about 19s, byte-identical across runs. 1,188 richer LLM summaries are carried forward (tagged); the old graph is preserved as knowledge-graph.llm-2026-07-01.json (Rule 12).
- Freshness: the .githooks/post-merge hook rebuilds detached when stale (opt-out AQ_GRAPH_BUILD_HOOK=0).
- The graph is now a gitignored generated artifact (22MB; tracking it would dirty the checkout after every merge and block the nrs fast-forward). UA_GRAPH_PATH overrides the path for tests and tooling. The wiki_info() bug (it counted the hash map as a section, so the wiki always read "behind") is fixed.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer (static analyser design). The orchestrator untracked the artifact, made the tests CI-safe (fixture graph via UA_GRAPH_PATH) and fixed the catalog ref.

## Commands Executed
```bash
scripts/ai/aq-graph-build                          # 24811 nodes / 62943 edges, ~19s
aq-graph-query impact nix/modules/services/switchboard.nix   # 49 dependents (old graph: 0)
aq-understand-anything status --check              # FRESH
test-graph-build, test-graph-query, test-system-capability-catalog, test-capability-audit, test-capability-index   # PASS with the real graph ABSENT (CI condition)
```

## Validation Evidence
- All consumers (aq-graph-query, the MCP graph_query, the dashboard summary route, aq-wiki) work on the new graph. Python import resolution covers nearly all non-stdlib imports (the remainder is third-party).

## Rollback Plan
- Revert. The old LLM graph is available as knowledge-graph.llm-2026-07-01.json.

## Residual Risk
- Call edges are best-effort static (name-matched ones get weight 0.5). LLM summaries remain only where carried forward; selective local-model enrichment of changed files is a follow-up. After merge, pulling removes the old tracked graph file from the checkout, and the post-merge hook rebuilds it within about 20s.

## Hint Feedback
- None.
