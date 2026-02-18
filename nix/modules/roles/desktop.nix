{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Desktop role — COSMIC desktop environment with cosmic-greeter.
#
# Activated when: mySystem.roles.desktop.enable = true
#
# Provisions:
#   - COSMIC desktop + cosmic-greeter (replaces GDM/GNOME)
#   - Hyprland (available alongside COSMIC)
#   - Wayland session environment variables
#   - PipeWire audio, NetworkManager, Bluetooth
#   - GNOME keyring (secrets + SSH unlock, PAM-integrated)
#   - XDG portals: COSMIC → Hyprland → GNOME fallback (NIX-ISSUE-013)
#   - Flatpak + Flathub remote (idempotent oneshot)
#   - Printing, core fonts
#
# Auto-login is intentionally OFF by default (security).
# Enable in per-host default.nix for personal single-user workstations.
# ---------------------------------------------------------------------------
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

    # ---- Desktop environment: COSMIC + cosmic-greeter ----------------------
    # GDM/GNOME are intentionally omitted; cosmic-greeter handles the login
    # screen and COSMIC handles the session.
    services.desktopManager.cosmic.enable      = lib.mkDefault true;
    services.displayManager.cosmic-greeter.enable = lib.mkDefault true;

    # Hyprland is available alongside COSMIC for users who prefer a tiling WM.
    programs.hyprland.enable = lib.mkDefault true;

    # Auto-login: off by default. Override in per-host default.nix:
    #   services.displayManager.autoLogin = { enable = true; user = "alice"; };
    services.displayManager.autoLogin.enable = lib.mkDefault false;
    services.displayManager.autoLogin.user   = lib.mkDefault cfg.primaryUser;

    # ---- Wayland session environment ---------------------------------------
    environment.sessionVariables = {
      QT_QPA_PLATFORM             = lib.mkDefault "wayland";
      MOZ_ENABLE_WAYLAND          = lib.mkDefault "1";
      NIXOS_OZONE_WL              = lib.mkDefault "1";
      COSMIC_DATA_CONTROL_ENABLED = lib.mkDefault "1";
    };

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

    # ---- GNOME keyring (secrets / SSH key unlock) -------------------------
    # gnome-keyring unlocks SSH keys and stores secrets (GPG, passwords).
    # PAM integration ensures the keyring is unlocked automatically at login.
    # gcr-ssh-agent replaces the keyring SSH component in nixpkgs ≥ 26.05;
    # guard it so 25.11 builds don't fail on a missing option.
    services.gnome.gnome-keyring.enable = lib.mkDefault true;
    services.gnome.gcr-ssh-agent.enable =
      lib.mkIf (lib.versionAtLeast lib.version "26.05") (lib.mkDefault true);

    # Disable Tracker/tinysparql on COSMIC — not needed, adds startup weight.
    services.gnome.tinysparql.enable =
      lib.mkIf (lib.versionAtLeast lib.version "25.11") (lib.mkDefault false);

    security.pam.services = {
      greetd.enableGnomeKeyring = lib.mkDefault true;
      login.enableGnomeKeyring  = lib.mkDefault true;
      passwd.enableGnomeKeyring = lib.mkDefault true;
    };

    # ---- XDG desktop portals -----------------------------------------------
    # Required for Flatpak file-picker, screenshot, screen-cast, etc.
    xdg.portal = {
      enable               = lib.mkDefault true;
      extraPortals         = lib.mkDefault extraPortals;
      config.common.default = lib.mkDefault "*";
    };

    # ---- Flatpak -----------------------------------------------------------
    # Declarative Flatpak app sync is performed by scripts/sync-flatpak-profile.sh
    # after nixos-rebuild (the app list comes from mySystem.profileData.flatpakApps).
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
