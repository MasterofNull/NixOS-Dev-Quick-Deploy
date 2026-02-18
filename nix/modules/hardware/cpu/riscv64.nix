{ lib, config, ... }:
# ---------------------------------------------------------------------------
# RISC-V CPU module (riscv64gc)
#
# Covers: RISC-V 64-bit processors running NixOS.
# Examples:
#   - SiFive HiFive Unmatched (FU740-C000)  — the canonical NixOS RISC-V board
#   - StarFive VisionFive 2 (JH7110)        → nixos-hardware module available
#   - AllWinner D1 / Nezha (single-core RV) → minimal support
#   - QEMU virt machine (riscv64)           → primary development/CI target
#
# Activation gate: mySystem.hardware.cpuVendor == "riscv"
#
# Architecture note: set mySystem.system = "riscv64-linux" in facts.nix.
# This is a nascent architecture in NixOS; many packages are cross-compiled
# from x86_64, and some may not build natively yet.
#
# RISC-V notes:
#   - No CPU microcode packages (RISC-V does not use x86/ARM-style microcode)
#   - No thermald (Intel-only)
#   - cpufreq scaling: very board-dependent; not all RISC-V boards expose
#     cpufreq interfaces.  schedutil is set as the default but may be a no-op.
#   - Most RISC-V boards use U-Boot + OpenSBI (RISC-V Supervisor Binary Interface)
#   - nixos-hardware covers StarFive VisionFive 2 and SiFive HiFive boards
#
# Recommended nixos-hardware for RISC-V boards:
#   VisionFive 2  → inputs.nixos-hardware.nixosModules.starfive-visionfive2
# ---------------------------------------------------------------------------
let
  cfg      = config.mySystem;
  isRiscV  = cfg.hardware.cpuVendor == "riscv";
in
{
  config = lib.mkIf isRiscV {
    # ---- CPU frequency scaling -----------------------------------------------
    # schedutil is set as the default; many RISC-V boards do not expose cpufreq
    # interfaces and will silently ignore this setting.
    powerManagement.cpuFreqGovernor = lib.mkDefault "schedutil";

    # ---- Power management ---------------------------------------------------
    powerManagement.enable = lib.mkDefault true;

    # thermald and power-profiles-daemon are x86/ACPI-specific.
    # They must NOT be enabled on RISC-V.
    services.power-profiles-daemon.enable = lib.mkDefault false;
    services.tlp.enable = lib.mkForce false;

    # ---- Boot configuration ------------------------------------------------
    # RISC-V uses U-Boot + OpenSBI (SBI acts as the firmware layer).
    # systemd-boot on RISC-V requires UEFI support from U-Boot (available on
    # VisionFive 2 and HiFive Unmatched).  Set to false for non-UEFI boards.
    boot.loader.grub.enable = lib.mkDefault false;

    # ---- Initrd -------------------------------------------------------------
    # systemd-based initrd works on RISC-V with kernel 6.x.
    boot.initrd.systemd.enable = lib.mkDefault true;

    # ---- Nix build parallelism ---------------------------------------------
    # Most RISC-V development boards have 4 cores and ≤8GB RAM.
    # ram-tuning.nix sets adaptive limits from systemRamGb; no override needed.

    # ---- Zswap / swap -------------------------------------------------------
    # RISC-V boards often have limited RAM.  ram-tuning.nix enables zswap
    # adaptively.  For boards with eMMC swap, add a swapDevices entry in the
    # host-specific default.nix.

    # ---- RISC-V specific notes ---------------------------------------------
    # OpenSBI version and extensions depend on the board.  If SBI features
    # (e.g. RFENCE, IPI) are missing, the kernel will log warnings but usually
    # continues to boot.
    #
    # For QEMU virt machine testing:
    #   qemu-system-riscv64 -M virt -cpu rv64 -m 4G -smp 4 \
    #     -bios <opensbi_fw_jump.elf> -kernel <nixos-kernel>
  };
}
