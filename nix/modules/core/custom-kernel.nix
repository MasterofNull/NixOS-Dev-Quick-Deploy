# Custom Kernel Build Module
# Enables building custom Linux kernels with patches, Rust support, and hardening.
#
# Usage:
#   mySystem.kernel.customBuild = {
#     enable = true;
#     source = "stable";
#     version = "6.12.5";
#     patches = [{ name = "cve-fix"; url = "..."; sha256 = "..."; }];
#     rustSupport = true;
#   };
{ config, lib, pkgs, ... }:

let
  cfg = config.mySystem.kernel;
  customCfg = cfg.customBuild;
  hardeningCfg = cfg.hardening;

  # Kernel source fetching based on source type
  kernelSource = {
    "mainline" = {
      owner = "torvalds";
      repo = "linux";
      branch = "master";
    };
    "stable" = {
      owner = "gregkh";
      repo = "linux";
      branch = "linux-${customCfg.majorMinor}.y";
    };
    "longterm" = {
      owner = "gregkh";
      repo = "linux";
      branch = "linux-${customCfg.majorMinor}.y";
    };
  };

  # Parse major.minor from version string
  versionParts = lib.splitString "." customCfg.version;
  majorMinor = "${builtins.elemAt versionParts 0}.${builtins.elemAt versionParts 1}";

  # Fetch kernel tarball from kernel.org CDN
  kernelTarball = pkgs.fetchurl {
    url = "https://cdn.kernel.org/pub/linux/kernel/v${builtins.elemAt versionParts 0}.x/linux-${customCfg.version}.tar.xz";
    sha256 = customCfg.sourceSha256;
  };

  # Build custom patches list
  customPatches = map (patch: {
    name = patch.name;
    patch = if patch ? url then
      pkgs.fetchpatch {
        inherit (patch) name url sha256;
      }
    else if patch ? path then
      patch.path
    else
      throw "Patch ${patch.name} must have either 'url' or 'path' attribute";
  }) customCfg.patches;

  # Hardening kernel config fragments
  hardeningConfigs = {
    standard = ''
      # Standard hardening (KSPP baseline)
      CONFIG_RANDOMIZE_BASE=y
      CONFIG_RANDOMIZE_MEMORY=y
      CONFIG_GCC_PLUGIN_STRUCTLEAK=y
      CONFIG_GCC_PLUGIN_STACKLEAK=y
      CONFIG_STACKPROTECTOR=y
      CONFIG_STACKPROTECTOR_STRONG=y
      CONFIG_FORTIFY_SOURCE=y
      CONFIG_INIT_ON_ALLOC_DEFAULT_ON=y
      CONFIG_INIT_ON_FREE_DEFAULT_ON=y
      CONFIG_SLAB_FREELIST_RANDOM=y
      CONFIG_SLAB_FREELIST_HARDENED=y
      CONFIG_HARDENED_USERCOPY=y
      CONFIG_STATIC_USERMODEHELPER=y
    '';
    maximum = ''
      # Maximum hardening (standard + CFI + shadow stack)
      CONFIG_RANDOMIZE_BASE=y
      CONFIG_RANDOMIZE_MEMORY=y
      CONFIG_GCC_PLUGIN_STRUCTLEAK=y
      CONFIG_GCC_PLUGIN_STRUCTLEAK_BYREF_ALL=y
      CONFIG_GCC_PLUGIN_STACKLEAK=y
      CONFIG_STACKPROTECTOR=y
      CONFIG_STACKPROTECTOR_STRONG=y
      CONFIG_FORTIFY_SOURCE=y
      CONFIG_INIT_ON_ALLOC_DEFAULT_ON=y
      CONFIG_INIT_ON_FREE_DEFAULT_ON=y
      CONFIG_SLAB_FREELIST_RANDOM=y
      CONFIG_SLAB_FREELIST_HARDENED=y
      CONFIG_HARDENED_USERCOPY=y
      CONFIG_STATIC_USERMODEHELPER=y
      # CFI (Control Flow Integrity)
      CONFIG_CFI_CLANG=y
      CONFIG_CFI_PERMISSIVE=n
      # Shadow call stack (ARM64/x86_64)
      CONFIG_SHADOW_CALL_STACK=y
      # Page table isolation
      CONFIG_PAGE_TABLE_ISOLATION=y
      # Kernel lockdown
      CONFIG_SECURITY_LOCKDOWN_LSM=y
      CONFIG_SECURITY_LOCKDOWN_LSM_EARLY=y
      CONFIG_LOCK_DOWN_KERNEL_FORCE_INTEGRITY=y
      # Mitigations
      CONFIG_SPECULATION_MITIGATIONS=y
      CONFIG_RETPOLINE=y
    '';
  };

  # Rust kernel config fragment
  rustConfig = ''
    # Rust support for kernel modules
    CONFIG_RUST=y
    CONFIG_RUST_BUILD_ASSERT_ALLOW=y
    CONFIG_RUST_OVERFLOW_CHECKS=y
    # Rust samples (useful for development)
    CONFIG_SAMPLES_RUST=y
    CONFIG_SAMPLE_RUST_MINIMAL=m
    CONFIG_SAMPLE_RUST_PRINT=m
  '';

  # Build the custom kernel
  customKernel = pkgs.linuxManualConfig {
    inherit (pkgs) stdenv;
    version = customCfg.version;
    src = kernelTarball;

    # Base config from defconfig
    configfile = pkgs.runCommand "kernel-config" {
      nativeBuildInputs = [ pkgs.flex pkgs.bison pkgs.perl ];
    } ''
      cd ${kernelTarball}
      make defconfig
      cat .config > $out

      # Apply hardening fragment
      ${lib.optionalString hardeningCfg.enable ''
        cat >> $out << 'EOF'
      ${hardeningConfigs.${hardeningCfg.level}}
      EOF
      ''}

      # Apply Rust fragment
      ${lib.optionalString customCfg.rustSupport ''
        cat >> $out << 'EOF'
      ${rustConfig}
      EOF
      ''}

      # Apply custom config fragments
      ${lib.concatMapStrings (frag: ''
        cat >> $out << 'EOF'
      ${frag}
      EOF
      '') customCfg.configFragments}
    '';

    kernelPatches = customPatches ++ (lib.optionals hardeningCfg.enable [
      # Additional hardening patches
    ]);

    allowImportFromDerivation = true;
  };

  # Select kernel packages based on configuration
  selectedKernelPackages =
    if customCfg.enable then
      pkgs.linuxPackagesFor customKernel
    else if cfg.track == "latest-stable" && pkgs ? linuxPackages_latest then
      pkgs.linuxPackages_latest
    else
      pkgs.linuxPackages;

