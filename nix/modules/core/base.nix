{ lib, pkgs, config, ... }:
let
  cfg = config.mySystem;
  bootFsType = lib.attrByPath [ "fileSystems" "/boot" "fsType" ] null config;
  hostHasEfiFirmware = builtins.pathExists "/sys/firmware/efi";
  useSystemdBoot = (!cfg.secureboot.enable) && (bootFsType == "vfat" || hostHasEfiFirmware);
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

    environment.systemPackages = resolvedPackages;

    warnings = lib.optionals (missingPackageNames != [ ]) [
      "Ignoring unknown package names in mySystem.profileData.systemPackageNames: ${lib.concatStringsSep ", " missingPackageNames}"
    ];

    # This keeps the scaffold evaluable while migration progresses.
    system.stateVersion = lib.mkDefault "25.11";
  };
}
