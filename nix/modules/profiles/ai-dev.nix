{ lib, config, ... }:
let
  cfg = config.mySystem;
  flatpakProfiles = import ../../data/flatpak-profiles.nix;
  profilePackages = import ../../data/profile-system-packages.nix;
in
{
  config = lib.mkIf (cfg.profile == "ai-dev") {
    mySystem.roles.aiStack.enable = lib.mkDefault true;
    mySystem.roles.virtualization.enable = lib.mkDefault true;
    mySystem.roles.gaming.enable = lib.mkDefault false;
    mySystem.roles.desktop.enable = lib.mkDefault true;
    mySystem.mcpServers.enable = lib.mkDefault true;
    mySystem.profileData.flatpakApps = lib.mkDefault flatpakProfiles.ai_workstation;
    mySystem.profileData.systemPackageNames = lib.mkDefault profilePackages.ai-dev;
  };
}
