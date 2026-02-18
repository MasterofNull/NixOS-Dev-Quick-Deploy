{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Apple Silicon (M-series) CPU module — Asahi Linux
#
# Covers: Apple M1, M2, M3, M4 (and Pro/Max/Ultra variants) running NixOS
# via the Asahi Linux project.
#
# Activation gate: mySystem.hardware.cpuVendor == "apple"
#
# CRITICAL: Apple Silicon requires a special kernel and firmware.
# This module provides NixOS settings; the Asahi-specific kernel, firmware,
# Mesa overlay, and boot configuration MUST come from either:
#   1. The official nixos-hardware Apple modules:
#        inputs.nixos-hardware.nixosModules.apple-m1
#        inputs.nixos-hardware.nixosModules.apple-m2
#   2. The nixos-apple-silicon community flake:
#        https://github.com/tpwrules/nixos-apple-silicon
#
# Without one of the above, NixOS will not boot on Apple Silicon hardware.
# Set mySystem.hardware.nixosHardwareModule in facts.nix to the appropriate
# nixos-hardware entry (e.g. "apple-m1", "apple-m2") so the flake.nix
# imports it automatically.
#
# Architecture: aarch64-linux (set mySystem.system = "aarch64-linux" in facts.nix)
#
# CPU topology: Apple M-series uses a heterogeneous core design:
#   - Efficiency cores (E-cores, "Icestorm"/"Sawtooth") — low-power
#   - Performance cores (P-cores, "Firestorm"/"Everest") — high-throughput
#   The Asahi kernel schedules appropriately via the generic scheduler;
#   no manual governor tuning is required.
#
# GPU: Apple AGX — handled by nix/modules/hardware/gpu/apple.nix
# ---------------------------------------------------------------------------
let
  cfg      = config.mySystem;
  isApple  = cfg.hardware.cpuVendor == "apple";
  isMobile = cfg.hardware.isMobile;
in
{
  config = lib.mkIf isApple {
    # ---- CPU frequency scaling -----------------------------------------------
    # Apple M-series firmware manages frequency/voltage natively.
    # The Asahi kernel exposes cpufreq via the Apple SoC cpufreq driver
    # (apple-cpufreq).  schedutil is the recommended governor.
    powerManagement.cpuFreqGovernor = lib.mkDefault "schedutil";

    # ---- Power management ---------------------------------------------------
    powerManagement.enable = lib.mkDefault true;

    # power-profiles-daemon: not yet supported on Asahi (as of 2026).
    # Apple's PMU exposes platform_profile for battery/balanced/performance
    # only on newer Asahi kernel versions.  Disable TLP to avoid conflicts.
    services.power-profiles-daemon.enable = lib.mkDefault false;
    services.tlp.enable = lib.mkForce false;

    # ---- Thermal management ------------------------------------------------
    # thermald is Intel-only.  Apple M-series manages thermals in firmware;
    # the Asahi kernel exposes thermal zones via /sys/class/thermal but
    # does not need a userspace thermal daemon.

    # ---- Boot configuration ------------------------------------------------
    # Apple Silicon uses m1n1 (Asahi bootloader) + U-Boot + systemd-boot.
    # The exact boot chain is configured by the Asahi installer and should not
    # be overridden here.  nixos-hardware apple modules handle this.
    boot.loader.grub.enable = lib.mkDefault false;
    # systemd-boot is used on top of U-Boot on Apple Silicon:
    boot.loader.systemd-boot.enable = lib.mkDefault true;
    boot.loader.efi.canTouchEfiVariables = lib.mkDefault false; # EFI vars are U-Boot managed

    # ---- Initrd -------------------------------------------------------------
    # systemd-based initrd works on Asahi (kernel 6.7+).
    boot.initrd.systemd.enable = lib.mkDefault true;

    # ---- Known-good kernel parameters for Asahi ----------------------------
    boot.kernelParams = lib.mkAfter [
      "apple_dcp.show_notch=1"   # Allow full display height (hide notch area)
    ];

    # ---- Nix build parallelism ---------------------------------------------
    # Apple M-series has high core counts (up to 24 on M3 Max).
    # nix.settings are set adaptively by ram-tuning.nix — no override needed.

    # ---- Firmware / WiFi ---------------------------------------------------
    # Apple firmware blobs for WiFi/BT must be extracted from macOS by the
    # Asahi installer.  nixos-hardware apple modules install the extraction
    # script and associated systemd unit.  Nothing to set here.

    # ---- Cross-compilation note -------------------------------------------
    # When building NixOS on an x86_64 host for Apple Silicon target, set:
    #   nixpkgs.crossSystem = lib.systems.examples.aarch64-multiplatform;
    # in your flake. The nixos-hardware apple modules include this automatically.
  };
}
