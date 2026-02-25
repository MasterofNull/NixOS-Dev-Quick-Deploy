{ lib, config, ... }:
{
  imports =
    [ ./facts.nix ]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [ ./hardware-configuration.nix ];

  mySystem.localhostIsolation.enable = lib.mkDefault true;
  mySystem.mcpServers.repoPath =
    lib.mkDefault "/home/${config.mySystem.primaryUser}/Documents/NixOS-Dev-Quick-Deploy";
}
