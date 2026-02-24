{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Gaming role — Steam, Proton, Gamemode, MangoHud, Wine.
#
# Activated when: mySystem.roles.gaming.enable = true
#
# Layers on top of any profile. Requires the desktop role (or equivalent
# graphics stack) to be active — this module does not enable a DE on its own.
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  gamingEnabled = cfg.roles.gaming.enable;
in
{
  config = lib.mkIf gamingEnabled {

    # ---- Steam + Proton ------------------------------------------------
    programs.steam = {
      enable = lib.mkDefault true;
      # Open firewall ports for Steam Remote Play.
      remotePlay.openFirewall = lib.mkDefault true;
      # Open firewall ports for local network game transfers.
      localNetworkGameTransfers.openFirewall = lib.mkDefault true;
      # Gamescope compositor session for better game compatibility and HDR.
      gamescopeSession.enable = lib.mkDefault true;
    };

    # Explicit for clarity; also implied by programs.steam.enable.
    hardware.steam-hardware.enable = lib.mkDefault true;

    # ---- Performance utilities -----------------------------------------
    programs.gamemode.enable = lib.mkDefault true;

    # ---- 32-bit graphics support (required for many Windows games) -----
    hardware.graphics = {
      enable      = lib.mkDefault true;
      enable32Bit = lib.mkDefault true;
    };

    # ---- Wine / Proton-GE ecosystem ------------------------------------
    environment.systemPackages = with pkgs; [
      wine          # Windows compatibility layer
      winetricks    # Wine prefix configuration helper
      lutris        # Game launcher with Wine/Proton management
      heroic        # Epic Games / GOG / Amazon launcher
      mangohud      # Performance overlay (MangoHud NixOS module removed upstream)
    ];
  };
}
