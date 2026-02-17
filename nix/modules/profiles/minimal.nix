{ lib, config, ... }:
let
  cfg = config.mySystem;
  flatpakProfiles = import ../../data/flatpak-profiles.nix;
  profilePackages = import ../../data/profile-system-packages.nix;
in
{
  config = lib.mkIf (cfg.profile == "minimal") {
    mySystem.roles.aiStack.enable = lib.mkDefault false;
    mySystem.roles.gaming.enable = lib.mkDefault false;
    mySystem.roles.desktop.enable = lib.mkDefault false;
    mySystem.profileData.flatpakApps = lib.mkDefault flatpakProfiles.minimal;
    mySystem.profileData.systemPackageNames = lib.mkDefault profilePackages.minimal;
  };
}
