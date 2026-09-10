{ ... }:
# ---------------------------------------------------------------------------
# facts.nix — aqos-install-vm: disposable disko install-MECHANICS harness
# host (slice s1a, .agents/plans/aqos-installer-experience/
# END-TO-END-BARE-METAL-PLAN.md; driven by
# scripts/testing/aqos-install-vm-dogfood.sh). NOT a real machine — hand
# authored (not discover-system-facts.sh output), modeled on
# nix/hosts/aqos-vm/facts.nix.
#
# Unlike aqos-vm (disk.layout = "none", relies entirely on
# `nixos-rebuild build-vm`'s own self-synthesized disk — never partitions
# anything), THIS host declares a REAL disko layout so its
# nixosConfiguration is a genuine disko-backed target. /dev/vda is the
# canonical first virtio disk inside disko's own rootless in-VM test runner
# (inputs.disko.lib.testLib.makeDiskoTest, wired in flake.nix as
# checks.x86_64-linux.aqos-install-vm-disko-{plain,luks}; concrete partition
# shapes live in ./disko-plain.nix and ./disko-luks.nix) — that framework
# overwrites disko.devices.*.device with the real in-VM device path
# regardless of what's declared here (lib.mkForce, priority 50, always
# wins), so the device path below only matters for evaluating this host
# standalone (`nix eval .#nixosConfigurations.aqos-install-vm-plain`).
#
# The plain layout (gpt-efi-ext4) is the default below; the LUKS variant is
# selected purely via a flake-level `extraModules` override in flake.nix
# (nixosConfigurations.aqos-install-vm-luks) — never by hand-editing this
# file, so ONE host directory is reused for both proof runs.
# ---------------------------------------------------------------------------
{
  mySystem = {
    hostName = "aqos-install-vm";
    primaryUser = "aqosvm";
    # Documents intent only — nixosConfigurations.aqos-install-vm-{plain,luks}
    # force this profile directly in flake.nix (mkHost { profile = "aqos-workstation"; }).
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

    # Real disko layout (unlike aqos-vm's "none") — proves the
    # mySystem.disk.layout wiring end-to-end for the golden profile. See
    # header comment: overwritten by disko's testLib for the actual
    # partition/format/boot proof; kept here so this host is also a
    # standalone, self-consistent disko-backed NixOS configuration.
    disk = {
      layout = "gpt-efi-ext4";
      device = "/dev/vda";
      luks.enable = false;
      btrfsSubvolumes = [ "@root" "@home" "@nix" ];
    };

    # No secure boot in a disposable VM — also keeps systemd-boot (not
    # lanzaboote) selected by nix/modules/core/base.nix's useSystemdBoot gate.
    secureboot.enable = false;
  };
}
