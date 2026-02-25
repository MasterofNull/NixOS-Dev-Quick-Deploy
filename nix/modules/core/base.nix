{ lib, pkgs, config, ... }:
let
  cfg = config.mySystem;
  ports = cfg.ports;
  bootFsType = lib.attrByPath [ "fileSystems" "/boot" "fsType" ] null config;
  useSystemdBoot = (!cfg.secureboot.enable) && (cfg.hardware.firmwareType == "efi" || bootFsType == "vfat");
  selectedKernelPackages =
    if cfg.kernel.track == "latest-stable" && pkgs ? linuxPackages_latest then
      pkgs.linuxPackages_latest
    else
      pkgs.linuxPackages;
  usersCfg = config.users.users or { };
  hasPrimaryUserDecl = builtins.hasAttr cfg.primaryUser usersCfg;
  primaryUserCfg = if hasPrimaryUserDecl then usersCfg.${cfg.primaryUser} else { };
  hasRootDecl = builtins.hasAttr "root" usersCfg;
  rootUserCfg = if hasRootDecl then usersCfg.root else { };
  hasPasswordDirective = userCfg:
    (userCfg ? hashedPassword)
    || (userCfg ? hashedPasswordFile)
    || (userCfg ? initialPassword)
    || (userCfg ? initialHashedPassword)
    || (userCfg ? passwordFile);
  hashedPasswordLocked = userCfg:
    (userCfg ? hashedPassword)
    && (userCfg.hashedPassword != null)
    && builtins.isString userCfg.hashedPassword
    && (lib.hasPrefix "!" userCfg.hashedPassword || lib.hasPrefix "*" userCfg.hashedPassword);
  basePackageNames = [
    "curl"
    "flatpak"
    "git"
    "jq"
    "ripgrep"
    "nodejs"
    "go"
    "cargo"
    "ruby"
    "neovim"
  ];
  mergedPackageNames = lib.unique (basePackageNames ++ cfg.profileData.systemPackageNames);
  missingPackageNames = builtins.filter (name: !(builtins.hasAttr name pkgs)) mergedPackageNames;
  resolvedPackages =
    builtins.filter (pkg: pkg != null) (
      map (name:
        if builtins.hasAttr name pkgs then pkgs.${name} else null
      ) mergedPackageNames
    );

  # ── Dev testing helper scripts (referenced by system-health-check.sh) ──────
  # These are minimal wrappers installed as system commands so they appear in
  # PATH for all users without a project-local virtualenv.
  devHelperPackages = with pkgs; [
    watchexec  # file-watcher for pytest-watch; also useful standalone
    (writeShellScriptBin "pytest-init" ''
      set -euo pipefail
      mkdir -p tests
      [[ -f tests/__init__.py ]] || touch tests/__init__.py
      [[ -f tests/conftest.py ]] || printf '%s\n' \
        'import pytest' \
        "" \
        '@pytest.fixture' \
        'def tmp_data():' \
        '    return {}' \
        > tests/conftest.py
      if [[ ! -f pytest.ini ]] && [[ ! -f pyproject.toml ]]; then
        printf '%s\n' \
          '[pytest]' \
          'testpaths = tests' \
          'python_files = test_*.py *_test.py' \
          'python_classes = Test*' \
          'python_functions = test_*' \
          'addopts = -v --tb=short' \
          > pytest.ini
      fi
      echo "pytest structure initialized in $(pwd)" >&2
    '')
    (writeShellScriptBin "pytest-watch" ''
      exec ${watchexec}/bin/watchexec --exts py --restart -- pytest "$@"
    '')
    (writeShellScriptBin "pytest-report" ''
      exec pytest --tb=short --cov=. --cov-report=term-missing --cov-report=html "$@"
    '')
    (writeShellScriptBin "pytest-quick" ''
      exec pytest -x -q --no-header "$@"
    '')
  ];
