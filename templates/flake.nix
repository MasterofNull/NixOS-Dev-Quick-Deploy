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
  };

  outputs = { self, nixpkgs, home-manager, nix-flatpak, ... }:
    let
      system = "SYSTEM_PLACEHOLDER";
    in
    {
      nixosConfigurations."HOSTNAME_PLACEHOLDER" = nixpkgs.lib.nixosSystem {
        inherit system;
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
        modules = [
          nix-flatpak.homeManagerModules.nix-flatpak
          ./home.nix
        ];
      };
    };
}
