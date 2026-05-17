# Phase — System Stability Recovery Slice 1

## Objective
Restore safe AMD auto-acceleration behavior and add regression coverage preventing future policy drift between declarative hardware profiles and the live AI stack module.

## Scope Lock
### In
- `nix/modules/roles/ai-stack.nix`
- focused regression validation for AMD auto-selection policy
- supporting documentation only if required by validation

### Out
- rollback automation
- kernel-track redesign
- unrelated service failures

## Workstreams
1. Align runtime acceleration resolution with canonical hardware policy.
2. Add a focused guard/test for AMD auto-selection consistency.
3. Run syntax/evaluation and focused regression checks.

## Step Plan
1. Read the current AI stack module and existing test patterns.
2. Patch the AMD auto path back to Vulkan and ensure comments match behavior.
3. Add a focused repo-local validation script/test that compares the live module policy against the canonical profile expectations.
4. Run focused validation plus Tier 0.

## Validation
- Focused policy check for AMD auto-selection.
- `nix flake check --no-build` if evaluation cost is acceptable.
- `scripts/governance/tier0-validation-gate.sh --pre-commit`.

## Rollback
Revert the slice commit; no persistent state changes.
