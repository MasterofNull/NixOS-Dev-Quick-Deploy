# nix/modules/hardware/default.nix
#
# Single import point for the full hardware module tree.
# Import only THIS file from flake.nix — do not import individual modules directly.
#
# Every module gates itself on mySystem.hardware.* options, so importing the full
# set on every machine is safe: inactive conditions produce zero NixOS options.
#
# ┌───────────────────────────────────────────────────────────────────────────┐
# │  CPU MODULES            Gates on cpuVendor =                              │
# │  cpu/amd.nix            "amd"       — AMD Ryzen/EPYC (x86_64)            │
# │  cpu/intel.nix          "intel"     — Intel Core/Xeon (x86_64)           │
# │  cpu/arm.nix            "arm"       — Generic ARM Cortex-A (aarch64)     │
# │  cpu/qualcomm.nix       "qualcomm"  — Snapdragon SoC (aarch64)           │
# │  cpu/apple-silicon.nix  "apple"     — Apple M-series via Asahi (aarch64) │
# │  cpu/riscv64.nix        "riscv"     — RISC-V (riscv64gc)                 │
# ├───────────────────────────────────────────────────────────────────────────┤
# │  GPU MODULES            Gates on gpuVendor =                              │
# │  gpu/amd.nix            "amd"       — AMD Radeon (RDNA/GCN, Mesa)        │
# │  gpu/intel.nix          "intel"     — Intel HD/Iris/UHD iGPU (i915/xe)  │
# │  gpu/intel-arc.nix      "intel-arc" — Intel Arc A/B discrete (xe/i915)  │
# │  gpu/nvidia.nix         "nvidia"    — NVIDIA GeForce/Quadro (proprietary)│
# │  gpu/adreno.nix         "adreno"    — Qualcomm Adreno (freedreno/Turnip) │
# │  gpu/mali.nix           "mali"      — ARM Mali (Panfrost/Lima, open)     │
# │  gpu/apple.nix          "apple"     — Apple AGX (Asahi Mesa honeykrisp)  │
# ├───────────────────────────────────────────────────────────────────────────┤
# │  PLATFORM MODULES       Always imported; gate on individual options       │
# │  storage.nix            storageType — BFQ scheduler, TRIM, NVMe tuning   │
# │  ram-tuning.nix         systemRamGb — zswap, Nix build limits (adaptive) │
# │  mobile.nix             isMobile    — power profiles, lid/key handling   │
# │  recovery.nix           rootFsckMode — emergency shell, fsck skip        │
# └───────────────────────────────────────────────────────────────────────────┘
#
# igpuVendor (hybrid GPU) is consumed by the GPU modules themselves:
#   - gpu/intel.nix  activates ALSO when igpuVendor == "intel"  (Optimus iGPU)
#   - gpu/amd.nix    activates ALSO when igpuVendor == "amd"    (dual-AMD APU)
#
# To add a new host: run scripts/discover-system-facts.sh which auto-detects
# CPU/GPU vendor and writes the correct values to nix/hosts/<host>/facts.nix.
{ ... }:
{
  imports = [
    # ── CPU modules ─────────────────────────────────────────────────────────
    ./cpu/amd.nix
    ./cpu/intel.nix
    ./cpu/arm.nix
    ./cpu/qualcomm.nix
    ./cpu/apple-silicon.nix
    ./cpu/riscv64.nix

    # ── GPU modules ─────────────────────────────────────────────────────────
    ./gpu/amd.nix
    ./gpu/intel.nix
    ./gpu/intel-arc.nix
    ./gpu/nvidia.nix
    ./gpu/adreno.nix
    ./gpu/mali.nix
    ./gpu/apple.nix

    # ── Platform / system modules ───────────────────────────────────────────
    ./storage.nix
    ./ram-tuning.nix
    ./mobile.nix
    ./recovery.nix
  ];
}
