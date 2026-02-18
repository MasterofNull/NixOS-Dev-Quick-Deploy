{ lib, ... }:
# Per-host Home Manager config for hyperd.
# home.username and home.homeDirectory are injected by flake.nix from
# mySystem.primaryUser — do NOT declare them here.
{
  # ---- Git identity -------------------------------------------------------
  # Override the placeholder identity set in nix/home/base.nix.
  programs.git.settings = {
    user.name = lib.mkDefault "NixOS User";
    user.email = lib.mkDefault "user@localhost";
  };

  # ---- Machine-specific packages ------------------------------------------
  # Packages already in nix/home/base.nix (ripgrep, fd, jq, git, etc.) do not
  # need to be repeated here.
  # home.packages = with pkgs; [ ];
}
