{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  isIntel = cfg.hardware.cpuVendor == "intel";
in
{
  # Intel CPU: microcode and thermal management.
  hardware.cpu.intel.updateMicrocode = lib.mkIf isIntel (lib.mkDefault true);

  # thermald: Intel-only thermal daemon. Enabled when Intel microcode is active.
  # amd/cpu.nix uses lib.mkForce false on AMD systems to prevent conflict.
  services.thermald.enable = lib.mkIf isIntel (lib.mkDefault true);

  # Intel baseline: schedutil for balanced desktop/development performance.
  # Hosts that prioritize battery life can override in host-local modules.
  powerManagement.cpuFreqGovernor = lib.mkIf isIntel (lib.mkDefault "schedutil");

  # i915 for early display output. Conditionally added to initrd based on earlyKmsPolicy.
  boot.initrd.kernelModules = lib.mkIf (isIntel && cfg.hardware.earlyKmsPolicy == "force")
    (lib.mkAfter [ "i915" ]);
}
