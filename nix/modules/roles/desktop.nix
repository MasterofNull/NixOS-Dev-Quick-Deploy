{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  desktopEnabled = cfg.roles.desktop.enable;

  # XDG portal backend selection.
  # xdg-desktop-portal-gnome requires gnome-shell running — do NOT add it when
  # a non-GNOME DE is active (NIX-ISSUE-013).  Use COSMIC or Hyprland portal
  # when available; fall back to GNOME portal only on older/GNOME-only systems.
  hasCosmicPortal   = builtins.hasAttr "xdg-desktop-portal-cosmic"   pkgs;
  hasHyprlandPortal = builtins.hasAttr "xdg-desktop-portal-hyprland" pkgs;
  hasGnomePortal    = builtins.hasAttr "xdg-desktop-portal-gnome"    pkgs;

  extraPortals =
    lib.optional hasCosmicPortal   pkgs.xdg-desktop-portal-cosmic
    ++ lib.optional hasHyprlandPortal pkgs.xdg-desktop-portal-hyprland
    ++ lib.optional (!hasCosmicPortal && hasGnomePortal)
         pkgs.xdg-desktop-portal-gnome;
in
{
  config = lib.mkIf desktopEnabled {

    # ---- Boot target -------------------------------------------------------
    systemd.defaultUnit = lib.mkDefault "graphical.target";

    # ---- Display server & desktop environment ------------------------------
    services.xserver.enable = lib.mkDefault true;
    services.displayManager.gdm.enable = lib.mkDefault true;
    services.desktopManager.gnome.enable = lib.mkDefault true;

    # Auto-login to primary user on personal workstations.
    services.displayManager.autoLogin.enable = lib.mkDefault true;
    services.displayManager.autoLogin.user   = lib.mkDefault cfg.primaryUser;

    # ---- Audio -------------------------------------------------------------
    security.rtkit.enable = lib.mkDefault true;
    services.pipewire = {
      enable            = lib.mkDefault true;
      alsa.enable       = lib.mkDefault true;
      alsa.support32Bit = lib.mkDefault true;
      pulse.enable      = lib.mkDefault true;
    };

    # ---- Networking --------------------------------------------------------
    networking.networkmanager.enable = lib.mkDefault true;

    # ---- Bluetooth ---------------------------------------------------------
    hardware.bluetooth = {
      enable      = lib.mkDefault true;
      powerOnBoot = lib.mkDefault true;
    };
    services.blueman.enable = lib.mkDefault true;

    # ---- XDG desktop portals -----------------------------------------------
    # Required for Flatpak file-picker, screenshot, screen-cast, etc.
    xdg.portal = {
      enable        = lib.mkDefault true;
      extraPortals  = lib.mkDefault extraPortals;
      config.common.default = lib.mkDefault "*";
    };

    # ---- Flatpak -----------------------------------------------------------
    # Declarative Flatpak app sync is performed by scripts/sync-flatpak-profile.sh
    # after nixos-rebuild (the app list comes from mySystem.profileData.flatpakApps).
    # This option ensures the Flatpak daemon and system helper are always present.
    services.flatpak.enable = lib.mkDefault true;

    # Add Flathub remote via a one-shot systemd service (idempotent, online only).
    systemd.services.flatpak-add-flathub = {
      description   = "Add Flathub remote to Flatpak system installation";
      wantedBy      = [ "multi-user.target" ];
      after         = [ "network-online.target" "flatpak-system-helper.service" ];
      wants         = [ "network-online.target" ];
      serviceConfig = {
        Type            = "oneshot";
        RemainAfterExit = true;
        ExecStart       = "${pkgs.flatpak}/bin/flatpak remote-add "
          + "--if-not-exists flathub "
          + "https://dl.flathub.org/repo/flathub.flatpakrepo";
      };
    };

    # ---- Printing ----------------------------------------------------------
    services.printing.enable = lib.mkDefault true;

    # ---- Fonts -------------------------------------------------------------
    fonts.fontconfig.enable = lib.mkDefault true;
    fonts.packages = lib.mkDefault (with pkgs; [
      noto-fonts
      noto-fonts-cjk-sans
      noto-fonts-emoji
      liberation_ttf
    ]);
  };
}
