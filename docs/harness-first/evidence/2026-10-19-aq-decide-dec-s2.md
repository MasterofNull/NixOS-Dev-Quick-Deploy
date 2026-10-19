# Harness-First Task Evidence

Date: 2026-10-19
Task ID: HF-20261019-AQ-DECIDE-DEC-S2

## Objective
- Implement DEC-S2 of `.agents/plans/aq-decide/DESIGN.md`:
  - Declare Nix options `mySystem.aiStack.aqDecide` with options for `enable`, `mode`, `embedder` (port, repo, file, sha256, gpuLayers), `integrations` (taskProfile, retryEscalate, rag, approvals, egress), and `train.timer.enable`.
  - Add `bge-small-aqdecide` to `defaultModelCatalog` in `nix/modules/roles/ai-stack.nix`.
  - Add port SSOT `ports.aqDecideEmbedder = 8082;` in `nix/modules/core/options.nix`.
  - Add dedicated model allowlist assertion for `mySystem.aiStack.aqDecide.embedder.huggingFaceRepo`.
  - Declare systemd user/system service `llama-cpp-aqdecide` (CPU-only by default with `-c 512 -ub 512 --threads 2 -ngl 0`) and tmpfiles rules for `/var/lib/aq-decide/state` (Rule 13).

## Workflow/Session IDs
- Session ID: 73f977e7-94b7-44b8-918e-821afb98ba44
- Plan: `.agents/plans/aq-decide/DESIGN.md` (DEC-S2)
- Branch: `feat/aq-decide-dec-s2`

## Delegation Decision
- Implemented in worktree `.agents/delegation/worktrees/dec-s2` by Antigravity (Gemini lane) with cross-lane independent review.

## Commands Executed
```bash
nix flake check --no-build
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- `nix flake check --no-build`: all NixOS configurations, homeConfigurations, checks, and devShells passed evaluation without errors.
- Declarative allowlist assertion verified for `CompendiumLabs/bge-small-en-v1.5-gguf`.

## Rollback Plan
- Set `mySystem.aiStack.aqDecide.enable = false;` and `mySystem.aiStack.aqDecide.embedder.enable = false;` or revert commit.

## Residual Risk
- The dedicated embedder instance defaults to disabled (`enable = false;`) and CPU-only (`gpuLayers = 0`) to guarantee zero VRAM/page-cache impact on the main 35B model until DEC-S5 promotion criteria are met.

## Hint Feedback
- None.
