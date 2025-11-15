# =============================================================================
# Flake Skeleton
# =============================================================================
# This template is rendered by lib/config.sh with deployment-specific values.
# Placeholders:
#   NIXPKGS_CHANNEL_PLACEHOLDER  ← substituted with selected nixpkgs channel
#   HM_CHANNEL_PLACEHOLDER       ← home-manager channel reference
#   SYSTEM_PLACEHOLDER           ← architecture (x86_64-linux, etc.)
#   HOSTNAME_PLACEHOLDER         ← system hostname
#   HOME_USERNAME_PLACEHOLDER    ← home-manager username
#
# The template intentionally avoids hardcoding home-manager as a NixOS module
# to keep `nixos-rebuild` from depending on the flake during system activation.
# =============================================================================
{
  description = "AIDB NixOS and Home Manager configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/NIXPKGS_CHANNEL_PLACEHOLDER";
    home-manager = {
      url = "github:nix-community/home-manager?ref=HM_CHANNEL_PLACEHOLDER";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    #nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";
    nix-flatpak.url = "github:gmodena/nix-flatpak";
    nixAiTools = {
      url = "github:numtide/nix-ai-tools";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, nix-flatpak, nixAiTools, ... }:
    let
      lib = nixpkgs.lib;
      system = "SYSTEM_PLACEHOLDER";
      nixAiToolsPackages =
        if nixAiTools ? packages && builtins.hasAttr system nixAiTools.packages then
          nixAiTools.packages.${system}
        else
          {};
    in
    {
      nixosConfigurations."HOSTNAME_PLACEHOLDER" = nixpkgs.lib.nixosSystem {
        inherit system;
        specialArgs = {
          inherit nixAiToolsPackages;
        };
        modules = [
          ./configuration.nix
          # Note: home-manager is used standalone (via homeConfigurations below)
          # Not as a NixOS module to avoid dependency issues during nixos-rebuild
        ];
      };

      homeConfigurations."HOME_USERNAME_PLACEHOLDER" = home-manager.lib.homeManagerConfiguration {
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };
        extraSpecialArgs = {
          inherit nixAiToolsPackages;
        };
        modules = [
          nix-flatpak.homeManagerModules.nix-flatpak
          ./home.nix
        ];
      };
    };
}
