{ ... }:
# ---------------------------------------------------------------------------
# facts.nix — aqos-vm: disposable VM host for the P3 VM-dogfood activation
# harness (scripts/testing/aqos-vm-dogfood.sh). NOT a real machine — hand
# authored (not discover-system-facts.sh output) to describe a generic,
# hardware-agnostic QEMU target for `nixos-rebuild build-vm`.
#
# Purpose: prove the golden aqos-workstation profile (AI OFF) evaluates and
# boots as a throwaway VM, with no real disk and no sudo required to build.
# See .agents/plans/aqos-installer-experience/P3-SLICE-PLAN.md ("VM dogfood").
# ---------------------------------------------------------------------------
{
  mySystem = {
    hostName = "aqos-vm";
    primaryUser = "aqosvm";
    # Documents intent only — nixosConfigurations.aqos-vm forces this profile
    # directly in flake.nix (mkHost { hostName = "aqos-vm"; profile = "aqos-workstation"; }).
    profile = "aqos-workstation";
    system = "x86_64-linux";

    hardware = {
      gpuVendor = "none";
      igpuVendor = "none";
      rocmGpuTarget = null;
      cpuVendor = "unknown";
      storageType = "ssd";
      systemRamGb = 4;
      isMobile = false;
      firmwareType = "efi";
      earlyKmsPolicy = "off";
      nixosHardwareModule = null;
    };

    kernel = {
      track = "latest-stable";
    };

    deployment = {
      enableHibernation = false;
      swapSizeGb = 0;
      rootFsckMode = "check";
      initrdEmergencyAccess = true;
    };

    # "none" + hardware-configuration.nix (below) satisfies the flake's
    # disk-layout assertion without pulling in disko (no real disk in a VM).
    disk = {
      layout = "none";
      device = "/dev/disk/by-id/CHANGE-ME";
      luks.enable = false;
      btrfsSubvolumes = [ "@root" "@home" "@nix" ];
    };

    # No secure boot in a disposable VM — also keeps systemd-boot (not
    # lanzaboote) selected by nix/modules/core/base.nix's useSystemdBoot gate.
    secureboot.enable = false;
  };
}
