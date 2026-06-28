# Plan - OSINT Systems

**PRD:** `.agent/PROJECT-OSINT-SYSTEMS-PRD.md`
**Status:** Implemented foundation, active recon gated
**Last updated:** 2026-06-28

## Scope

Provide safe passive OSINT research, source-bounded evidence ingestion, and shared retrieval for agent workflows.

## Implementation Slices

1. Passive ingest tool
   - Implemented: `osint_research_ingest` in `ai-stack/mcp-servers/hybrid-coordinator/extensions/mcp_handlers.py`
   - Implemented: local-agent handler in `ai-stack/local-agents/builtin_tools/ai_coordination.py`
   - Produces bounded `osint-intelligence` STIX-like ledger records.

2. Evidence query tool
   - Implemented: `osint_research_query` in coordinator and local-agent tool surfaces.
   - Retrieves persisted `osint-intelligence` records by query and optional workflow.

3. Curated research workflows
   - Implemented: `config/curated-web-research-sources.json`
   - Added `website-design-research` for web.dev, W3C WCAG, and NN/g UX sources.

4. Skill and catalog routing
   - Implemented: `.agent/skills/osint-systems/SKILL.md`
   - Implemented: `ai-stack/mcp-servers/hybrid-coordinator/knowledge/tooling_manifest.py`

## Validation

- `scripts/testing/test-osint-research-ingest.py`
- `python3 scripts/testing/test-osint-tools-mcp-contract.py`
- `python3 scripts/testing/test-web-research-lane.py`
- `python3 scripts/testing/test-curated-web-research.py`
- `scripts/ai/aq-skill-auto 'website design research public sources OSINT database query' --agent codex --json --test`
- `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit`

## Remaining Work

- Active recon remains gated until BBOT/Maigret/MOSAIC or approved replacements are safely packaged and bounded.
- Keep active scans, credentialed collection, sock-puppet actions, and invasive target interaction out of the default path.
