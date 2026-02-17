{ lib, config, ... }:
let
  cfg = config.mySystem;
  desktopEnabled = cfg.roles.desktop.enable;
in
{
  config = lib.mkIf desktopEnabled {
    # Desktop-capable hosts should boot to a graphical login, not multi-user TTY.
    systemd.defaultUnit = lib.mkDefault "graphical.target";

    services.xserver.enable = lib.mkDefault true;
    services.displayManager.gdm.enable = lib.mkDefault true;
    services.desktopManager.gnome.enable = lib.mkDefault true;

    # Keep previous behavior: login directly to the primary user on personal hosts.
    services.displayManager.autoLogin.enable = lib.mkDefault true;
    services.displayManager.autoLogin.user = lib.mkDefault cfg.primaryUser;

    security.rtkit.enable = lib.mkDefault true;
    services.pipewire = {
      enable = lib.mkDefault true;
      alsa.enable = lib.mkDefault true;
      pulse.enable = lib.mkDefault true;
    };

    networking.networkmanager.enable = lib.mkDefault true;
  };
}
