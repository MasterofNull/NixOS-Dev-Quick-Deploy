# PRD - Embedded Hardware Domain Activation

**Domain tag:** `embedded-hardware`
**Status:** Active foundation, destructive device operations approval-gated
**Last updated:** 2026-06-28

## Objective

Provide agents with a safe embedded hardware workflow for HDL linting, firmware authoring, cross-compilation guidance, device-tree review, and board-support analysis.

## Current Scope

- HDL design and lint workflows using declared toolchains such as Verilator/GHDL/Yosys.
- Firmware and ARM/RISC-V cross-compilation guidance.
- Device-tree and board-support review.
- Retrieval namespace: `embedded-hardware-patterns`.

## Safety Boundary

- Hardware flashing, JTAG/SWD access, fuse writes, bootloader replacement, and electrical actions require explicit approval.
- Prefer simulation, linting, static review, and reproducible build checks before physical-device interaction.

## Acceptance Criteria

- `embedded-hardware` exists in `config/capability-lifecycle-registry.json`.
- `.agent/EMBEDDED-HARDWARE-INSTRUCTIONS.md` is present.
- `config/hardware-capability-matrix.json` remains the hardware capability SSOT.
- `scripts/governance/discover-system-facts.sh` remains executable.
