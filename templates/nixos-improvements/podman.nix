# Rootless Podman Container Runtime
# NixOS 25.11 Xantusia
# Purpose: Optional, declarative enablement of Podman for local containers.
#
# Features:
# - Rootless Podman with docker-compatible CLI.
# - Podman Compose support for local stacks (AI-Optimizer, local LLMs, etc.).
# - Proper sub-uid/sub-gid mappings for rootless operation.
# - Simple defaults; no specific containers are defined here.
#
# Usage: Import this file in your configuration.nix:
#   imports = [ ./nixos-improvements/podman.nix ];

{ config, pkgs, lib, ... }:

{
  # Enable Podman with rootless support
  virtualisation.podman = {
    enable = true;
    dockerCompat = true;  # docker alias for podman
    defaultNetwork.settings = {
      dns_enabled = true;
    };

    # Enable automatic network setup
    autoPrune = {
      enable = true;
      dates = "weekly";
    };
  };

  # Enable containers to run rootless (critical fix for newuidmap error)
  virtualisation.containers = {
    enable = true;
    storage.settings = {
      storage = {
        # Use mkDefault to allow override by main configuration (e.g., for zfs)
        driver = lib.mkDefault "overlay";
        runroot = lib.mkDefault "/run/containers/storage";
        graphroot = lib.mkDefault "/var/lib/containers/storage";
        options.overlay.mountopt = lib.mkDefault "nodev,metacopy=on";
      };
    };
  };

  # Ensure newuidmap/newgidmap have correct capabilities (fixes permission error)
  security.wrappers = {
    newuidmap = {
      source = "${pkgs.shadow}/bin/newuidmap";
      setuid = true;
      owner = "root";
      group = "root";
    };
    newgidmap = {
      source = "${pkgs.shadow}/bin/newgidmap";
      setuid = true;
      owner = "root";
      group = "root";
    };
  };

  environment.systemPackages = with pkgs; [
    podman
    podman-compose
    podman-tui  # TUI for podman management
    skopeo      # Work with container images
    buildah     # Build OCI containers
  ];
}
