{
  description = "Flake-first declarative scaffold for NixOS Quick Deploy";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager = {
      url = "github:nix-community/home-manager/release-25.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixos-hardware = {
      url = "github:NixOS/nixos-hardware";
    };
    disko = {
      url = "github:nix-community/disko";
    };
    lanzaboote = {
      url = "github:nix-community/lanzaboote";
    };
    sops-nix = {
      url = "github:Mic92/sops-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # Apple Silicon (Asahi Linux) — only needed for Apple M-series hosts.
    # When cpuVendor = "apple", set mySystem.hardware.nixosHardwareModule = "apple-m1"
    # (or apple-m2) in facts.nix to pull in the Asahi kernel + Mesa overlay via
    # nixos-hardware.  Alternatively, use the community nixos-apple-silicon flake:
    #   nixos-apple-silicon.url = "github:tpwrules/nixos-apple-silicon";
    # and add its module manually in the host's default.nix.
    # The placeholder below is commented out to avoid unnecessary fetches on
    # non-Apple hardware; uncomment and add to outputs.inputs when needed.
    # nixos-apple-silicon = {
    #   url = "github:tpwrules/nixos-apple-silicon";
    #   inputs.nixpkgs.follows = "nixpkgs";
    # };
  };

  outputs = inputs@{ self, nixpkgs, home-manager, ... }:
    let
      lib = nixpkgs.lib;
      hasUnstableInput = builtins.hasAttr "nixpkgs-unstable" inputs;
      nixpkgsForTrack = track:
        if track == "unstable" && hasUnstableInput then
          inputs."nixpkgs-unstable"
        else
          nixpkgs;
      # nixosConfigurations supports any system declared in a host's facts.nix.
      # Supported system values for mySystem.system:
      #   "x86_64-linux"   — AMD/Intel desktops, laptops, servers
      #   "aarch64-linux"  — ARM64 SBCs (Qualcomm ThinkPad X13s, Raspberry Pi 4/5,
      #                      Rockchip boards) and Apple Silicon (via Asahi Linux)
      #   "riscv64-linux"  — RISC-V boards (SiFive HiFive Unmatched, StarFive VisionFive 2)
      # The system is read from nix/hosts/<host>/facts.nix → mySystem.system.
      # Defaults to defaultSystem when facts.nix is absent.
      defaultSystem = "x86_64-linux";
      # devShell systems: build the developer shell for common cross-compilation hosts.
      devSystems = [ "x86_64-linux" "aarch64-linux" ];
      profiles = [ "ai-dev" "gaming" "minimal" ];
      mkPkgs = nixpkgsInput: system': import nixpkgsInput {
        system = system';
        config.allowUnfree = true;
      };
      defaultPkgs = mkPkgs nixpkgs defaultSystem;

      hostPath = hostName: ./. + "/nix/hosts/${hostName}";
      factsPath = hostName: hostPath hostName + "/facts.nix";
      hostDefaultPath = hostName: hostPath hostName + "/default.nix";
      hostHardwarePath = hostName: hostPath hostName + "/hardware-configuration.nix";
      hostDeployOptionsPath = hostName: hostPath hostName + "/deploy-options.nix";
      hostDeployOptionsLocalPath = hostName: hostPath hostName + "/deploy-options.local.nix";
      hostHomePath = hostName: hostPath hostName + "/home.nix";
      hostHomeDeployOptionsPath = hostName: hostPath hostName + "/home-deploy-options.nix";

      hostEntries = builtins.readDir ./nix/hosts;
      hostDirs =
        lib.sort builtins.lessThan (
          builtins.filter
            (name: hostEntries.${name} == "directory" && builtins.pathExists (hostDefaultPath name))
            (builtins.attrNames hostEntries)
        );

      resolveHostFacts = hostName:
        if builtins.pathExists (factsPath hostName) then
          let imported = import (factsPath hostName) { }; in imported.mySystem or { }
        else
          { };

      resolveHostSystem = hostName:
        let facts = resolveHostFacts hostName; in facts.system or defaultSystem;

      resolveHostUser = hostName:
        let facts = resolveHostFacts hostName; in facts.primaryUser or "nixos";

      mkHost = { hostName, profile }:
        let
          system' = resolveHostSystem hostName;
          hostFacts = resolveHostFacts hostName;
          nixpkgsTrack = hostFacts.nixpkgsTrack or "stable";
          selectedNixpkgs = nixpkgsForTrack nixpkgsTrack;
          hasHostFacts = builtins.pathExists (factsPath hostName);
          requestedNixosHardwareModule = hostFacts.hardware.nixosHardwareModule or null;
          hasHostHardwareConfig = builtins.pathExists (hostHardwarePath hostName);
        in
        lib.nixosSystem {
          system = system';
          modules = [
            ({ lib, ... }: {
              mySystem.nixpkgsTrack = lib.mkDefault nixpkgsTrack;
              nixpkgs.pkgs = mkPkgs selectedNixpkgs system';
              warnings = lib.optional (nixpkgsTrack == "unstable" && !hasUnstableInput)
                "Host '${hostName}' requested mySystem.nixpkgsTrack=unstable, but flake input 'nixpkgs-unstable' is unavailable; falling back to stable nixpkgs.";
            })
            ./nix/modules/core/options.nix
            ./nix/modules/core/base.nix
            ./nix/modules/core/hospital-classified.nix
            ./nix/modules/core/network.nix
            ./nix/modules/core/logging.nix
            ./nix/modules/core/localhost-isolation.nix
            ./nix/modules/core/users.nix
            ./nix/modules/core/secrets.nix
            ./nix/modules/core/guardrail-alerts.nix
            ./nix/modules/core/fs-integrity-monitor.nix
            ./nix/modules/core/disk-health-monitor.nix
            ./nix/modules/roles/default.nix
            ./nix/modules/services/default.nix
            ./nix/modules/profiles/minimal.nix
            ./nix/modules/profiles/ai-dev.nix
            ./nix/modules/profiles/gaming.nix
            ./nix/modules/hardware/default.nix
            ./nix/modules/disk/default.nix
            ./nix/modules/secureboot.nix
            inputs.sops-nix.nixosModules.sops
            ({ lib, config, ... }:
              let
                moduleName = requestedNixosHardwareModule;
                hasNixosHardwareInput = builtins.hasAttr "nixos-hardware" inputs;
                nixosHardwareModules =
                  if hasNixosHardwareInput then inputs."nixos-hardware".nixosModules else { };
                moduleExists =
                  moduleName != null && builtins.hasAttr moduleName nixosHardwareModules;
                hasDiskoInput = builtins.hasAttr "disko" inputs;
                hasDiskoModule =
                  hasDiskoInput
                  && inputs.disko ? nixosModules
                  && inputs.disko.nixosModules ? disko;
                hasLanzabooteInput = builtins.hasAttr "lanzaboote" inputs;
                hasLanzabooteModule =
                  hasLanzabooteInput
                  && inputs.lanzaboote ? nixosModules
                  && inputs.lanzaboote.nixosModules ? lanzaboote;
                wantsDisko = (config.mySystem.disk.layout or "none") != "none";
                wantsSecureboot = config.mySystem.secureboot.enable or false;
              in
              {
                # Import optional upstream modules unconditionally when available.
                # Their effects are gated by local modules/options (mkIf), which avoids
                # recursive module argument evaluation from config-driven imports.
                imports =
                  lib.optional moduleExists nixosHardwareModules.${moduleName}
                  ++ lib.optional hasDiskoModule inputs.disko.nixosModules.disko
                  ++ lib.optional hasLanzabooteModule inputs.lanzaboote.nixosModules.lanzaboote;
                warnings =
                  lib.optional (moduleName != null && !hasNixosHardwareInput)
                    "nixos-hardware module '${moduleName}' requested but flake input 'nixos-hardware' is not configured."
                  ++ lib.optional (moduleName != null && hasNixosHardwareInput && !moduleExists)
                    "nixos-hardware module '${moduleName}' not found in flake input."
                  ++ lib.optional (wantsDisko && !hasDiskoInput)
                    "Disk layout '${config.mySystem.disk.layout}' requested but flake input 'disko' is not configured."
                  ++ lib.optional (wantsDisko && hasDiskoInput && !hasDiskoModule)
                    "Disk layout '${config.mySystem.disk.layout}' requested but disko module export is unavailable."
                  ++ lib.optional (wantsSecureboot && !hasLanzabooteInput)
                    "Secure boot requested but flake input 'lanzaboote' is not configured."
                  ++ lib.optional (wantsSecureboot && hasLanzabooteInput && !hasLanzabooteModule)
                    "Secure boot requested but lanzaboote module export is unavailable.";
              })
            ({ lib, ... }: {
              mySystem.hostName = lib.mkDefault hostName;
              mySystem.profile = lib.mkForce profile;
            })
            ({ lib, ... }: {
              assertions =
                [
                  {
                    assertion = hasHostFacts;
                    message = "Host '${hostName}' is missing '${toString (factsPath hostName)}'. Run scripts/discover-system-facts.sh before flake evaluation/deploy so hardware/kernel settings are generated from the local machine.";
                  }
                ]
                ++ lib.optional (!hasHostHardwareConfig && (hostFacts.disk.layout or "none") == "none") {
                  assertion = false;
                  message = "Host '${hostName}' uses disk layout 'none' but '${toString (hostHardwarePath hostName)}' is missing. Add host hardware-configuration.nix or set mySystem.disk.layout to a disko layout.";
                };
            })
            (hostDefaultPath hostName)
            ({ lib, ... }: {
              imports = lib.optionals (builtins.pathExists (hostDeployOptionsPath hostName)) [ (hostDeployOptionsPath hostName) ];
            })
            ({ lib, ... }: {
              imports = lib.optionals (builtins.pathExists (hostDeployOptionsLocalPath hostName)) [ (hostDeployOptionsLocalPath hostName) ];
            })
          ];
        };

      mkHostConfigs =
        lib.foldl'
          (acc: hostName:
            let
              perProfile = lib.listToAttrs (map
                (profile: {
                  name = "${hostName}-${profile}";
                  value = mkHost { inherit hostName profile; };
                })
                profiles);
            in
            acc // perProfile)
          { }
          hostDirs;

      mkHostHomeConfig = hostName:
        let
          hostSystem = resolveHostSystem hostName;
          hostFacts = resolveHostFacts hostName;
          nixpkgsTrack = hostFacts.nixpkgsTrack or "stable";
          selectedNixpkgs = nixpkgsForTrack nixpkgsTrack;
          hostUser = resolveHostUser hostName;
          hostModules =
            [ ./nix/home/base.nix ]
            ++ lib.optionals (builtins.pathExists (hostHomePath hostName)) [ (hostHomePath hostName) ]
            ++ lib.optionals (builtins.pathExists (hostHomeDeployOptionsPath hostName)) [ (hostHomeDeployOptionsPath hostName) ]
            ++ [
              ({ lib, ... }: {
                home.username = lib.mkDefault hostUser;
                home.homeDirectory = lib.mkDefault "/home/${hostUser}";
              })
            ];
        in
        home-manager.lib.homeManagerConfiguration {
          pkgs = mkPkgs selectedNixpkgs hostSystem;
          modules = hostModules;
        };

      mkHomeConfigs =
        lib.foldl'
          (acc: hostName:
            let
              hostUser = resolveHostUser hostName;
              hostScopedName = "${hostUser}-${hostName}";
              cfg = mkHostHomeConfig hostName;
            in
            acc
            // { "${hostScopedName}" = cfg; }
            // (if builtins.hasAttr hostUser acc then { } else { "${hostUser}" = cfg; }))
          { }
          hostDirs;
    in
    {
      nixosConfigurations = mkHostConfigs;
      homeConfigurations = mkHomeConfigs;
      devShells = lib.genAttrs devSystems (system':
        let pkgs' = mkPkgs nixpkgs system'; in {
          default = pkgs'.mkShell {
            packages = with pkgs'; [
              statix
              deadnix
              alejandra
            ];
          };
        });
    };
}
