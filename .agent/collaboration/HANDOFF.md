# Handoff Memo - 2026-05-18

**Status:** IN PROGRESS — Agent tool-contract hardening complete; Phase 58A.0 resumed with a draft canonical-kernel declaration.
**Last Action:** Finished the cross-agent tool contract alignment, then created `docs/architecture/canonical-kernel-declaration.md` and `.agents/plans/phase-58a-canonical-kernel-declaration.md` to move the original capability-expansion program forward again.
**Next Step:** Review and refine the canonical-kernel declaration with the team, then proceed to `58A.1 — Canonical role matrix SSOT` using that declaration as the upstream authority.
**Context Bloat:** Medium

## Completed in this session
1. Added a canonical low-friction agent tool contract.
2. Aligned Claude, Gemini, Qwen, AGENTS, workflow canon, generated Gemini context, and runtime isolation defaults.
3. Regenerated instruction projections through `scripts/data/sync-agent-instructions`.
4. Rejoined the original Phase 58A path by drafting the canonical kernel declaration and linking it into the architecture review artifacts.

## Validation evidence
- `python3 -m py_compile scripts/data/sync-agent-instructions` — PASS
- `python3 scripts/data/sync-agent-instructions --dry-run --verbose` — PASS before sync
- `python3 scripts/data/sync-agent-instructions --verbose` — PASS
- `nix-instantiate --parse nix/modules/core/options.nix` — PASS
- `scripts/governance/tier0-validation-gate.sh --pre-commit` — BLOCKED by existing baseline QA failures (`63 passed · 2 failed · 2 skipped`)

## Current architecture artifacts
- `.agent/PROJECT-CAPABILITY-EXPANSION-MASTER-PRD.md`
- `.agent/PROJECT-CAPABILITY-EXPANSION-CODEX-PRD.md`
- `.agents/plans/phase-58a-architecture-review-brief.md`
- `.agents/plans/phase-58a-capability-expansion-team-plan.md`
- `.agents/plans/phase-58a-canonical-kernel-declaration.md`
- `docs/architecture/canonical-kernel-declaration.md`

## Notes
- The new tool contract is an enabling cleanup, not a replacement for the broader architecture effort.
- The main line is now back on the intended sequence: kernel declaration → role matrix → routing/profile SSOT → instruction projections.