in
{
  options.mySystem.kernel = {
    customBuild = {
      enable = lib.mkEnableOption "custom kernel build from source";

      source = lib.mkOption {
        type = lib.types.enum [ "mainline" "stable" "longterm" "local" ];
        default = "stable";
        description = ''
          Kernel source to build from:
          - mainline: Linus Torvalds' tree (bleeding edge)
          - stable: Greg KH's stable tree (recommended)
          - longterm: LTS kernel branch
          - local: Use localSourcePath
        '';
      };

      version = lib.mkOption {
        type = lib.types.str;
        default = "6.12.5";
        example = "6.13.0-rc5";
        description = "Kernel version to build.";
      };

      majorMinor = lib.mkOption {
        type = lib.types.str;
        default = majorMinor;
        readOnly = true;
        description = "Computed major.minor version (e.g., 6.12).";
      };

      sourceSha256 = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "SHA256 hash of the kernel tarball (required if source != local).";
      };

      localSourcePath = lib.mkOption {
        type = lib.types.nullOr lib.types.path;
        default = null;
        description = "Local kernel source path when source = 'local'.";
      };

      patches = lib.mkOption {
        type = lib.types.listOf (lib.types.submodule {
          options = {
            name = lib.mkOption {
              type = lib.types.str;
              description = "Patch identifier (used in logs and tracking).";
            };
            url = lib.mkOption {
              type = lib.types.nullOr lib.types.str;
              default = null;
              description = "URL to fetch patch from.";
            };
            path = lib.mkOption {
              type = lib.types.nullOr lib.types.path;
              default = null;
              description = "Local path to patch file.";
            };
            sha256 = lib.mkOption {
              type = lib.types.nullOr lib.types.str;
              default = null;
              description = "SHA256 hash for URL-fetched patches.";
            };
            cveIds = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              example = [ "CVE-2026-12345" ];
              description = "CVE IDs this patch addresses.";
            };
            subsystems = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              example = [ "net" "security" ];
              description = "Kernel subsystems affected by this patch.";
            };
          };
        });
        default = [];
        description = "List of patches to apply to the kernel source.";
      };

      configFragments = lib.mkOption {
        type = lib.types.listOf lib.types.lines;
        default = [];
        example = [
          ''
            CONFIG_DEBUG_INFO=y
            CONFIG_DEBUG_INFO_DWARF5=y
          ''
        ];
        description = "Additional kernel config fragments to append.";
      };

      rustSupport = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = ''
          Enable Rust-for-Linux support.
          Required for building Rust kernel modules (DRM drivers 2027+).
        '';
      };

      rustVersion = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "1.78.0";
        description = "Specific Rust version required by this kernel (null = use system).";
      };

      extraBuildFlags = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [];
        example = [ "LLVM=1" "LLVM_IAS=1" ];
        description = "Extra flags passed to kernel make.";
      };
    };

    hardening = {
      enable = lib.mkEnableOption "kernel hardening configuration";

      level = lib.mkOption {
        type = lib.types.enum [ "standard" "maximum" "custom" ];
        default = "standard";
        description = ''
          Hardening preset level:
          - standard: KSPP baseline (ASLR, stack protector, SLAB hardening)
          - maximum: standard + CFI + shadow call stack + lockdown
          - custom: Only apply custom fragments
        '';
      };

      customFragments = lib.mkOption {
        type = lib.types.listOf lib.types.lines;
        default = [];
        description = "Custom hardening config fragments (for level = custom).";
      };

      mitigations = {
        spectre = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable Spectre mitigations (retpoline, IBRS).";
        };

        meltdown = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable Meltdown mitigations (KPTI).";
        };

        mds = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable MDS mitigations.";
        };

        srso = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable SRSO mitigations (AMD Zen).";
        };
      };
    };

    cveTracking = {
      enable = lib.mkEnableOption "CVE tracking integration";

      aidbEndpoint = lib.mkOption {
        type = lib.types.str;
        default = "http://127.0.0.1:8002";
        description = "AIDB MCP server endpoint for CVE data.";
      };

      autoScan = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Automatically scan kernel for CVEs on boot.";
      };
    };
  };

  config = lib.mkMerge [
    # Hardening config applies independently (works with any kernel)
    (lib.mkIf hardeningCfg.enable {
      # Add kernel mitigations to boot parameters
      boot.kernelParams =
        lib.optionals hardeningCfg.mitigations.spectre [ "spectre_v2=on" "spectre_v1=on" ]
        ++ lib.optionals hardeningCfg.mitigations.meltdown [ "pti=on" ]
        ++ lib.optionals hardeningCfg.mitigations.mds [ "mds=full" ]
        ++ lib.optionals hardeningCfg.mitigations.srso [ "spec_rstack_overflow=safe-ret" ];
    })

    # CVE tracking: auto-scan kernel on boot
    (lib.mkIf (cfg.cveTracking.enable && cfg.cveTracking.autoScan) {
      systemd.services.kernel-cve-scan = {
        description = "Scan running kernel for known CVEs";
        after = [ "network-online.target" "aidb-mcp-server.service" ];
        wants = [ "network-online.target" ];
        wantedBy = [ "multi-user.target" ];

        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          ExecStart = pkgs.writeShellScript "kernel-cve-scan" ''
            set -euo pipefail
            KERNEL_VERSION=$(${pkgs.coreutils}/bin/uname -r)
            HOSTNAME=$(${pkgs.nettools}/bin/hostname)
            AIDB="${cfg.cveTracking.aidbEndpoint}"

            echo "Scanning kernel $KERNEL_VERSION for CVEs..."

            # Check if AIDB is available
            if ! ${pkgs.curl}/bin/curl -sf "$AIDB/health" >/dev/null 2>&1; then
              echo "AIDB not available, skipping CVE scan"
              exit 0
            fi

            # Submit scan request
            RESULT=$(${pkgs.curl}/bin/curl -sf "$AIDB/kernel/scan" \
              -X POST \
              -H "Content-Type: application/json" \
              -d "{\"hostname\": \"$HOSTNAME\", \"kernel_version\": \"$KERNEL_VERSION\"}" \
              2>&1) || {
              echo "CVE scan request failed: $RESULT"
              exit 0  # Don't fail boot on scan failure
            }

            # Parse and report results
            TOTAL=$(echo "$RESULT" | ${pkgs.jq}/bin/jq -r '.total_cves // 0')
            CRITICAL=$(echo "$RESULT" | ${pkgs.jq}/bin/jq -r '.critical // 0')
            HIGH=$(echo "$RESULT" | ${pkgs.jq}/bin/jq -r '.high // 0')

            echo "CVE scan complete: $TOTAL total ($CRITICAL critical, $HIGH high)"

            if [ "$CRITICAL" -gt 0 ]; then
              echo "WARNING: Critical CVEs detected! Review with: curl $AIDB/kernel/hosts/$HOSTNAME/vulnerabilities"
            fi
          '';

          # Hardening
          PrivateTmp = true;
          ProtectSystem = "strict";
          ProtectHome = true;
          NoNewPrivileges = true;
          PrivateDevices = true;
        };
      };
    })

    # Custom kernel build config
    (lib.mkIf customCfg.enable {
      # Use custom kernel packages
      boot.kernelPackages = lib.mkForce selectedKernelPackages;

      # Ensure Rust toolchain is available for Rust kernel builds
      environment.systemPackages = lib.mkIf customCfg.rustSupport (with pkgs; [
        rustc
        cargo
        rust-bindgen
        llvmPackages_latest.clang
        llvmPackages_latest.llvm
      ]);

      # Warning assertions
      warnings = lib.mkIf (customCfg.sourceSha256 == "" && customCfg.source != "local") [
        "mySystem.kernel.customBuild: sourceSha256 is empty but source is '${customCfg.source}'. Build will fail."
      ];

      assertions = [
        {
          assertion = customCfg.source != "local" || customCfg.localSourcePath != null;
          message = "mySystem.kernel.customBuild: localSourcePath must be set when source = 'local'.";
        }
        {
          assertion = !customCfg.rustSupport || pkgs ? rustc;
          message = "mySystem.kernel.customBuild: Rust support requires rustc in pkgs.";
        }
      ];
    })
  ];
}
