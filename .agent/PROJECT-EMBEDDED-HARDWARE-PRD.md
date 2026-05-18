# PRD — embedded-hardware Domain Activation

**Domain tag:** `embedded-hardware`
**Status:** Proposed — Phase 58A capability expansion
**Authors:** Claude (orchestrator/architect)
**Date:** 2026-05-18
**Upstream template:** `docs/architecture/domain-activation-template.md`

---

## Problem Statement

The harness has no formal domain for embedded hardware and firmware development. Current state per the master PRD:

- **Good:** SBC and low-resource deployment support, hardware capability matrix (`config/hardware-capability-matrix.json`), ROCm promotion gate as a model for hardware-gated workflows.
- **Absent:** HDL toolchain (Verilator, GHDL, Yosys), ARM/RISC-V cross-compilation shells, OpenOCD/SWD/JTAG tooling, device-tree authoring, Zephyr/embedded Rust reference knowledge in AIDB.

Without a formal domain, agents responding to embedded queries have no canonical tool order, no AIDB knowledge base, no routing preference, and no safety boundary for dual-use hardware tooling (e.g., firmware writes, JTAG access).

---

## Goal

Establish `embedded-hardware` as a first-class capability domain. Initial activation covers:

1. Registering the domain (proposed → implemented cycle begins)
2. Declaring the routing preference and AIDB namespace
3. Authoring the agent instruction surface (`.agent/EMBEDDED-HARDWARE-INSTRUCTIONS.md`)
4. Wiring a baseline validation hook that confirms the hardware capability matrix and discovery tooling are present

Provisioning of Verilator, GHDL, Yosys, OpenOCD, and ARM/RISC-V cross-toolchains via Nix dev shells is the primary follow-on slice (embedded-hardware.1).

---

## Kernel Objects Touched

| Kernel object | How this domain touches it |
|---|---|
| `intent` | Adds `embedded-hardware` intent class → routes to `remote-reasoning` for HDL/architecture queries; `local-tool-calling` for simulation/synthesis invocation |
| `memory-evidence` | Datasheet extracts, device-tree patterns, board support notes → AIDB namespace `embedded-hardware-patterns` |
| `route-profile` | Prefers `remote-reasoning` for HDL design review; `local-tool-calling` for QEMU/Verilator/OpenOCD invocation; `default` for reference lookup |
| `delegation-review` | All firmware write and JTAG/SWD operations require explicit user confirmation (not delegatable to autonomous agents) |

---

## Routing Profile(s)

| Use case | Profile | Rationale |
|---|---|---|
| HDL design review / architecture | `remote-reasoning` | Complex; long-form reasoning needed |
| Simulation (Verilator, GHDL, QEMU) | `local-tool-calling` | CLI invocation; deterministic |
| Cross-compile build (ARM, RISC-V) | `local-tool-calling` | Local Nix dev shell; no remote needed |
| Reference / datasheet lookup | `default` | AIDB retrieval; Qwen adequate |
| Firmware flash / JTAG operations | Human-gated | Non-autonomous; confirm with user before execution |

All profiles exist in the canonical inventory. No new profile needed. Firmware flash/JTAG is classified as approval-gated per `docs/operations/AUTONOMOUS-OPERATIONS-POLICY.md`.

---

## AIDB Namespace

**Namespace:** `embedded-hardware-patterns`

Purpose: Store datasheet extracts, device-tree patterns, board support playbooks, HDL design patterns, Zephyr/embedded Rust reference material, and MCU register maps so sessions inherit prior hardware knowledge.

Initial seeding: Add `config/hardware-capability-matrix.json` content + known ARM/RISC-V ecosystem notes in `embedded-hardware.3` slice.
Indexing: Add to `scripts/automation/aidb-reindex.sh` once domain reaches `implemented`.

---

## Tool Preferences

### Preferred tools (ordered)

1. `nix develop .#embedded` — domain dev shell (provision in embedded-hardware.1; not yet available)
2. `verilator --lint-only <hdl>` — HDL lint (provision in embedded-hardware.1)
3. `ghdl -a <vhdl>` — VHDL analysis (provision in embedded-hardware.1)
4. `yosys -p "synth" <verilog>` — synthesis check (provision in embedded-hardware.1)
5. `qemu-system-arm` / `qemu-system-riscv64` — simulation (likely available via nixpkgs)
6. `openocd` — JTAG/SWD debug (provision in embedded-hardware.1; require user confirmation before flash ops)
7. `scripts/governance/discover-system-facts.sh` — hardware baseline refresh
8. `config/hardware-capability-matrix.json` — query hardware class before recommending toolchain
9. `scripts/governance/tier0-validation-gate.sh --pre-commit` — mandatory before commit

