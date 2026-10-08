# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-ecc-p0e

## Objective
- ECC parity P0-E MVP: portable GitHub CI pack distributed through the existing factory gate bundle (templates/factory-gate-bundle + scripts/ai/lib/factory_gate_install.py). Adds a rendered `.github/workflows/factory-gate.yml` (SHA-pinned actions, workflow-level `contents: read`, no privileged PR trigger, no repository secrets, `persist-credentials: false`) and a stdlib, no-network checker `ci/ci_policy.py` that yields a two-axis verdict: LOCAL_READY / LOCAL_BLOCKED / NOT_INSTALLED plus an always-UNVERIFIED_REMOTE remote axis.

## Workflow/Session IDs
- Workflow ID: wf-ecc-p0e-portable-ci-pack-20261008
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f (orchestrator); implementer is a worktree-isolated headless delegate

## Delegation Decision
- Implementer: Claude Sonnet 5.5 (step-up from cheap tier recorded by orchestrator: CI security-sensitive workflow design). Needs independent non-author review. Activation authority: none (no remote, account, secret or ruleset mutation).

## Commands Executed
```bash
python3 scripts/testing/test-factory-ci-pack.py
python3 scripts/testing/test-factory-gate-install.py
python3 scripts/testing/test-factory-gate-retrofit.py
python3 scripts/testing/test-factory-gate-readiness.py
python3 scripts/testing/test-factory-gate-capability-manifest.py
bash templates/factory-gate-bundle/self-test.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Fixture test PASS (temp dirs only): greenfield install renders the workflow with every `uses:` a 40-hex SHA; permissions least-privilege; greenfield collision refused with existing file untouched; brownfield retrofit preserves existing `ci.yml` byte-for-byte and adds the pack; a project-owned file at the pack path is preserved and reported NOT_INSTALLED; tag-pinned tampering flips verdict to LOCAL_BLOCKED; pull_request_target, write-all, top-level write, missing permissions, unpinned docker refs detected; forged remote-evidence file never promotes the remote axis.
- Existing install/retrofit/readiness/capability-manifest fixtures and bundle self-test still pass (self-test allowed_top gained `.github`).
- QA 0.10.58 registered in scripts/ai/_aq-qa-bash and phase0.py. Dashboard: advanced runtime summary `capability_gap.ci_pack` and a "· CI pack" row in assets/dashboard.js.

## Rollback Plan
- Revert the single commit; the manifest entries, template, checker, QA check and dashboard row are all additive. Installed targets keep a project-owned workflow file that can be deleted by its owner.

## Residual Risk
- Provenance/attestation (id-token/attestations write on default-branch pushes) is not shipped: no verified action SHA is available offline; evidence digest artifact only.
- Remote required checks/rulesets stay UNVERIFIED_REMOTE; the checker is a line-based scanner, not a YAML parser (anchors/flow-style permissions are not interpreted).
- Dashboard row reflects template readiness and the host repo's own workflows (which still contain unpinned legacy actions); it does not scan arbitrary installed targets.
- Stack toolchain setup is project-owned (`.factory/ci-setup.sh` or added pinned setup actions).

## Hint Feedback
- No aq-hints consulted.
