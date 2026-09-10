{ ... }:
# ---------------------------------------------------------------------------
# Placeholder hardware configuration for the aqos-vm dogfood host.
#
# This host is never installed on real hardware — it only exists to be built
# with `nixos-rebuild build-vm`, which synthesizes its own virtual disk/boot
# path (nixos/modules/virtualisation/qemu-vm.nix overrides fileSystems with
# mkVMOverride). This file exists solely to satisfy the flake's disk-layout
# assertion (mySystem.disk.layout = "none" requires a hardware-configuration.nix)
# so the host EVALUATES cleanly; the device path below is never touched.
# ---------------------------------------------------------------------------
{
  fileSystems."/" = {
    device = "/dev/disk/by-label/AQOS_VM_ROOT";
    fsType = "ext4";
  };
}
