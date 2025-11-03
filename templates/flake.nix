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
      nixAiToolsOverlays =
        lib.optional
          (nixAiTools ? overlays && nixAiTools.overlays ? default)
          nixAiTools.overlays.default;
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
          { nixpkgs.overlays = nixAiToolsOverlays; }
          ./configuration.nix
          # Note: home-manager is used standalone (via homeConfigurations below)
          # Not as a NixOS module to avoid dependency issues during nixos-rebuild
        ];
      };

      homeConfigurations."HOME_USERNAME_PLACEHOLDER" = home-manager.lib.homeManagerConfiguration {
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
          overlays = nixAiToolsOverlays;
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
