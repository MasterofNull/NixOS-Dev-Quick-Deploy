{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  isAmd = cfg.hardware.cpuVendor == "amd";
in
{
  # AMD CPU: microcode, P-state, thermal.
  # Owns services.thermald.enable for ALL profiles — Intel cpu/intel.nix sets it true.
  hardware.cpu.amd.updateMicrocode = lib.mkIf isAmd (lib.mkDefault true);

  # schedutil is built into the kernel; no module load needed.
  powerManagement.cpuFreqGovernor = lib.mkIf isAmd (lib.mkDefault "schedutil");

  # Enable AMD P-state driver when the kvm-amd module is loaded (virtualisation or bare-metal).
  # lib.mkAfter ensures it appends after any hardware-configuration.nix params.
  boot.kernelParams = lib.mkIf isAmd (lib.mkAfter [
    "amd_pstate=active"
  ]);

  # thermald is Intel-only; explicitly disable on AMD to prevent crash loops.
  # This is the single owner of services.thermald.enable — do not set it elsewhere.
  services.thermald.enable = lib.mkIf isAmd (lib.mkForce false);
}
