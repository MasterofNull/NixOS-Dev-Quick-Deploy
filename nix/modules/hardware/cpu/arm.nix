{ lib, config, ... }:
# ---------------------------------------------------------------------------
# Generic ARM64 (AArch64) CPU module
#
# Covers: ARM Cortex-A based SoCs where the vendor is not Qualcomm or Apple.
# Examples: Raspberry Pi 4/5 (BCM2711/2712), AllWinner H3/H5/H6, Rockchip
#           RK3399/RK3588, PINE64 boards, NXP i.MX, Samsung Exynos (non-Qualcomm).
#
# Activation gate: mySystem.hardware.cpuVendor == "arm"
#
# Key differences from x86_64:
#   - No CPU microcode packages (ARM SoC firmware is board-specific, not CPU-vendor-specific)
#   - No thermald (Intel-only)
#   - No AMD P-state / Intel HWP — cpuidle/cpufreq managed by kernel drivers
#   - DTB (Device Tree Blob) is provided by nixos-hardware board modules; do not set here
#   - Many ARM boards need board-specific kernel config via nixos-hardware
#
# Board-specific tuning goes in nix/hosts/<host>/default.nix by importing the
# appropriate nixos-hardware module (e.g. nixos-hardware.nixosModules.raspberry-pi-4).
# ---------------------------------------------------------------------------
let
  cfg    = config.mySystem;
  isArm  = cfg.hardware.cpuVendor == "arm";
in
{
  config = lib.mkIf isArm {
    # ---- CPU frequency scaling ---------------------------------------------
    # schedutil is the best general-purpose governor on ARM:
    # it couples frequency decisions to the scheduler's CFS load estimates,
    # responding faster than ondemand while saving more power than performance.
    powerManagement.cpuFreqGovernor = lib.mkDefault "schedutil";

    # ---- Thermal management ------------------------------------------------
    # thermald is Intel-only.  ARM SoCs manage thermals via kernel thermal
    # zones and their own cooling trip points (defined in the Device Tree).
    # Do NOT enable thermald on ARM — it will fail to start.
    # services.thermald.enable is intentionally not set here; the Intel module
    # owns that option and only activates on Intel CPUs.

    # ---- Boot settings for ARM devices ------------------------------------
    # Most ARM boards use U-Boot or EFI + systemd-boot.
    # board-specific bootloader config (e.g. extlinux, u-boot) should be
    # set via nixos-hardware modules for the specific board family.

    # Disable x86-only features that would fail on ARM
    boot.loader.grub.enable = lib.mkDefault false;

    # ---- ARM-specific kernel modules ----------------------------------------
    # cpufreq drivers are built in on most ARM kernels; no module loading needed.
    # Board SoC drivers are loaded via the appropriate nixos-hardware module.

    # ---- Power management --------------------------------------------------
    # Generic ARM boards benefit from auto-cpufreq / schedutil.
    # power-profiles-daemon works on platforms that support ACPI P-states
    # (mainly Qualcomm Snapdragon X Elite and later AArch64 boards with ACPI).
    # For DTB-based boards without ACPI, schedutil is sufficient.
    powerManagement.enable = lib.mkDefault true;
  };
}
