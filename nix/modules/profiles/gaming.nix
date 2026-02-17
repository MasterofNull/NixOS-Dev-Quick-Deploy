{ lib, config, ... }:
let
  cfg = config.mySystem;
  flatpakProfiles = import ../../data/flatpak-profiles.nix;
  profilePackages = import ../../data/profile-system-packages.nix;
in
{
  config = lib.mkIf (cfg.profile == "gaming") {
    mySystem.roles.gaming.enable = lib.mkDefault true;
    mySystem.roles.aiStack.enable = lib.mkDefault false;
    mySystem.roles.desktop.enable = lib.mkDefault true;
    mySystem.profileData.flatpakApps = lib.mkDefault flatpakProfiles.gaming;
    mySystem.profileData.systemPackageNames = lib.mkDefault profilePackages.gaming;

    programs.gamemode.enable = lib.mkDefault true;
  };
}