in
{
  config = {
    networking.hostName = lib.mkDefault cfg.hostName;

    # Centralized port registry wiring
    mySystem.aiStack.llamaCpp.port = lib.mkDefault ports.llamaCpp;
    mySystem.aiStack.embeddingServer.port = lib.mkDefault ports.embedding;
    mySystem.aiStack.switchboard.port = lib.mkDefault ports.switchboard;
    mySystem.mcpServers.aidbPort = lib.mkDefault ports.mcpAidb;
    mySystem.mcpServers.hybridPort = lib.mkDefault ports.mcpHybrid;
    mySystem.mcpServers.ralphPort = lib.mkDefault ports.mcpRalph;
    mySystem.mcpServers.redis.port = lib.mkDefault ports.redis;
    mySystem.monitoring.prometheusPort = lib.mkDefault ports.prometheus;
    mySystem.monitoring.nodeExporterPort = lib.mkDefault ports.nodeExporter;
    mySystem.monitoring.commandCenter.frontendPort = lib.mkDefault ports.commandCenterFrontend;
    mySystem.monitoring.commandCenter.apiPort = lib.mkDefault ports.commandCenterApi;

    nix.settings = {
      experimental-features = [ "nix-command" "flakes" ];
      auto-optimise-store = lib.mkDefault true;
      # Explicit policy (not mkDefault) to prevent regressions where only
      # root is trusted after a generation switch.
      trusted-users = [ "root" "@wheel" cfg.primaryUser ];
      allowed-users = [ "@wheel" cfg.primaryUser ];
      substituters = lib.mkDefault cfg.deployment.nixBinaryCaches;
    };
    nix.gc = {
      automatic = lib.mkDefault true;
      dates = lib.mkDefault "weekly";
      options = lib.mkDefault "--delete-older-than 7d";
    };
    nix.optimise = {
      automatic = lib.mkDefault true;
      dates = lib.mkDefault [ "weekly" ];
    };
    boot.kernelPackages = lib.mkDefault selectedKernelPackages;

    # Default to systemd-boot on EFI hosts so flake builds remain bootable
    # even when only hardware-configuration.nix is imported.
    boot.loader.systemd-boot.enable = lib.mkIf useSystemdBoot (lib.mkDefault true);
    boot.loader.efi.canTouchEfiVariables = lib.mkIf useSystemdBoot (lib.mkDefault true);
    boot.loader.systemd-boot.configurationLimit = lib.mkIf useSystemdBoot (lib.mkDefault 20);
    boot.loader.systemd-boot.graceful = lib.mkIf useSystemdBoot (lib.mkDefault true);
    boot.loader.grub.enable = lib.mkDefault false;

    # Systemd-based initrd: no bash in initrd, ~20-30% faster boot.
    # Available on all supported kernels in 25.11. Safe default for EFI hosts;
    # BIOS hosts may need to set this false in local-overrides.nix.
    boot.initrd.systemd.enable = lib.mkDefault true;

    # Keep /tmp on tmpfs by default (legacy template parity, opt-out via facts).
    boot.tmp.useTmpfs = lib.mkDefault cfg.deployment.tmpUseTmpfs;

    # nix-ld: compatibility layer enabling pre-compiled generic Linux ELF binaries
    # (Claude Code installer, commercial AI CLI tools) to run on NixOS without
    # patchelf. Provides /lib64/ld-linux-x86-64.so.2 and basic glibc stub.
    programs.nix-ld = {
      enable = lib.mkDefault true;
      libraries = with pkgs; [
        stdenv.cc.cc.lib
        zlib
        glibc
        gcc-unwrapped.lib
        mesa
        libglvnd
        openssl
        curl
        libxml2
        libxcrypt
      ];
    };

    programs.appimage = {
      enable = lib.mkDefault true;
      binfmt = lib.mkDefault true;
    };

    environment.systemPackages = resolvedPackages ++ devHelperPackages;

    # ---- Security hardening (system-wide baseline) -------------------------
    # These mirror the security block in templates/configuration.nix so that
    # the flake-first path provides equivalent hardening without the template.

    # polkit: privilege escalation daemon required by GUI apps (e.g. COSMIC
    # settings, NetworkManager applet, package managers).
    security.polkit.enable = lib.mkDefault true;

    # sudo: restrict to wheel group; require password for every invocation.
    security.sudo = {
      enable           = lib.mkDefault true;
      execWheelOnly    = lib.mkDefault true;   # wheel group only — no free sudo
      wheelNeedsPassword = lib.mkDefault true; # no passwordless sudo by default

      # Extend credential cache to 60 minutes so a single deploy run (nixos-rebuild
      # → home-manager → flatpak sync) does not prompt for password multiple times.
      # The default 5-minute timeout expires mid-deploy when operations take >5 min.
      extraConfig = lib.mkDefault ''
        Defaults timestamp_timeout=60
      '';

      # Allow wheel members to run bootctl status without a password.
      # deploy-clean.sh calls bootctl status as the non-root operator user to
      # validate the bootloader before switching; without this rule the preflight
      # silently skips all bootloader checks.
      extraRules = lib.mkDefault [
        {
          groups   = [ "wheel" ];
          commands = [
            { command = "${pkgs.systemd}/bin/bootctl"; options = [ "NOPASSWD" ]; }
          ];
        }
      ];
    };

    # AppArmor: mandatory access control — defence-in-depth for confined
    # services. Does not interfere with normal user operations.
    security.apparmor.enable = lib.mkDefault true;

    # Fonts: always provide popular Nerd Fonts system-wide so terminal
    # font pickers (including COSMIC) can discover them reliably.
    fonts.fontconfig.enable = lib.mkDefault true;
    fonts.fontDir.enable = lib.mkDefault true;
    fonts.packages = lib.mkAfter (with pkgs; [
      nerd-fonts.meslo-lg
      nerd-fonts.jetbrains-mono
      nerd-fonts.fira-code
      nerd-fonts.hack
      noto-fonts
      noto-fonts-color-emoji
    ]);

    warnings = lib.optionals (missingPackageNames != [ ]) [
      "Ignoring unknown package names in mySystem.profileData.systemPackageNames: ${lib.concatStringsSep ", " missingPackageNames}"
    ] ++ lib.optionals (cfg.kernel.track == "latest-stable" && !(pkgs ? linuxPackages_latest)) [
      "mySystem.kernel.track=latest-stable requested, but pkgs.linuxPackages_latest is unavailable for this platform. Falling back to pkgs.linuxPackages."
    ];

    assertions =
      [
        {
          assertion = !(hashedPasswordLocked primaryUserCfg);
          message = "Primary user '${cfg.primaryUser}' has a locked hashedPassword in declarative config. Refusing build to prevent account lockout.";
        }
        {
          assertion = !(cfg.deployment.initrdEmergencyAccess && hasRootDecl && hashedPasswordLocked rootUserCfg);
          message = "Root user has a locked hashedPassword while mySystem.deployment.initrdEmergencyAccess=true. Refusing build to preserve recovery login.";
        }
        {
          assertion = !(!config.users.mutableUsers && hasPrimaryUserDecl && !hasPasswordDirective primaryUserCfg);
          message = "users.mutableUsers=false requires a password directive for users.users.${cfg.primaryUser}.";
        }
        {
          assertion = !(!config.users.mutableUsers && !hasPrimaryUserDecl);
          message = "users.mutableUsers=false requires declaring users.users.${cfg.primaryUser}.";
        }
        {
          assertion = !(cfg.deployment.initrdEmergencyAccess && hasRootDecl && !hasPasswordDirective rootUserCfg);
          message = "mySystem.deployment.initrdEmergencyAccess=true requires a password directive on users.users.root when root is declared.";
        }

        # ── Phase 18.3: Configuration schema validation ───────────────────────
        # These assertions catch common misconfiguration at eval time,
        # preventing broken deployments from reaching nixos-rebuild.

        # AI stack: K3s backend cannot have llamaCpp.enable with conflicting port settings.
        # (No hard conflict; this is a guard against accidental port collisions.)
        {
          assertion = !(cfg.roles.aiStack.enable
            && cfg.aiStack.backend == "llamacpp"
            && cfg.mcpServers.enable
            && cfg.mcpServers.embeddingsPort == cfg.aiStack.llamaCpp.port);
          message = "Port conflict: mcpServers.embeddingsPort (${toString cfg.mcpServers.embeddingsPort}) must not equal aiStack.llamaCpp.port (${toString cfg.aiStack.llamaCpp.port}).";
        }

        # MCP server ports must all be distinct.
        {
          assertion = cfg.mcpServers.embeddingsPort != cfg.mcpServers.aidbPort
            && cfg.mcpServers.embeddingsPort != cfg.mcpServers.hybridPort
            && cfg.mcpServers.embeddingsPort != cfg.mcpServers.ralphPort
            && cfg.mcpServers.aidbPort       != cfg.mcpServers.hybridPort
            && cfg.mcpServers.aidbPort       != cfg.mcpServers.ralphPort
            && cfg.mcpServers.hybridPort     != cfg.mcpServers.ralphPort;
          message = "mcpServers port conflict: embeddingsPort=${toString cfg.mcpServers.embeddingsPort}, aidbPort=${toString cfg.mcpServers.aidbPort}, hybridPort=${toString cfg.mcpServers.hybridPort}, ralphPort=${toString cfg.mcpServers.ralphPort} — all must be distinct.";
        }


        # Central ports registry: internal service ports must be unique.
        {
          assertion = ports.postgres != ports.redis
            && ports.postgres != ports.qdrantHttp
            && ports.postgres != ports.mcpAidb
            && ports.redis != ports.qdrantHttp
            && ports.redis != ports.mcpAidb
            && ports.qdrantHttp != ports.mcpAidb
            && ports.mcpAidb != ports.mcpHybrid
            && ports.mcpAidb != ports.mcpRalph
            && ports.mcpHybrid != ports.mcpRalph
            && ports.otelCollectorMetrics != ports.commandCenterFrontend
            && ports.otelCollectorMetrics != ports.commandCenterApi
            && ports.otelCollectorMetrics != ports.prometheus
            && ports.otelCollectorMetrics != ports.nodeExporter
            && ports.otelCollectorMetrics != ports.otlpGrpc
            && ports.otelCollectorMetrics != ports.otlpHttp
            && ports.otlpGrpc != ports.otlpHttp;
          message = "ports registry conflict: postgres=${toString ports.postgres}, redis=${toString ports.redis}, qdrantHttp=${toString ports.qdrantHttp}, mcpAidb=${toString ports.mcpAidb}, mcpHybrid=${toString ports.mcpHybrid}, mcpRalph=${toString ports.mcpRalph}, otelCollectorMetrics=${toString ports.otelCollectorMetrics}, otlpGrpc=${toString ports.otlpGrpc}, otlpHttp=${toString ports.otlpHttp}, commandCenterFrontend=${toString ports.commandCenterFrontend}, commandCenterApi=${toString ports.commandCenterApi}, prometheus=${toString ports.prometheus}, nodeExporter=${toString ports.nodeExporter} — all constrained ports must be distinct.";
        }

        # MCP servers require the AI stack role to be enabled.
        {
          assertion = !(cfg.mcpServers.enable && !cfg.roles.aiStack.enable);
          message = "mcpServers.enable = true requires roles.aiStack.enable = true.";
        }

        # Hibernation requires swap.
        {
          assertion = !(cfg.deployment.enableHibernation && cfg.deployment.swapSizeGb == 0);
          message = "deployment.enableHibernation = true requires deployment.swapSizeGb > 0 (currently 0). Set swapSizeGb >= systemRamGb (${toString cfg.hardware.systemRamGb}).";
        }

        # Secure boot requires EFI firmware.
        {
          assertion = !(cfg.secureboot.enable && cfg.hardware.firmwareType != "efi");
          message = "secureboot.enable = true requires hardware.firmwareType = \"efi\" (currently \"${cfg.hardware.firmwareType}\").";
        }

        # LUKS disk encryption requires a supported layout.
        {
          assertion = !(cfg.disk.luks.enable && cfg.disk.layout == "none");
          message = "disk.luks.enable = true requires disk.layout != \"none\". Set disk.layout to \"gpt-luks-ext4\" or another LUKS-capable layout.";
        }
      ];

    # This keeps the scaffold evaluable while migration progresses.
    system.stateVersion = lib.mkDefault "25.11";
  };
}
