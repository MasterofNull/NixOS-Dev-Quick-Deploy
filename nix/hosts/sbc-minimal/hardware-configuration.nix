{ ... }:
{
  # Placeholder reference hardware configuration for the sbc-minimal example.
  # Replace this with the real output from `nixos-generate-config` on target
  # hardware before deploying to a physical SBC.
  boot.initrd.availableKernelModules = [ "sd_mod" "mmc_block" "usb_storage" ];
  boot.kernelModules = [ ];

  fileSystems."/" = {
    device = "/dev/disk/by-label/NIXOS_SD";
    fsType = "ext4";
  };
}
