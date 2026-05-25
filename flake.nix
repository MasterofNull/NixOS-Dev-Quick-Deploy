{
  description = "Declarative NixOS AI harness with autonomous optimization, host-local inference, and multi-agent coordination";

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
    # Phase 63.4: NixOS impermanence — declarative /persist state paths for AI stack.
    # Enabled per-host via mySystem.aiStack.impermanence.enable = true (default: false).
    # Requires a /persist filesystem to be mounted before nixos-rebuild activates.
    impermanence = {
      url = "github:nix-community/impermanence";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixified-ai = {
      url = "github:nixified-ai/flake";
    };
    nixos-rocm = {
      url = "github:nixos-rocm/nixos-rocm";
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

  outputs = inputs @ {
    self,
    nixpkgs,
    home-manager,
    ...
  }: let
    lib = nixpkgs.lib;
    hasUnstableInput = builtins.hasAttr "nixpkgs-unstable" inputs;
    nixpkgsForTrack = track:
      if track == "unstable" && hasUnstableInput
      then inputs."nixpkgs-unstable"
      else nixpkgs;
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
    devSystems = ["x86_64-linux" "aarch64-linux"];
    profiles = ["ai-dev" "gaming" "minimal"];
    mkPkgs = nixpkgsInput: system':
      import nixpkgsInput {
        system = system';
        config.allowUnfree = true;
      };
    hostPath = hostName: ./. + "/nix/hosts/${hostName}";
    factsPath = hostName: hostPath hostName + "/facts.nix";
    hostDefaultPath = hostName: hostPath hostName + "/default.nix";
    hostHardwarePath = hostName: hostPath hostName + "/hardware-configuration.nix";
    hostDeployOptionsPath = hostName: hostPath hostName + "/deploy-options.nix";
    hostDeployOptionsLocalPath = hostName: hostPath hostName + "/deploy-options.local.nix";
    hostHomePath = hostName: hostPath hostName + "/home.nix";
    hostHomeDeployOptionsPath = hostName: hostPath hostName + "/home-deploy-options.nix";

    hostEntries = builtins.readDir ./nix/hosts;
    hostDirs = lib.sort builtins.lessThan (
      builtins.filter
      (name: hostEntries.${name} == "directory" && builtins.pathExists (hostDefaultPath name))
      (builtins.attrNames hostEntries)
    );

    resolveHostFacts = hostName:
      if builtins.pathExists (factsPath hostName)
      then let imported = import (factsPath hostName) {}; in imported.mySystem or {}
      else {};

    resolveHostSystem = hostName: let facts = resolveHostFacts hostName; in facts.system or defaultSystem;

    resolveHostUser = hostName: let facts = resolveHostFacts hostName; in facts.primaryUser or "nixos";

    mkHost = {
      hostName,
      profile,
    }: let
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
          # Layering contract:
          # 1. facts.nix: discovered machine facts only
          # 2. core/roles/services/profiles: reusable policy
          # 3. host-classes/: reusable machine-family overlays
          # 4. nix/hosts/<host>/*.nix: host-only exceptions
          ({lib, ...}: {
            mySystem.nixpkgsTrack = lib.mkDefault nixpkgsTrack;
            nixpkgs.pkgs = mkPkgs selectedNixpkgs system';
            warnings =
              lib.optional (nixpkgsTrack == "unstable" && !hasUnstableInput)
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
          ./nix/modules/core/custom-kernel.nix
          ./nix/modules/roles/default.nix
          ./nix/modules/services/default.nix
          ./nix/modules/profiles/minimal.nix
          ./nix/modules/profiles/ai-dev.nix
          ./nix/modules/host-classes/p14s-amd-ai-workstation.nix
          ./nix/modules/profiles/gaming.nix
          ./nix/modules/hardware/default.nix
          ./nix/modules/disk/default.nix
          ./nix/modules/secureboot.nix
          inputs.sops-nix.nixosModules.sops
          ({
            lib,
            config,
            ...
          }: let
            moduleName = requestedNixosHardwareModule;
            hasNixosHardwareInput = builtins.hasAttr "nixos-hardware" inputs;
            nixosHardwareModules =
              if hasNixosHardwareInput
              then inputs."nixos-hardware".nixosModules
              else {};
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
            hasImpermanenceInput = builtins.hasAttr "impermanence" inputs;
            hasImpermanenceModule =
              hasImpermanenceInput
              && inputs.impermanence ? nixosModules
              && inputs.impermanence.nixosModules ? impermanence;
            wantsDisko = (config.mySystem.disk.layout or "none") != "none";
            wantsSecureboot = config.mySystem.secureboot.enable or false;
          in {
            # Import optional upstream modules unconditionally when available.
            # Their effects are gated by local modules/options (mkIf), which avoids
            # recursive module argument evaluation from config-driven imports.
            imports =
              lib.optional moduleExists nixosHardwareModules.${moduleName}
              ++ lib.optional hasDiskoModule inputs.disko.nixosModules.disko
              ++ lib.optional hasLanzabooteModule inputs.lanzaboote.nixosModules.lanzaboote
              ++ lib.optional hasImpermanenceModule inputs.impermanence.nixosModules.impermanence;
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
          ({lib, ...}: {
            mySystem.hostName = lib.mkDefault hostName;
            mySystem.profile = lib.mkForce profile;
          })
          # Pass flake self as flakeRepoPath for pure evaluation access to repo files
          ({...}: {
            mySystem.mcpServers.flakeRepoPath = self;
          })
          ({lib, ...}: {
            assertions =
              [
                {
                  assertion = hasHostFacts;
                  message = "Host '${hostName}' is missing '${toString (factsPath hostName)}'. Run scripts/governance/discover-system-facts.sh before flake evaluation/deploy so hardware/kernel settings are generated from the local machine.";
                }
              ]
              ++ lib.optional (!hasHostHardwareConfig && (hostFacts.disk.layout or "none") == "none") {
                assertion = false;
                message = "Host '${hostName}' uses disk layout 'none' but '${toString (hostHardwarePath hostName)}' is missing. Add host hardware-configuration.nix or set mySystem.disk.layout to a disko layout.";
              };
          })
          (hostDefaultPath hostName)
          ({lib, ...}: {
            imports = lib.optionals (builtins.pathExists (hostDeployOptionsPath hostName)) [(hostDeployOptionsPath hostName)];
          })
          ({lib, ...}: {
            imports = lib.optionals (builtins.pathExists (hostDeployOptionsLocalPath hostName)) [(hostDeployOptionsLocalPath hostName)];
          })
        ];
      };

    mkHostConfigs =
      lib.foldl'
      (acc: hostName: let
        perProfile = lib.listToAttrs (map
          (profile: {
            name = "${hostName}-${profile}";
            value = mkHost {inherit hostName profile;};
          })
          profiles);
      in
        acc // perProfile)
      {}
      hostDirs;

    mkHostHomeConfig = hostName: let
      hostSystem = resolveHostSystem hostName;
      hostFacts = resolveHostFacts hostName;
      nixpkgsTrack = hostFacts.nixpkgsTrack or "stable";
      selectedNixpkgs = nixpkgsForTrack nixpkgsTrack;
      hostUser = resolveHostUser hostName;
      hostModules =
        # Home layering mirrors the system side:
        # 1. nix/home/*.nix: shared Home Manager defaults
        # 2. nix/hosts/<host>/home.nix: host-specific HM behavior
        [./nix/home/base.nix ./nix/home/deploy-common.nix]
        ++ lib.optionals (builtins.pathExists (hostHomePath hostName)) [(hostHomePath hostName)]
        ++ lib.optionals (builtins.pathExists (hostHomeDeployOptionsPath hostName)) [(hostHomeDeployOptionsPath hostName)]
        ++ [
          ({lib, ...}: {
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
      (acc: hostName: let
        hostUser = resolveHostUser hostName;
        hostScopedName = "${hostUser}-${hostName}";
        cfg = mkHostHomeConfig hostName;
      in
        acc
        // {"${hostScopedName}" = cfg;}
        // (
          if builtins.hasAttr hostUser acc
          then {}
          else {"${hostUser}" = cfg;}
        ))
      {}
      hostDirs;
  in {
    nixosConfigurations = mkHostConfigs;
    homeConfigurations = mkHomeConfigs;
    devShells = lib.genAttrs devSystems (system': let
      pkgs' = import nixpkgs {
        system = system';
        config.allowUnfree = true;
        overlays = [(import ./nix/lib/overlays/osint-tools.nix)];
      };
    in {
      default = pkgs'.mkShell {
        packages = with pkgs'; [
          statix
          deadnix
          alejandra
        ];
      };
      bitnet-benchmark = pkgs'.mkShell {
        packages = with pkgs'; [
          python312
          cmake
          clang
          git
          gnumake
          pkg-config
          zlib
        ];
        shellHook = ''
          export BITNET_BENCHMARK_SHELL=1
          export BITNET_PYTHON_BIN="${pkgs'.python312}/bin/python3.12"
          export LD_LIBRARY_PATH="${pkgs'.lib.makeLibraryPath [pkgs'.zlib pkgs'.stdenv.cc.cc.lib]}:''${LD_LIBRARY_PATH:-}"
          echo "BitNet benchmark shell ready: python3.12, cmake, clang, git, make, pkg-config, zlib"
        '';
      };

      # ── Domain dev shells (Phase 58A capability expansion) ──────────────

      # security-systems domain: static analysis + vulnerability scanning
      security = pkgs'.mkShell {
        packages = with pkgs'; [
          semgrep
          trivy
          shellcheck
          cppcheck
          (python3.withPackages (ps:
            with ps; [
              bandit
              safety
            ]))
        ];
        shellHook = ''
          export SECURITY_DOMAIN_SHELL=1
          export AIDB_NAMESPACE=security-findings
          echo "security-systems shell: semgrep, trivy, shellcheck, cppcheck, bandit, safety"
          echo "AIDB namespace: security-findings | Route: remote-reasoning (policy) / local-tool-calling (scans)"
        '';
      };

      # systems-software domain: Nix static analysis + shell tooling
      # Note: statix/deadnix/alejandra are also in default shell for convenience
      systems = pkgs'.mkShell {
        packages = with pkgs'; [
          statix
          deadnix
          alejandra
          shellcheck
          nix-tree
          nix-diff
          nixpkgs-fmt
        ];
        shellHook = ''
          export SYSTEMS_DOMAIN_SHELL=1
          export AIDB_NAMESPACE=nix-systems-patterns
          echo "systems-software shell: statix, deadnix, alejandra, shellcheck, nix-tree, nix-diff, nixpkgs-fmt"
          echo "AIDB namespace: nix-systems-patterns | Route: local-tool-calling"
          echo "Port SSOT: nix/modules/core/options.nix — never hardcode ports"
        '';
      };

      # embedded-hardware domain: HDL, simulation, cross-compile, debug
      embedded = pkgs'.mkShell {
        packages = with pkgs'; [
          verilator
          ghdl-llvm
          yosys
          openocd
          gcc-arm-embedded
          dtc
          qemu
          gdb
          minicom
        ];
        shellHook = ''
          export EMBEDDED_DOMAIN_SHELL=1
          export AIDB_NAMESPACE=embedded-hardware-patterns
          echo "embedded-hardware shell: verilator, ghdl-llvm, yosys, openocd, gcc-arm-embedded, dtc, qemu, gdb, minicom"
          echo "AIDB namespace: embedded-hardware-patterns"
          echo "SAFETY: firmware flash/JTAG ops require explicit user confirmation before execution"
        '';
      };

      # osint-systems domain: reconnaissance + behavioral profiling
      # do not permit insecure PyPDF2 evaluation paths into system profile
      osint = pkgs'.mkShell {
        packages = with pkgs'; [
          (pkgs'.callPackage ./nix/pkgs/maigret.nix {})
          (pkgs'.callPackage ./nix/pkgs/mosaic.nix {})
          holehe
          sherlock
          (writeShellScriptBin "bbot" ''
            echo "BBOT is currently being provisioned. Use the OSINT MCP server's bounded tools for now." >&2
            exit 1
          '')
          # Support tools
          exiftool
          mat2
          theharvester
          h8mail
        ];
        shellHook = ''
          export NIXPKGS_ALLOW_INSECURE=1 # Temporary: allows insecure pypdf2 for maigret
          export OSINT_DOMAIN_SHELL=1
          export AIDB_NAMESPACE=osint-intelligence
          echo "osint-systems shell: maigret, mosaic-osint, sherlock, holehe, bbot-placeholder, exiftool, mat2, theharvester, h8mail"
          echo "AIDB namespace: osint-intelligence | Route: remote-reasoning"
        '';
      };

      # mobile-web domain: Flutter, web tooling, accessibility + security audits
      # Note: lighthouse is installed via npm in shellHook (removed from nodePackages in nixpkgs 25.11)
      mobile-web = pkgs'.mkShell {
        packages = with pkgs'; [
          flutter
          android-tools
          nodejs_22
          chromium
          playwright-driver
        ];
        shellHook = ''
          export MOBILE_WEB_DOMAIN_SHELL=1
          export AIDB_NAMESPACE=mobile-web-patterns
          export CHROME_EXECUTABLE="${pkgs'.chromium}/bin/chromium"
          export PLAYWRIGHT_BROWSERS_PATH="${pkgs'.playwright-driver.browsers}"
          # lighthouse removed from nixpkgs nodePackages in 25.11; install on demand:
          if ! command -v lighthouse &>/dev/null; then
            echo "  hint: npm install -g lighthouse  (to add Lighthouse audit)"
          fi
          echo "mobile-web shell: flutter, android-tools, nodejs_22, chromium, playwright"
          echo "AIDB namespace: mobile-web-patterns | iOS builds NOT supported (no macOS/Xcode)"
        '';
      };

      # scientific-research domain: reproducible pipelines, notebooks, reports
      scientific = pkgs'.mkShell {
        packages = with pkgs'; [
          (python3.withPackages (ps:
            with ps; [
              numpy
              scipy
              matplotlib
              pandas
              jupyterlab
              snakemake
              biopython
            ]))
          pandoc
          texlive.combined.scheme-small
          R
        ];
        shellHook = ''
          export SCIENTIFIC_DOMAIN_SHELL=1
          export AIDB_NAMESPACE=scientific-research-patterns
          echo "scientific-research shell: numpy/scipy/matplotlib/pandas/jupyterlab/snakemake, pandoc, texlive, R"
          echo "AIDB namespace: scientific-research-patterns"
          echo "REPRODUCIBILITY: always set random seeds; pin package versions; record data provenance"
        '';
      };

      # gis-systems domain: GDAL/OGR, spatial analysis, CRS validation
      # Note: postgis is a PostgreSQL server extension, not a standalone CLI tool.
      # For local dev spatial queries without a server, use spatialite-tools instead.
      # PostGIS is available in nixpkgs as postgresqlPackages.postgis for service config.
      gis = pkgs'.mkShell {
        packages = with pkgs'; [
          gdal
          proj
          (python3.withPackages (ps:
            with ps; [
              geopandas
              rasterio
              shapely
              pyproj
              fiona
            ]))
          qgis
          spatialite-tools
        ];
        shellHook = ''
          export GIS_DOMAIN_SHELL=1
          export AIDB_NAMESPACE=gis-systems-patterns
          export CANONICAL_CRS="EPSG:4326"
          echo "gis-systems shell: gdal, proj, geopandas/rasterio/shapely, qgis, spatialite-tools"
          echo "AIDB namespace: gis-systems-patterns | Canonical CRS: EPSG:4326 (WGS84)"
          echo "CRS DISCIPLINE: always validate CRS with 'ogrinfo -al -so <file>' before any spatial operation"
        '';
      };

      # data-eng domain: database, data processing, telemetry
      data-eng = pkgs'.mkShell {
        packages = with pkgs'; [
          postgresql
          redis
          duckdb
          (python3.withPackages (ps:
            with ps; [
              pandas
              sqlalchemy
              psycopg2
              redis
              pyarrow
            ]))
        ];
        shellHook = ''
          export DATA_ENG_DOMAIN_SHELL=1
          export AIDB_NAMESPACE=data-engineering-patterns
          echo "data-eng shell: postgres, redis, duckdb, pandas, sqlalchemy"
        '';
      };

      # qa-auto domain: automated testing, performance, accessibility
      qa-auto = pkgs'.mkShell {
        packages = with pkgs'; [
          playwright-driver
          k6
          (python3.withPackages (ps:
            with ps; [
              pytest
              pytest-asyncio
              pytest-xdist
              locust
            ]))
        ];
        shellHook = ''
          export QA_AUTO_DOMAIN_SHELL=1
          export AIDB_NAMESPACE=qa-automation-patterns
          export PLAYWRIGHT_BROWSERS_PATH="${pkgs'.playwright-driver.browsers}"
          echo "qa-auto shell: playwright, k6, pytest, locust"
        '';
      };

      # frontend domain: modern web development, UI/UX, visualization
      frontend = pkgs'.mkShell {
        packages = with pkgs'; [
          bun
          nodejs_22
          typescript
        ];
        shellHook = ''
          export FRONTEND_DOMAIN_SHELL=1
          export AIDB_NAMESPACE=frontend-uiux-patterns
          echo "frontend shell: bun, nodejs, typescript, tailwind"
        '';
      };

      # ml-ai domain: model training, inference optimization, ROCm/CUDA
      ml-ai = pkgs'.mkShell {
        packages = with pkgs'; [
          (python3.withPackages (ps:
            with ps; [
              torch
              transformers
              datasets
              huggingface-hub
            ]))
          # ROCm tools for AMD hardware
          rocmPackages.rocminfo
          rocmPackages.rocm-smi
        ];
        shellHook = ''
          export ML_AI_DOMAIN_SHELL=1
          export AIDB_NAMESPACE=ml-ai-patterns
          echo "ml-ai shell: pytorch, transformers, huggingface, rocm-smi"
        '';
      };

      # cloud-ops domain: infrastructure, orchestration, cloud APIs
      cloud-ops = pkgs'.mkShell {
        packages = with pkgs'; [
          terraform
          kubectl
          kubernetes-helm
          ansible
          awscli2
          google-cloud-sdk
        ];
        shellHook = ''
          export CLOUD_OPS_DOMAIN_SHELL=1
          export AIDB_NAMESPACE=cloud-operations-patterns
          echo "cloud-ops shell: terraform, kubectl, helm, ansible, aws/gcloud"
        '';
      };

      # ── Unified full-stack shell: all 11 domains in one env ──────────────
      # Use this when you want all domain tools in PATH without manually
      # entering per-domain shells. The harness (hybrid-coordinator) reads
      # DOMAIN_SHELL=full and auto-selects tools based on intent classification.
      # Usage: nix develop .#full
      full = pkgs'.mkShell {
        packages = with pkgs'; [
          # Nix / systems
          statix
          deadnix
          alejandra
          shellcheck
          nix-tree
          nix-diff
          nixpkgs-fmt
          # Security
          semgrep
          trivy
          cppcheck
          # Data / ML / Research
          postgresql
          redis
          duckdb
          (python3.withPackages (ps:
            with ps; [
              # Security
              bandit
              safety
              # Data / ML
              pandas
              sqlalchemy
              psycopg2
              redis
              pyarrow
              torch
              transformers
              datasets
              huggingface-hub
              # Scientific + GIS Python stack
              numpy
              scipy
              matplotlib
              jupyterlab
              snakemake
              biopython
              geopandas
              rasterio
              shapely
              pyproj
              fiona
              # QA
              pytest
              pytest-asyncio
              pytest-xdist
              locust
            ]))
          # Embedded / hardware
          verilator
          ghdl-llvm
          yosys
          openocd
          gcc-arm-embedded
          dtc
          qemu
          gdb
          minicom
          # Mobile / web / frontend
          flutter
          android-tools
          nodejs_22
          chromium
          playwright-driver
          bun
          typescript
          # Scientific / docs
          pandoc
          texlive.combined.scheme-small
          R
          # GIS / spatial
          gdal
          proj
          qgis
          spatialite-tools
          # Cloud / Ops
          terraform
          kubectl
          kubernetes-helm
          ansible
          awscli2
          google-cloud-sdk
          # ROCm
          rocmPackages.rocminfo
          rocmPackages.rocm-smi
          # Phase 66.1: Wasmtime — WASM sandbox tier (L2) below nsjail cost
          # Staged here (devShells.full only); not in hybridPython coordinator env
          wasmtime
        ];
        shellHook = ''
          export DOMAIN_SHELL=full
          export FULL_STACK_SHELL=1
          # Per-domain namespace hints (harness reads these to route to AIDB)
          export DOMAIN_NAMESPACES="security-findings,nix-systems-patterns,embedded-hardware-patterns,mobile-web-patterns,scientific-research-patterns,gis-systems-patterns,data-engineering-patterns,qa-automation-patterns,frontend-uiux-patterns,ml-ai-patterns,cloud-operations-patterns"
          # Mobile / Web
          export CHROME_EXECUTABLE="${pkgs'.chromium}/bin/chromium"
          export PLAYWRIGHT_BROWSERS_PATH="${pkgs'.playwright-driver.browsers}"
          # GIS
          export CANONICAL_CRS="EPSG:4326"
          echo "=== AI Harness Full-Stack Domain Shell ==="
          echo "All 11 domains active: security | systems | embedded | mobile-web | scientific | gis | data-eng | qa-auto | frontend | ml-ai | cloud-ops"
          echo "Intent routing: hybrid-coordinator classifies task → selects AIDB namespace + profile"
          echo "AIDB namespaces: \$DOMAIN_NAMESPACES"
          echo "Embedded safety: firmware flash/JTAG requires user confirmation"
          echo "GIS CRS: always validate with 'ogrinfo -al -so <file>' before transforms"
          echo "Scientific: always set random seeds; record data provenance"
          if ! command -v lighthouse &>/dev/null; then
            echo "Lighthouse: npm install -g lighthouse (web accessibility auditing)"
          fi
          echo "==========================================="
        '';
      };
    });
  };
}
