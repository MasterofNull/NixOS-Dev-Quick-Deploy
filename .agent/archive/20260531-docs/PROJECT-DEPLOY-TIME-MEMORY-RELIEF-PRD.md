# Project PRD — Deploy-Time Memory Relief

## Objective
Reduce live-activation memory pressure by temporarily pausing selected high-memory AI services around `nixos-rebuild switch`, then restoring them deterministically after activation.

## Current evidence
- AppArmor reload failures during activation are intermittent and correlate with severe memory pressure.
- The deploy path already validates and restarts repo-backed AI services after switch.
- `llama-cpp` is the dominant memory consumer and can be restarted declaratively after activation.

## In scope
1. Identify the smallest safe pause set for live switch mode.
2. Pause only when live activation is actually happening.
3. Resume services reliably even if activation fails.
4. Keep behavior configurable and visible in logs/help.
5. Validate with shell checks and dry-run/self-check paths.

## Out of scope
- Broad memory tuning of the AI stack.
- Changing AppArmor policy.
- Pausing services for build-only or boot-only runs.

## Success criteria
- Live switch path can free memory before activation.
- Paused services are restored afterward via an idempotent cleanup path.
- Operator can disable the behavior if needed.
- Existing deploy semantics remain intact for non-switch modes.
