# Project PRD — AppArmor Activation Reliability

## Objective
Reduce intermittent `apparmor.service` reload failures during `nixos-rebuild switch` by detecting critically low memory headroom before activation and surfacing a clear operator action.

## Current evidence
- AppArmor reload failures are intermittent, not deterministic.
- Failures alternate between small profiles and report `Out of memory`.
- Current host snapshot shows ~27 GiB RAM total, ~26 GiB used, and very low available headroom while swap is active.
- Profile files are tiny and successful reloads peak at only a few MiB.

## In scope
1. Add a preflight/readiness memory-headroom check in the deploy path.
2. Keep the threshold configurable and bounded.
3. Emit a clear warning/failure message that ties low headroom to activation risk.
4. Validate the new check with static/targeted testing.

## Out of scope
- Weakening AppArmor policy.
- Reworking memory use of llama.cpp or the whole AI stack.
- Broad host memory tuning.

## Success criteria
- Deploy/readiness path surfaces low-memory risk before activation.
- Healthy-memory systems are unaffected.
- Check is configurable and documented in script help/output.
- Slice is committed with handoff notes updated.
