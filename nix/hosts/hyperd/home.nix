{ pkgs, ... }:
{
  home.username = "hyperd";
  home.homeDirectory = "/home/hyperd";

  home.packages = with pkgs; [
    fd
    ripgrep
  ];
}