### Tool availability status (2026-05-18)

| Tool | Available | Notes |
|---|---|---|
| `qemu-system-arm` | Likely (nixpkgs) | Check with `which qemu-system-arm` |
| `verilator` | Not provisioned | Follow-on: embedded-hardware.1 |
| `ghdl` | Not provisioned | Follow-on: embedded-hardware.1 |
| `yosys` | Not provisioned | Follow-on: embedded-hardware.1 |
| `openocd` | Not provisioned | Follow-on: embedded-hardware.1; requires user confirm for flash |
| `arm-none-eabi-gcc` | Not provisioned | Follow-on: embedded-hardware.1 |

### Fallback order (tools absent)

`qemu-system-arm` (simulation) → `nix-instantiate` (check Nix cross config) → AIDB pattern lookup → remote-reasoning query → escalate to human

### Forbidden

- Firmware flash or JTAG write operations without explicit user confirmation
- Using unverified LLM-generated register values in hardware configuration (use datasheet as ground truth)
- `mkForce` override of hardware capability matrix without orchestrator approval
- Cross-compile toolchain from `pip install` or external script (NixOS-first: Nix dev shell only)
- Connecting to JTAG/SWD targets on production hardware without user authorization

---

## Security and Safety Considerations

- Embedded tooling is dual-use. Agents in this domain must not: generate exploit payloads for specific hardware targets, generate code to disable secure boot or bypass firmware signature verification, or write to hardware registers on running production systems without explicit user authorization.
- Firmware writes and JTAG/SWD operations are **approval-gated** per `docs/operations/AUTONOMOUS-OPERATIONS-POLICY.md`.
- QEMU simulation (no real hardware) is safe for autonomous agent use.
- LLM-generated register maps must be validated against a cited datasheet before use.
- Datasheet ingestion into AIDB: strip proprietary confidentiality notices before indexing; do not ingest under NDA.

---

## Acceptance Criteria

1. `config/capability-lifecycle-registry.json` contains an `embedded-hardware` entry at state ≥ `proposed`.
2. `.agent/EMBEDDED-HARDWARE-INSTRUCTIONS.md` exists with domain tag, task classes, tool preferences, AIDB namespace binding, and dual-use safety rules.
3. `config/validation-check-registry.json` contains an `embedded-hardware-health` check that exits 0 when baseline artifacts (hardware-capability-matrix.json, discover-system-facts.sh) are present.
4. When domain reaches `implemented`: Verilator + GHDL + Yosys in a `nix develop .#embedded` shell; ARM cross-toolchain available; aq-qa check exits 0; AIDB namespace seeded.
5. When domain reaches `validated`: Gemini review-gate PASS on one HDL or firmware workflow; no P0/P1 regressions in `aq-qa 0`.

---

## Rollback Procedure

1. Set `embedded-hardware` registry state to `blocked`.
2. Remove `embedded-hardware` intent class from `config/intent-routing-map.json` if added.
3. Disable `embedded-hardware-health` check in `config/validation-check-registry.json` (`"enabled": false`).
4. Archive (do not delete) `embedded-hardware-patterns` AIDB namespace content.
5. Remove `embedded` dev shell from `flake.nix` if added.

---

## Open Items (follow-on slices)

| Item | Slice |
|---|---|
| Provision Verilator, GHDL, Yosys, OpenOCD, ARM/RISC-V cross-toolchain in `nix develop .#embedded` | embedded-hardware.1 |
| Wire `embedded-hardware` intent class in `config/intent-routing-map.json` | embedded-hardware.2 |
| Seed `embedded-hardware-patterns` AIDB namespace | embedded-hardware.3 |
| Datasheet ingestion pipeline (PDF → AIDB chunks) | embedded-hardware.4 |
| Update `embedded-hardware-health` check for real tool invocation | embedded-hardware.5 |
| Gemini review gate on first HDL workflow output | embedded-hardware.6 (→ validated) |

---

## Related Docs

- `docs/architecture/domain-activation-template.md`
- `docs/architecture/capability-lifecycle.md`
- `docs/architecture/gemini-review-gate.md`
- `docs/architecture/qwen-task-eligibility.md`
- `docs/architecture/routing-profile-inventory.md`
- `docs/operations/AUTONOMOUS-OPERATIONS-POLICY.md`
- `config/hardware-capability-matrix.json`
- `scripts/governance/discover-system-facts.sh`
- `scripts/governance/rocm-promotion-gate.sh` (model for hardware-gated promotion workflows)
