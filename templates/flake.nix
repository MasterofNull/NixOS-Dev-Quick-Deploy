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
        specialArgs = {
          inherit nix-flatpak;
        };
        modules = [
          ./configuration.nix
          home-manager.nixosModules.home-manager
          {
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.users."HOME_USERNAME_PLACEHOLDER" = import ./home.nix;
          }
        ];
      };

      homeConfigurations."HOME_USERNAME_PLACEHOLDER" = home-manager.lib.homeManagerConfiguration {
        pkgs = nixpkgs.legacyPackages.${system};
        extraSpecialArgs = {
          inherit nix-flatpak;
        };
        modules = [
          ./home.nix
        ];
      };
    };
}
