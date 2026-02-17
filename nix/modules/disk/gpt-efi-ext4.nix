{ lib, config, ... }:
let
  cfg = config.mySystem.disk;
in
{
  config = lib.mkIf (cfg.layout == "gpt-efi-ext4") {
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
                type = "filesystem";
                format = "ext4";
                mountpoint = "/";
              };
            };
          };
        };
      };
    };
  };
}
