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
    # nixos-hardware: pre-built hardware modules for specific machines.
    # The correct module is selected at deploy time via mySystem.hardware.nixosHardwareModule
    # in nix/hosts/<hostname>/facts.nix (written by lib/hardware-detect.sh).
    nixos-hardware.url = "github:NixOS/nixos-hardware";
    disko.url = "github:nix-community/disko";
    lanzaboote.url = "github:nix-community/lanzaboote";
    #nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";
    nix-flatpak = {
      url = "github:gmodena/nix-flatpak";
    };
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

  outputs = { self, nixpkgs, home-manager, nixos-hardware, disko, lanzaboote, nix-flatpak, sops-nix, nixAiTools, nix-vscode-extensions, ... }:
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
      nixosConfigurations."HOSTNAME_PLACEHOLDER" =
        let
          # Load per-host hardware facts (written by lib/hardware-detect.sh at Phase 1).
          # facts.nix sets mySystem.hardware.{cpuVendor, gpuVendor, storageType, ...}
          # which drives all hardware-conditional modules below.
          hostFacts = (import ./nix/hosts/HOSTNAME_PLACEHOLDER/facts.nix { }).mySystem;
          hwModuleName = hostFacts.hardware.nixosHardwareModule or null;
          hwModuleExists =
            hwModuleName != null
            && builtins.hasAttr hwModuleName nixos-hardware.nixosModules;
          wantsDisko = (hostFacts.disk.layout or "none") != "none";
          hasDiskoModule = disko ? nixosModules && disko.nixosModules ? disko;
          wantsSecureboot = hostFacts.secureboot.enable or false;
          hasLanzabooteModule = lanzaboote ? nixosModules && lanzaboote.nixosModules ? lanzaboote;
        in
        nixpkgs.lib.nixosSystem {
          inherit system;
          specialArgs = {
            inherit nixAiToolsPackages;
          };
          modules = [
            # Declarative options schema (mySystem.* namespace)
            ./nix/modules/core/options.nix
            # Per-host hardware facts (sets mySystem.hardware.* values)
            ./nix/hosts/HOSTNAME_PLACEHOLDER/facts.nix
            # Hardware-conditional modules (CPU, GPU, storage, RAM tuning, mobile)
            # Each module gates itself on mySystem.hardware.* — safe to import unconditionally.
            ./nix/modules/hardware/default.nix
            ./nix/modules/disk/default.nix
            ./nix/modules/secureboot.nix
          ]
          # nixos-hardware: import the machine-specific upstream module if detected.
          # Provides additional kernel/firmware tuning specific to the exact hardware model.
          ++ lib.optionals hwModuleExists [
            nixos-hardware.nixosModules.${hwModuleName}
          ]
          ++ lib.optionals (wantsDisko && hasDiskoModule) [
            disko.nixosModules.disko
          ]
          ++ lib.optionals (wantsSecureboot && hasLanzabooteModule) [
            lanzaboote.nixosModules.lanzaboote
          ]
          ++ [
            sops-nix.nixosModules.sops
            ./configuration.nix
            # Note: home-manager is used standalone (via homeConfigurations below)
            # Not as a NixOS module to avoid dependency issues during nixos-rebuild
          ];
          warnings =
            lib.optional (hwModuleName != null && !hwModuleExists)
              "nixos-hardware module '${hwModuleName}' requested in facts.nix but not found in input."
            ++ lib.optional (wantsDisko && !hasDiskoModule)
              "Disk layout '${hostFacts.disk.layout or "none"}' requested but disko module export is unavailable."
            ++ lib.optional (wantsSecureboot && !hasLanzabooteModule)
              "Secure boot requested but lanzaboote module export is unavailable.";
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
        default = devPkgs.mkShell {
          packages = with devPkgs; [
            statix
            deadnix
            alejandra
          ];
          shellHook = ''
            echo "Nix lint shell ready (statix, deadnix, alejandra)."
          '';
        };

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
            # ts-node removed - Node.js 22.6.0+ has built-in TypeScript support
            # Use: node --experimental-strip-types script.ts
            nodePackages.typescript-language-server
            nodePackages.eslint
          ];
          shellHook = ''
            echo "📦 TypeScript dev shell ready (Node.js 22, TypeScript, ESLint)."
            echo "ℹ️  Node.js 22+ has built-in TypeScript support:"
            echo "   node --experimental-strip-types script.ts"
            echo "Tip: run 'npx tsc --init' in a project to bootstrap TypeScript config."
          '';
        };
      };
    };
}
