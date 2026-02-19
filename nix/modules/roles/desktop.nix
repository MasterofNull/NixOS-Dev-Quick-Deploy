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
      XDG_DATA_HOME               = lib.mkDefault "$HOME/.local/share";
      # XDG_DATA_DIRS is NOT set here.  services.flatpak.enable handles
      # adding /var/lib/flatpak/exports/share and the per-user export path
      # via /etc/profile.d/flatpak.sh.  Hardcoding it here caused both paths
      # to be inserted TWICE, making every Flatpak app appear twice in the
      # COSMIC launcher (NIX-ISSUE: fix-duplicate-flatpaks-whq2y).
    };

    # ---- Audio -------------------------------------------------------------
    security.rtkit.enable = lib.mkDefault true;
    services.pipewire = {
      enable            = lib.mkDefault true;
      alsa.enable       = lib.mkDefault true;
      alsa.support32Bit = lib.mkDefault true;
      pulse.enable      = lib.mkDefault true;
    };

    # Disable wireplumber's libcamera UVC monitor to prevent SIGABRT crash.
    # Root cause: libcamera's PipelineHandlerUVC::match() calls LOG(Fatal) when
    # the UVC pipeline cannot bind, which invokes abort() via LogMessage dtor.
    # wireplumber then receives SIGABRT and core-dumps.
    # Fix: disable the "monitor.libcamera" component in the main wireplumber profile.
    # This has no effect on USB webcams through the kernel V4L2 path, which
    # wireplumber's "monitor.v4l2" handles independently.
    # Reference: NIX-ISSUE-010 / CLAUDE.md recurring errors table.
    services.pipewire.wireplumber.extraConfig."10-disable-libcamera" = {
      "wireplumber.profiles".main."monitor.libcamera" = "disabled";
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

    # Allow wheel-group members to install/update/remove Flatpak apps and manage
    # remotes without repeated polkit password prompts.
    # Root cause of the repeated "[sudo] password for hyperd:" prompts during
    # the deploy script's flatpak sync: each batch of runtime/app installs triggers
    # a separate flatpak-system-helper polkit authorisation round.
    security.polkit.extraConfig = ''
      polkit.addRule(function(action, subject) {
        if (action.id.startsWith("org.freedesktop.Flatpak") &&
            subject.isInGroup("wheel")) {
          return polkit.Result.YES;
        }
      });
    '';

    # ---- Flatpak user-scope deduplication ------------------------------------
    # Removes any user-scope Flatpak apps that are already installed system-wide.
    # Root cause: COSMIC's app launcher (and any graphical Flatpak client) scans
    # both /var/lib/flatpak/exports/share/applications/ (system) and
    # ~/.local/share/flatpak/exports/share/applications/ (user).  If the same
    # app is installed at both levels, it appears twice in the launcher.
    # This oneshot runs at login as the primary user and removes user-scope
    # duplicates, making the system the single source of truth for Flatpak apps
    # that were installed declaratively via sync-flatpak-profile.sh.
    systemd.user.services.flatpak-dedup-user-apps = {
      description = "Remove user-scope Flatpak apps already installed system-wide";
      wantedBy    = [ "default.target" ];
      after       = [ "flatpak-system-helper.service" ];
      serviceConfig = {
        Type            = "oneshot";
        RemainAfterExit = false;
        ExecStart = pkgs.writeShellScript "flatpak-dedup-user-apps" ''
          set -euo pipefail
          flatpak=${pkgs.flatpak}/bin/flatpak
          # List system-installed app IDs.
          mapfile -t sys_apps < <("$flatpak" list --system --app --columns=application 2>/dev/null || true)
          [[ ''${#sys_apps[@]} -eq 0 ]] && exit 0
          # For each system app, uninstall the user-scope copy if it exists.
          mapfile -t user_apps < <("$flatpak" list --user --app --columns=application 2>/dev/null || true)
          for app in "''${user_apps[@]}"; do
            if printf '%s\n' "''${sys_apps[@]}" | grep -Fxq "$app"; then
              echo "flatpak-dedup: removing user-scope duplicate: $app"
              "$flatpak" uninstall --user --noninteractive "$app" 2>/dev/null || true
            fi
          done
        '';
      };
    };

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

    # ---- Geolocation (GeoClue2) --------------------------------------------
    # Required by COSMIC settings daemon for automatic day/night theme switching
    # and timezone detection.  Privacy note: location is only exposed to apps
    # that have been granted access (see services.geoclue2.appConfig).
    services.geoclue2 = {
      enable = lib.mkDefault true;
      appConfig."com.system76.CosmicSettings" = {
        isAllowed = true;
        isSystem  = true;
        users     = [ ];
      };
    };

    # ---- cosmic-greeter runtime directories --------------------------------
    # cosmic-greeter requires several config subdirectories to exist under
    # /var/lib/cosmic-greeter at first boot, otherwise the greeter silently
    # falls back to a blank session or fails to start.
    # Created via systemd-tmpfiles so they survive across nixos-rebuild.
    systemd.tmpfiles.rules = lib.mkAfter [
      "d /var/lib/cosmic-greeter                                             0750 cosmic-greeter cosmic-greeter -"
      "d /var/lib/cosmic-greeter/.config                                     0750 cosmic-greeter cosmic-greeter -"
      "d /var/lib/cosmic-greeter/.config/cosmic                              0750 cosmic-greeter cosmic-greeter -"
      "d /var/lib/cosmic-greeter/.config/cosmic/com.system76.CosmicComp      0750 cosmic-greeter cosmic-greeter -"
      "d /var/lib/cosmic-greeter/.config/cosmic/com.system76.CosmicComp/v1   0750 cosmic-greeter cosmic-greeter -"
      "d /var/lib/cosmic-greeter/.config/cosmic/com.system76.CosmicTheme.Dark 0750 cosmic-greeter cosmic-greeter -"
      "d /var/lib/cosmic-greeter/.config/cosmic/com.system76.CosmicTheme.Dark/v1 0750 cosmic-greeter cosmic-greeter -"
      "d /var/lib/cosmic-greeter/.config/cosmic/com.system76.CosmicTheme.Mode 0750 cosmic-greeter cosmic-greeter -"
      "d /var/lib/cosmic-greeter/.config/cosmic/com.system76.CosmicTheme.Mode/v1 0750 cosmic-greeter cosmic-greeter -"
      "d /var/lib/cosmic-greeter/.config/cosmic/com.system76.CosmicTk        0750 cosmic-greeter cosmic-greeter -"
      "d /var/lib/cosmic-greeter/.config/cosmic/com.system76.CosmicTk/v1     0750 cosmic-greeter cosmic-greeter -"
      # Keep user Flatpak exports writable so per-user app sync can update icons/desktop exports.
      "d /home/${cfg.primaryUser}/.local/share/flatpak/exports                 0755 ${cfg.primaryUser} ${cfg.primaryUser} -"
      "d /home/${cfg.primaryUser}/.local/share/flatpak/exports/share           0755 ${cfg.primaryUser} ${cfg.primaryUser} -"
      "d /home/${cfg.primaryUser}/.local/share/flatpak/exports/share/icons     0755 ${cfg.primaryUser} ${cfg.primaryUser} -"
      "d /home/${cfg.primaryUser}/.local/share/flatpak/exports/share/icons/hicolor 0755 ${cfg.primaryUser} ${cfg.primaryUser} -"
      "z /home/${cfg.primaryUser}/.local/share/flatpak/exports                 - ${cfg.primaryUser} ${cfg.primaryUser} -"
    ];

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
