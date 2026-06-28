# Plan - Mobile Web

**PRD:** `.agent/PROJECT-MOBILE-WEB-PRD.md`
**Status:** Baseline implemented
**Last updated:** 2026-06-28

## Scope

Activate mobile/web guidance for frontend, accessibility, Playwright verification, and MASVS-style review while keeping invasive testing gated.

## Implementation Slices

1. Domain instruction anchor
   - Implemented: `.agent/MOBILE-WEB-INSTRUCTIONS.md`

2. Lifecycle registry entry
   - Implemented: `mobile-web` in `config/capability-lifecycle-registry.json`

3. Browser automation capability
   - Implemented: bounded Playwright MCP candidate in `config/agent-capability-intake-candidates.json`
   - Implemented: agent config surfaces in `.gemini/settings.json` and `ai-stack/continue/config.json`

4. Website research support
   - Implemented: `website-design-research` in `config/curated-web-research-sources.json`
   - Implemented: `frontend-design` skill metadata validation fix.

## Validation

- Focused CI: `mobile-web domain baseline artifact presence check`
- `scripts/testing/test-enabled-external-mcp-candidates.py`
- `scripts/ai/aq-skill-auto 'website design research public sources OSINT database query' --agent codex --json --test`
- `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit`

## Remaining Work

- Add real Lighthouse or equivalent local audit integration only after pinning and sandbox review.
- Keep reverse engineering, credentialed testing, and account/device actions approval-gated.
