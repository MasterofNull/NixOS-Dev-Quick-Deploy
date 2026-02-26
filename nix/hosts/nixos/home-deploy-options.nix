{ lib, ... }:
{
  # Git identity (user.name, user.email) is written directly to ~/.gitconfig
  # by nixos-quick-deploy.sh so it remains mutable after every switch.
  # Only enable git and optionally set the credential helper here.
  programs.git = {
    enable = lib.mkDefault true;
  };
}
