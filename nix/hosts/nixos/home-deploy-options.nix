{ lib, ... }:
{
  programs.git = {
    enable = lib.mkDefault true;
    settings = {
      user.name = lib.mkForce "NixOS User";
      user.email = lib.mkForce "user@localhost";
    };
  };
}
