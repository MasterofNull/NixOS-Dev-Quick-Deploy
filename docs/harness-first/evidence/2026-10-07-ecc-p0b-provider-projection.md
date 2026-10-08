# Harness-First Task Evidence

Date: 2026-10-07
Task ID: HF-20261007-ecc-p0b

## Objective
- ECC parity P0-B MVP: preview-only canonical provider projection compiler. One typed contract (canon regions, roles from role-matrix, tools/capabilities from agent-capability-contract, claude hooks) projected per provider (codex, claude, gemini, local; WORKFLOW-CANON as "shared"). `preview` prints deterministic projection JSON; `check` reports drift vs current provider files. No apply/write mode. Output sha256 over RFC 8785 canonical JSON is printed so a future apply can hash-bind confirmation.

## Workflow/Session IDs
- Workflow ID: wf-ecc-p0b-provider-projection-20261007
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f (orchestrator); implementer is a worktree-isolated headless delegate

## Delegation Decision
- Implementer: Claude Sonnet 5.5 (step-up from cheap tier recorded by orchestrator: multi-file contract work). Not self-accepted; needs independent non-author review. Activation authority: none.

## Commands Executed
```bash
python3 scripts/testing/test-provider-projection.py
scripts/ai/aq-provider-projection preview
scripts/ai/aq-provider-projection check
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Fixture test PASS: byte-identical preview across two runs; drift detected (exit 1) on tampered region; missing marker and missing file reported; brownfield extra content reported as preserved, not drift; unknown manifest field, unknown target, colliding target refused; secret-shaped value (built at runtime) refused and not echoed; CLI has no `apply`.
- Reuses canon/canon.yaml and aqos_install_resolver jcs/sha helpers; does not run canon-compile --write or scripts/data/sync-agent-instructions; no file writes.
- Secret check is an explicit vendor-pattern list (no generic facility is source-verified); applied to canon block bodies and contract metadata.
- QA 0.10.55 registered in scripts/ai/_aq-qa-bash and scripts/testing/harness_qa/phases/phase0.py; runs the fixture test and appends live projection state (clean/drift) to its description.
- Live `aq-provider-projection check` on the repo: status clean, 0 drift findings.

## Rollback Plan
- Revert the single commit; no provider file, service, or runtime state is touched.

## Residual Risk
- Scope: only canon-owned regions are compared; hand-written content outside regions is reported as preserved bytes but not validated. Roles/tools/hooks/capabilities are projected from their sources but not yet written into provider files (needs the apply slice with owner confirmation and file-transaction design; aqos_rollback.py is not a file-transaction authority).
- WORKFLOW-CANON.md is grouped as "shared", and AGENTS.md as codex-owned; revisit when apply is designed.
- Dashboard card not added; visibility is via QA 0.10.55 only.

## Hint Feedback
- No aq-hints consulted.
