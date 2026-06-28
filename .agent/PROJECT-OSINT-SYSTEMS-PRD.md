# PRD - OSINT Systems Domain Activation

**Domain tag:** `osint-systems`
**Status:** Active foundation, passive research enabled, active recon gated
**Last updated:** 2026-06-28

## Objective

Provide all agents with a safe OSINT research path that can collect public-source evidence, normalize it into bounded ledger records, and make it available through the `osint-intelligence` namespace for later retrieval and synthesis.

## Current Scope

- Passive public web research through curated source manifests.
- Robots-aware and SSRF-protected HTTP extraction.
- Browser-assisted fallback only for explicit URLs and approved workflows.
- STIX-like `observed-data` ledger records for `osint-intelligence`.
- Agent access through the hybrid coordinator MCP surface and local-agent tool registry.
- Website creation research pack covering responsive design, WCAG reference material, and UX usability sources.

## Out of Scope Until Explicit Review

- Active scanning.
- Authentication-gated data collection.
- Sock-puppet automation.
- PII enrichment beyond explicit authorized investigation scope.
- Enabling insecure Maigret or MOSAIC Nix derivations.
- GitHub MCP token-backed use until scoped auth and runtime are approved.

## Architecture

| Layer | Implementation |
|---|---|
| Agent tool | `osint_research_ingest`, `osint_research_query` |
| Research engine | `research_workflows.run_curated_research_workflow()` |
| Source policy | `config/curated-web-research-sources.json` |
| Passive fetch | `web_research.fetch_web_research()` |
| Browser fallback | `browser_research.fetch_browser_research()` |
| Ledger namespace | `osint-intelligence` |
| Ledger schema | `stix-2.1-lite` |
| Active recon MCP | `ai-stack/mcp-servers/osint-tools/server.py` |

## Acceptance Criteria

- `osint-systems` exists in `config/capability-lifecycle-registry.json`.
- `.agent/OSINT-SYSTEMS-INSTRUCTIONS.md` is present.
- `osint_research_ingest` and `osint_research_query` are listed in the coordinator MCP tool definitions.
- Local agents can lease/call `osint_research_ingest` and query persisted evidence with `osint_research_query`.
- Passive research output contains bounded ledger records with `namespace=osint-intelligence`.
- `website-design-research` is registered in the curated source manifest for website build workflows.
- Existing `osint-tools` MCP contract remains safe and does not activate insecure Maigret/MOSAIC packages.
- Web research tests prove robots-aware extraction, curated workflow fallback, and no live network dependency in tests.
