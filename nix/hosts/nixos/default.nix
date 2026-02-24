{ lib, pkgs, ... }:
{
  imports =
    [ ./facts.nix ]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [ ./hardware-configuration.nix ];

  # Keep Steam available on this ai-dev workstation while still using the
  # flake-first role model (drivers + 32-bit graphics from roles/gaming.nix).
  mySystem.roles.gaming.enable = lib.mkForce true;

  # Host-level font baseline: keep popular Nerd Fonts available system-wide
  # for COSMIC Terminal font picker and prompt glyph rendering.
  fonts = {
    fontconfig.enable = true;
    fontDir.enable = true;
    packages = with pkgs; [
      nerd-fonts.meslo-lg
      nerd-fonts.jetbrains-mono
      nerd-fonts.fira-code
      nerd-fonts.hack
      noto-fonts
      noto-fonts-color-emoji
    ];
  };
}
