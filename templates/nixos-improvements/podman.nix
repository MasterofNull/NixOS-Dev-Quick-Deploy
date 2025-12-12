# Rootless Podman Container Runtime
# NixOS 25.11 Xantusia
# Purpose: Optional, declarative enablement of Podman for local containers.
#
# Features:
# - Rootless Podman with docker-compatible CLI.
# - Podman Compose support for local stacks (AI-Optimizer, local LLMs, etc.).
# - Simple defaults; no specific containers are defined here.
#
# Usage: Import this file in your configuration.nix:
#   imports = [ ./nixos-improvements/podman.nix ];

{ config, pkgs, lib, ... }:

{
  virtualisation.podman = {
    enable = true;
    dockerCompat = true;
    defaultNetwork.settings = {
      dns_enabled = true;
    };
  };

  environment.systemPackages = with pkgs; [
    podman
    podman-compose
  ];
}
