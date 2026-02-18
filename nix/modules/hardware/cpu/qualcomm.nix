{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Qualcomm Snapdragon SoC CPU module
#
# Covers: Qualcomm Snapdragon SoCs running Linux/NixOS.
# Examples:
#   - Lenovo ThinkPad X13s (Snapdragon 8cx Gen 3)   → nixos-hardware module available
#   - Snapdragon X Elite (Snapdragon X1E) laptops    → ACPI-based, power-profiles-daemon
#   - Qualcomm reference boards (QRB5165, RB3)       → Fedora / Linaro-based
#
# Activation gate: mySystem.hardware.cpuVendor == "qualcomm"
#
# Qualcomm-specific notes:
#   - Snapdragon uses heterogeneous CPU clusters (Kryo/Prime+Gold+Silver cores)
#     mapped via cpufreq-hw (CPUFREQ Hardware) on ACPI-based boards, or via
#     DT-cpufreq on DTB-based boards.
#   - schedutil is the recommended governor; it handles per-cluster scaling.
#   - The GPU (Adreno) is handled by nix/modules/hardware/gpu/adreno.nix.
#   - Board-specific setup goes via nixos-hardware (e.g. lenovo-thinkpad-x13s).
#   - thermald is Intel-only — do NOT enable it here.
#
# Recommended nixos-hardware modules for Snapdragon boards:
#   ThinkPad X13s  → inputs.nixos-hardware.nixosModules.lenovo-thinkpad-x13s
# ---------------------------------------------------------------------------
let
  cfg         = config.mySystem;
  isQualcomm  = cfg.hardware.cpuVendor == "qualcomm";
  isMobile    = cfg.hardware.isMobile;
in
{
  config = lib.mkIf isQualcomm {
    # ---- CPU frequency scaling -----------------------------------------------
    # schedutil integrates well with cpufreq-hw (Qualcomm's hardware-accelerated
    # freq decision engine on Snapdragon ACPI platforms).
    powerManagement.cpuFreqGovernor = lib.mkDefault "schedutil";

    # ---- Power management ---------------------------------------------------
    powerManagement.enable = lib.mkDefault true;

    # power-profiles-daemon: supported on ACPI-based Snapdragon platforms
    # (Snapdragon X Elite, ThinkPad X13s).  DTB-only boards may not expose
    # the ACPI platform_profile interface — this is a safe default.
    services.power-profiles-daemon.enable = lib.mkDefault (isMobile);
    services.tlp.enable = lib.mkIf isMobile (lib.mkForce false);  # conflicts with ppd

    # ---- Boot ---------------------------------------------------------------
    # Snapdragon X Elite and ThinkPad X13s use EFI + systemd-boot.
    # Older DTB-based boards use U-Boot.  nixos-hardware handles board specifics.
    boot.loader.grub.enable = lib.mkDefault false;

    # ---- Qualcomm-specific kernel modules -----------------------------------
    # qcom-spmi-pmic: PMIC driver for Snapdragon power management IC (battery,
    # regulators, GPIOs).  Built-in on most Qualcomm kernels; listed here as a
    # reminder that it must be available for suspend/resume to work correctly.
    # Uncomment if your distro kernel does not include it:
    # boot.kernelModules = [ "qcom-spmi-pmic" ];

    # ---- Suspend / Resume ---------------------------------------------------
    # Qualcomm Snapdragon suspend requires special handling:
    #   - mem_sleep_default=s2idle preferred (s2RAM often not fully supported)
    #   - wakeup sources via PMIC GPIO; handled by board-specific nixos-hardware
    boot.kernelParams = lib.mkAfter [
      "mem_sleep_default=s2idle"  # Qualcomm S2 idle (Connected Standby / AOSP)
    ];
  };
}
