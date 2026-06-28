# Plan - Capability Intake

**PRD:** `.agent/PROJECT-CAPABILITY-INTAKE-PRD.md`
**Status:** Implemented, active
**Last updated:** 2026-06-28

## Scope

Enable a deny-by-default admission workflow for external plugins, skills, MCP servers, and agent tools.

## Implementation Slices

1. Candidate registry
   - Implemented: `config/agent-capability-intake-candidates.json`
   - Captures state, pinned versions, mitigations, permissions, tool allowlists, and blocked/pending conditions.

2. Audit CLI
   - Implemented: `scripts/ai/aq-capability-intake`
   - Supports `list`, `audit <candidate-id>`, and `audit --all --json`.

3. Skill and routing docs
   - Implemented: `.agent/skills/capability-intake/SKILL.md`
   - Agents must use this before enabling external capabilities.

4. Review delegation briefs
   - Implemented: `tasks_inbox/capability-intake-*.md`
   - Provides async review slices for high-value candidates.

## Validation

- `python3 scripts/testing/test-capability-intake.py`
- `scripts/testing/test-enabled-external-mcp-candidates.py`
- `scripts/ai/aq-capability-intake audit --all --json`
- `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit`

## Remaining Work

- Promote `pending-rebuild` scanners only after NixOS rebuild and live PATH verification.
- Keep GitHub MCP blocked until scoped auth and pinned runtime are available.
