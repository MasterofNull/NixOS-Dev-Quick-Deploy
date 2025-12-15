# Engineering Environment – PCB, IC, CAD/CAM, 3D Printing

**Domain:** [nixos-dev]  
**Version:** 1.0  
**Date:** 2025-12-05

This cheat sheet summarizes the engineering toolchain and dev shells provided by NixOS-Dev-Quick-Deploy for PCB/IC design, CAD/CAM, and 3D printing, without changing the core architecture or cluttering the root directory.

---

## 1. Installed Engineering Toolchain (Home Manager)

Defined in `templates/home.nix` under `home.packages`:

- **PCB & Electronics**
  - `kicad` – PCB design suite.
  - `ngspice` – SPICE simulator (KiCad integration).

- **Mechanical CAD / 3D Modeling**
  - `freecad` – Parametric 3D CAD.
  - `openscad` – Programmatic 3D CAD (code-based models).
  - `blender` – General-purpose 3D modeling and visualization.

- **Digital IC / FPGA**
  - `yosys` – Synthesis framework.
  - `nextpnr` – Place-and-route.
  - `iverilog` – Verilog simulator.
  - `gtkwave` – Waveform viewer.

These packages are installed at the user level via Home Manager, keeping the system base lean while providing a rich engineering environment.

**Slim profile behavior:**  
If you select the **minimal** Flatpak profile during the Phase 1 user settings prompt, the generated `home.nix` uses a **slim** engineering profile (it omits the heavy PCB/CAD/IC packages above). The default `core` and `ai_workstation` profiles keep the full engineering toolchain enabled.
This does not affect the dev shells themselves – `pcb-design`, `ic-design`, `cad-cam`, and `ts-dev` are always available via `nix develop` once the flake is rendered.

---

## 2. Dev Shells (`nix develop`)

Defined in `templates/flake.nix` under `devShells.${system}`. From the rendered flake directory:

```bash
# PCB / electronics design shell
nix develop .#pcb-design

# Digital IC / FPGA design shell
nix develop .#ic-design

# Mechanical CAD / 3D printing shell
nix develop .#cad-cam

# TypeScript / Node.js development shell
nix develop .#ts-dev
```

Each shell includes:

- **`pcb-design`**
  - KiCad, FreeCAD, OpenSCAD, ngspice.
  - Shell hook prints: “📐 PCB design shell ready (KiCad, FreeCAD, OpenSCAD, ngspice).”

- **`ic-design`**
  - Yosys, nextpnr, Icarus Verilog, GTKWave, ngspice.
  - Shell hook prints: “🧠 IC/FPGA design shell ready (Yosys, nextpnr, Icarus Verilog, GTKWave, ngspice).”

- **`cad-cam`**
  - FreeCAD, OpenSCAD, Blender.
  - Shell hook prints: “🛠️  CAD/CAM shell ready (FreeCAD, OpenSCAD, Blender).”

- **`ts-dev`**
  - Node.js 22, TypeScript, ts-node, TypeScript language server, ESLint.
  - Shell hook prints: “📦 TypeScript dev shell ready (Node.js 22, TypeScript, ESLint).”
  - Use this shell as the standard environment for future Python→TypeScript ports and TS-based tooling.

These dev shells keep heavy tooling out of `environment.systemPackages`, aligning with the original goal of a clean, modular NixOS-Dev configuration.

---

## 3. Workflow Hints (High-Level)

- **PCB Flow**
  - Design schematic & PCB: KiCad.
  - Run simulations: export netlist and simulate with ngspice.
  - Optional 3D visualization: FreeCAD / Blender imports.

- **IC / FPGA Flow**
  - Write Verilog / SystemVerilog.
  - Synthesize with Yosys → place & route with nextpnr.
  - Simulate with Icarus Verilog; inspect waves with GTKWave.

- **CAD / 3D Printing Flow**
  - Model parts in FreeCAD or OpenSCAD.
  - Export STL; slice with your preferred slicer (e.g., PrusaSlicer from Flathub or Nixpkgs with `allowBroken` when appropriate).
  - Send G-code to printer via your preferred workflow.

These flows are intentionally described at a high level; detailed per-project instructions belong in project-specific docs or repositories, keeping NixOS-Dev-Quick-Deploy clean and reusable.

---

## 4. Cleanup & Maintenance Alignment

- Engineering tools are:
  - Declared in `templates/home.nix` (user environment, not system base).
  - Exposed via `devShells` in `templates/flake.nix` (for focused, per-task environments).
- No new top-level root docs were created; this file lives under `docs/` and is linked via the architecture/roadmap, respecting the documentation organization rules in `AGENTS.md`:
  - System overview remains in `README.md` and `SYSTEM_PROJECT_DESIGN.md`.
  - Architecture in `docs/ARCHITECTURE.md`.
  - Roadmap and rules in `docs/DEVELOPMENT-ROADMAP.md`.
  - Engineering environment details here in `docs/ENGINEERING-ENVIRONMENT.md`.

For hosts that also run local AI stacks to assist with PCB/IC/CAD workflows, use the AI environment knobs described in `docs/AI_INTEGRATION.md`:
- `AI_PROFILE` controls how heavy local LLM usage should be (for example `cpu_slim` on smaller laptops, `cpu_full` on workstations).
- `AI_STACK_PROFILE` switches between personal, guest, or no local stack.
- `config/edge-model-registry.json` describes which externally hosted models are available for each profile.
You can always inspect the current settings with `./scripts/ai-env-summary.sh` from the repo root.

This keeps the repo organized while expanding the engineering capabilities of the NixOS-Dev-Quick-Deploy system.
