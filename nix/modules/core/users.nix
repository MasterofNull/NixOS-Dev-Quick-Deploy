{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Core user provisioning — declares the primary system user.
#
# Sources the user name from mySystem.primaryUser (set in facts.nix or
# per-host default.nix).  Groups, shell, and shell enablement are set here;
# per-host customisation goes in nix/hosts/<host>/default.nix.
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
in
{
  config = {
    users.users.${cfg.primaryUser} = {
      isNormalUser = true;
      extraGroups  = lib.mkDefault [
        "wheel"           # sudo / polkit access
        "networkmanager"  # manage network connections without sudo
        "video"           # GPU / backlight access
        "audio"           # ALSA fallback (PipeWire covers most cases)
        "input"           # evdev device access for Wayland compositors
      ];
      shell = lib.mkForce pkgs.zsh;
      # SSH authorized keys — set mySystem.sshAuthorizedKeys in per-host default.nix.
      openssh.authorizedKeys.keys = lib.mkDefault cfg.sshAuthorizedKeys;
    };

    # Set the global default shell so primary user shell does not conflict
    # with NixOS user module defaults at equal priority.
    users.defaultUserShell = lib.mkDefault pkgs.zsh;

    # zsh must be enabled system-wide when used as a login shell.
    programs.zsh.enable = lib.mkDefault true;
  };
}
