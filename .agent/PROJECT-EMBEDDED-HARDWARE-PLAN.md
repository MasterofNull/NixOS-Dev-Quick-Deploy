# Plan - Embedded Hardware

**PRD:** `.agent/PROJECT-EMBEDDED-HARDWARE-PRD.md`
**Status:** Baseline implemented
**Last updated:** 2026-06-28

## Scope

Activate embedded hardware guidance and governance without enabling destructive physical-device operations.

## Implementation Slices

1. Domain instruction anchor
   - Implemented: `.agent/EMBEDDED-HARDWARE-INSTRUCTIONS.md`

2. Lifecycle registry entry
   - Implemented: `embedded-hardware` in `config/capability-lifecycle-registry.json`

3. Hardware SSOT
   - Implemented: `config/hardware-capability-matrix.json`
   - Implemented: `scripts/governance/discover-system-facts.sh`

4. Safety boundary
   - Implemented in PRD and domain instructions: flashing, JTAG/SWD, fuse writes, and physical-device actions require explicit approval.

## Validation

- Focused CI: `embedded-hardware domain baseline artifact and hardware-matrix presence check`
- `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit`

## Remaining Work

- Add deterministic HDL lint fixture coverage before promoting new embedded toolchains beyond guidance/static review.
- Add dashboard visibility if a future embedded service or long-running worker is introduced.
