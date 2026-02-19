{ lib, pkgs, config, ... }:
let
  cfg = config.mySystem;
  bootFsType = lib.attrByPath [ "fileSystems" "/boot" "fsType" ] null config;
  useSystemdBoot = (!cfg.secureboot.enable) && (cfg.hardware.firmwareType == "efi" || bootFsType == "vfat");
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
    "kubectl"
  ];
  mergedPackageNames = lib.unique (basePackageNames ++ cfg.profileData.systemPackageNames);
  missingPackageNames = builtins.filter (name: !(builtins.hasAttr name pkgs)) mergedPackageNames;
  resolvedPackages =
    builtins.filter (pkg: pkg != null) (
      map (name:
        if builtins.hasAttr name pkgs then pkgs.${name} else null
      ) mergedPackageNames
    );
in
{
  config = {
    networking.hostName = lib.mkDefault cfg.hostName;

    nix.settings.experimental-features = [ "nix-command" "flakes" ];

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

    environment.systemPackages = resolvedPackages;

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

    warnings = lib.optionals (missingPackageNames != [ ]) [
      "Ignoring unknown package names in mySystem.profileData.systemPackageNames: ${lib.concatStringsSep ", " missingPackageNames}"
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
      ];

    # This keeps the scaffold evaluable while migration progresses.
    system.stateVersion = lib.mkDefault "25.11";
  };
}
