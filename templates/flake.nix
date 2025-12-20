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
    sops-nix = {
      url = "github:Mic92/sops-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixAiTools = {
      url = "github:numtide/nix-ai-tools";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nix-vscode-extensions = {
      url = "github:nix-community/nix-vscode-extensions";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, nix-flatpak, sops-nix, nixAiTools, nix-vscode-extensions, ... }:
    let
      lib = nixpkgs.lib;
      system = "SYSTEM_PLACEHOLDER";
      nixAiToolsPackages =
        if nixAiTools ? packages && builtins.hasAttr system nixAiTools.packages then
          nixAiTools.packages.${system}
        else
          {};
      devPkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };
    in
    {
      nixosConfigurations."HOSTNAME_PLACEHOLDER" = nixpkgs.lib.nixosSystem {
        inherit system;
        specialArgs = {
          inherit nixAiToolsPackages;
        };
        modules = [
          sops-nix.nixosModules.sops
          ./configuration.nix
          # Note: home-manager is used standalone (via homeConfigurations below)
          # Not as a NixOS module to avoid dependency issues during nixos-rebuild
        ];
      };

      homeConfigurations."HOME_USERNAME_PLACEHOLDER" = home-manager.lib.homeManagerConfiguration {
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ nix-vscode-extensions.overlays.default ];
          config.allowUnfree = true;
        };
        extraSpecialArgs = {
          inherit nixAiToolsPackages;
        };
        modules = [
          sops-nix.homeManagerModules.sops
          nix-flatpak.homeManagerModules.nix-flatpak
          ./home.nix
        ];
      };

      devShells.${system} = {
        # PCB / electronics design environment
        # Note: KiCad, FreeCAD, OpenSCAD available via Flatpak
        pcb-design = devPkgs.mkShell {
          packages = with devPkgs; [
            # kicad - using Flatpak (org.kicad.KiCad)
            # freecad - using Flatpak (org.freecad.FreeCAD)
            # openscad - using Flatpak (org.openscad.OpenSCAD)
            ngspice
          ];
          shellHook = ''
            echo "📐 PCB design shell ready (ngspice). Note: KiCad, FreeCAD, OpenSCAD available via Flatpak."
          '';
        };

        # Digital IC / FPGA design environment
        ic-design = devPkgs.mkShell {
          packages = with devPkgs; [
            yosys
            nextpnr
            iverilog
            gtkwave
            ngspice
          ];
          shellHook = ''
            echo "🧠 IC/FPGA design shell ready (Yosys, nextpnr, Icarus Verilog, GTKWave, ngspice)."
          '';
        };

        # Mechanical CAD / 3D printing environment
        # Note: FreeCAD, OpenSCAD available via Flatpak
        cad-cam = devPkgs.mkShell {
          packages = with devPkgs; [
            # freecad - using Flatpak (org.freecad.FreeCAD)
            # openscad - using Flatpak (org.openscad.OpenSCAD)
            blender
          ];
          shellHook = ''
            echo "🛠️  CAD/CAM shell ready (Blender). Note: FreeCAD, OpenSCAD available via Flatpak."
            '';
        };

        # TypeScript / Node.js development environment
        ts-dev = devPkgs.mkShell {
          packages = with devPkgs; [
            nodejs_22
            nodePackages.typescript
            nodePackages.ts-node
            nodePackages.typescript-language-server
            nodePackages.eslint
          ];
          shellHook = ''
            echo "📦 TypeScript dev shell ready (Node.js 22, TypeScript, ESLint)."
            echo "Tip: run 'npx tsc --init' in a project to bootstrap TypeScript config."
          '';
        };
      };
    };
}
