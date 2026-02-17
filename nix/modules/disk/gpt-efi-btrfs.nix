{ lib, config, ... }:
let
  cfg = config.mySystem.disk;
  mkMountpoint = name:
    if name == "@root" then
      "/"
    else if lib.hasPrefix "@" name then
      "/" + (lib.removePrefix "@" name)
    else
      "/" + name;
  subvolumes =
    builtins.listToAttrs (map (name: {
      inherit name;
      value.mountpoint = mkMountpoint name;
    }) cfg.btrfsSubvolumes);
in
{
  config = lib.mkIf (cfg.layout == "gpt-efi-btrfs") {
    disko.devices = {
      disk.main = {
        type = "disk";
        device = cfg.device;
        content = {
          type = "gpt";
          partitions = {
            ESP = {
              size = "1G";
              type = "EF00";
              content = {
                type = "filesystem";
                format = "vfat";
                mountpoint = "/boot";
              };
            };
            root = {
              size = "100%";
              content = {
                type = "btrfs";
                subvolumes = subvolumes;
              };
            };
          };
        };
      };
    };
  };
}
