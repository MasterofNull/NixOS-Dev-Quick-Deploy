{ lib, ... }:
{
  # Git identity (user.name, user.email) is written directly to ~/.gitconfig
  # by nixos-quick-deploy.sh so it remains mutable after every switch.
  # Do not set a shared credential.helper default here: Home Manager's freeform
  # git settings merge treats duplicate scalar definitions as hard conflicts,
  # even when host deploy overlays intend to override them.
  programs.git = {
    enable = lib.mkDefault true;
  };
}
