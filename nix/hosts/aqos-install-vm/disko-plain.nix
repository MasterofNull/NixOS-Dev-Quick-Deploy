# Test-only disko device tree for inputs.disko.lib.testLib.makeDiskoTest
# (see flake.nix checks.x86_64-linux.aqos-install-vm-disko-plain and
# scripts/testing/aqos-install-vm-dogfood.sh).
#
# Mirrors the PRODUCTION plain layout at
# nix/modules/disk/gpt-efi-ext4.nix (ESP + ext4 root) exactly, but as a
# plain (non-NixOS-module) attrset: makeDiskoTest's `disko-config` argument
# is evaluated OUTSIDE the NixOS module system (see disko's own
# lib/tests.nix `prepareDiskoConfig`, which does `cleanedTopLevel.disko.
# devices.disk` directly on whatever this file returns), so the
# mySystem.disk.layout-gated production module (which needs `config` from
# the module system) cannot be imported here directly. Keep this file in
# sync with gpt-efi-ext4.nix by hand — both must encode the same partition
# shape (ESP EF00 -> vfat /boot, root -> ext4 /).
{
  disko.devices.disk.main = {
    type = "disk";
    device = "/dev/vda"; # overwritten by disko's testLib.prepareDiskoConfig
    content = {
      type = "gpt";
      partitions = {
        ESP = {
          size = "512M";
          type = "EF00";
          content = {
            type = "filesystem";
            format = "vfat";
            mountpoint = "/boot";
            mountOptions = [ "umask=0077" ];
          };
        };
        root = {
          size = "100%";
          content = {
            type = "filesystem";
            format = "ext4";
            mountpoint = "/";
          };
        };
      };
    };
  };
}
