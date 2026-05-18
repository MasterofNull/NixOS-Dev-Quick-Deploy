# Embedded-Hardware Domain — Agent Instruction Payload

**Domain tag:** `embedded-hardware`
**State:** proposed (2026-05-18)
**Upstream authority:** `.agent/PROJECT-EMBEDDED-HARDWARE-PRD.md`, `docs/architecture/capability-lifecycle.md`
**Registry ID:** `embedded-hardware` in `config/capability-lifecycle-registry.json`

---

## Domain Scope

This instruction surface applies whenever an agent operates in the `embedded-hardware` domain — i.e., performing:

- HDL design, simulation, or synthesis (Verilog, VHDL, SystemVerilog)
- Firmware authoring or analysis (C, Rust, assembly for MCU targets)
- Cross-compilation for ARM, RISC-V, or other embedded targets
- Device-tree authoring and validation
- JTAG/SWD debug session planning (NOT autonomous execution — approval-gated)
- Board support package (BSP) research or authoring
- Datasheet parsing and register-map extraction
- Embedded knowledge retrieval from AIDB (`embedded-hardware-patterns` namespace)

Agents MUST check `config/hardware-capability-matrix.json` before recommending a toolchain or acceleration backend for any embedded target.

---

## Eligible Task Classes

Reference: `docs/architecture/qwen-task-eligibility.md`

| Task class | Eligible agents | Notes |
|---|---|---|
| Register-map lookup from AIDB | Qwen (Tier A) | Pure retrieval; bounded |
| HDL lint (verilator --lint-only on ≤2 files) | Qwen (Tier A) | Deterministic; bounded |
| Device-tree snippet authoring (≤100 lines) | Qwen (Tier B) | Review-gated; validate with dtc |
| Firmware C scaffold (≤400 lines, known MCU) | Qwen (Tier B) | Review-gated; no real flash |
| HDL architecture review | Gemini | Research/comparative; Gemini review gate required |
| BSP playbook research | Gemini | Discovery tasks; Gemini review gate on output |
| Firmware flash / JTAG write planning | Claude only | Approval-gated; confirm with user before execution |
| Cross-toolchain Nix shell authoring | Claude/Gemini | Architectural; Gemini review gate on flake changes |

Qwen MUST NOT:
- Invoke `openocd` with write/flash operations
- Connect to physical hardware targets autonomously
- Generate register values without citing a datasheet source
- Produce firmware for secure boot bypass or hardware exploit

Gemini MUST NOT:
- Submit embedded-hardware code without Claude or Codex review
- Invoke physical hardware tooling (openocd, JTAG) in any mode

---

## Dual-Use Safety Rules

Embedded tooling can be dual-use. ALL agents in this domain must:

1. **Firmware writes and JTAG/SWD operations are approval-gated.** Confirm with user before executing. This includes: `openocd -c "program"`, flashing via dfu-util, or any command that modifies persistent hardware state.
2. **Do not generate code** to disable secure boot, bypass firmware signatures, or extract device secrets without explicit user authorization and documented legal/authorization context.
3. **Validate register values against a cited datasheet** before including them in firmware. LLM-generated register values are untrusted.
4. **QEMU simulation only** for autonomous agent use. No real hardware operations without approval.
5. **Datasheet ingestion:** Strip proprietary notices; do not ingest material under NDA.

---

## Tool Preferences

### Preferred tools (ordered)

1. Check `config/hardware-capability-matrix.json` — hardware class before any toolchain recommendation
2. `nix develop .#embedded` — domain dev shell (not yet provisioned; embedded-hardware.1)
3. `verilator --lint-only <hdl>` — HDL lint (not yet provisioned)
4. `ghdl -a <vhdl>` — VHDL analysis (not yet provisioned)
5. `qemu-system-arm` / `qemu-system-riscv64` — simulation (check availability first)
6. `dtc -I dts -O dtb` — device-tree compiler (system utility)
7. `openocd` — JTAG/SWD debug — **APPROVAL-GATED for write/flash ops**
8. `agrep "<pattern>" .` — search existing embedded config/code before authoring
9. `scripts/governance/discover-system-facts.sh` — hardware baseline refresh
10. `scripts/governance/tier0-validation-gate.sh --pre-commit` — mandatory before commit

### Fallback order (tools not provisioned)

`qemu-system-arm` → `dtc` → `nix-instantiate --parse` (cross config) → AIDB pattern lookup → remote-reasoning query → escalate

### Forbidden

- Firmware flash / JTAG write without user confirmation
- LLM-generated register values used without datasheet citation
- `pip install` for embedded toolchains (NixOS-first: Nix dev shell only)
- Code that disables secure boot or firmware signature verification
- Connecting to physical JTAG/SWD targets autonomously

---

## AIDB Namespace Binding

**Namespace:** `embedded-hardware-patterns`

- **Read:** Before authoring device-tree or register maps, query: `POST /query` with `{"query": "<component/MCU description>", "mode": "local"}` and namespace filter `embedded-hardware-patterns`.
- **Write:** After resolving embedded challenge or extracting datasheet pattern: `POST /api/memory/facts` with metadata `{"namespace": "embedded-hardware-patterns", "domain": "embedded-hardware", "source": "<datasheet or url>"}`.
- **Dedup:** MemoryBroker `{"status":"skipped"}` = success.
- **Seeding:** `embedded-hardware.3` slice will seed from `config/hardware-capability-matrix.json` + known ARM/RISC-V ecosystem notes.

---

## Review Requirements

Per `docs/architecture/gemini-review-gate.md`:

| Work category | Gate required |
|---|---|
| New Nix dev shell for embedded toolchain | Gemini review gate |
| HDL architecture or synthesis workflow | Gemini review gate |
| BSP playbook or datasheet ingestion pipeline | Gemini review gate |
| JTAG/SWD operation planning | User confirmation (not just gate) |
| Device-tree snippet (Qwen Tier B) | Gemini review gate |
| Register-map lookup (pure retrieval) | No gate required |
| HDL lint pass (no synthesis, no flash) | No gate required |

---

## Routing Preference Summary

| Query type | Profile | Notes |
|---|---|---|
| HDL design review / architecture | `remote-reasoning` | Complex; reasoning-heavy |
| Simulation / cross-compile invocation | `local-tool-calling` | CLI tools; local |
| Reference / datasheet lookup | `default` | AIDB retrieval; Qwen adequate |
| Firmware flash / JTAG planning | Human-gated | Not autonomous |

---

## Activation Checklist (for orchestrator)

Before marking the domain `implemented`:

- [ ] `nix develop .#embedded` shell defined in `flake.nix` with Verilator, GHDL, Yosys, ARM/RISC-V cross
- [ ] `embedded-hardware` intent class added to `config/intent-routing-map.json`
- [ ] `embedded-hardware-patterns` AIDB namespace seeded
- [ ] `scripts/automation/aidb-reindex.sh` includes `embedded-hardware-patterns` step
- [ ] `embedded-hardware-health` check updated to test tool invocation (e.g., `verilator --version`)

Before marking the domain `validated`:

- [ ] Gemini review-gate PASS on one HDL or BSP workflow output
- [ ] No firmware-write operation attempted without user confirmation
- [ ] `aq-qa embedded-hardware-health` exits 0 in CI
- [ ] No P0/P1 regressions in `aq-qa 0`
