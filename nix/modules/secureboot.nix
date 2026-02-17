{ lib, config, ... }:
let
  cfg = config.mySystem;
in
{
  config = lib.mkIf cfg.secureboot.enable {
    boot.loader.systemd-boot.enable = lib.mkForce false;
    boot.lanzaboote = {
      enable = true;
      pkiBundle = "/etc/secureboot";
    };
  };
}
