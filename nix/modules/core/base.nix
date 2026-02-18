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

    environment.systemPackages = resolvedPackages;

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
