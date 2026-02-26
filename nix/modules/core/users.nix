{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Core user provisioning — declares the primary system user.
#
# Sources the user name from mySystem.primaryUser (set in facts.nix or
# per-host default.nix).  Groups, shell, and shell enablement are set here;
# per-host customisation goes in nix/hosts/<host>/default.nix.
#
# PASSWORD POLICY — read before modifying:
#   users.mutableUsers = true (explicitly set below) means NixOS preserves
#   the password from the running system's /etc/shadow on every nixos-rebuild.
#   The deploy script NEVER prompts for or changes the login password.
#   To change your password use passwd(1) normally — it will survive rebuilds.
#
#   Do NOT set hashedPassword / initialPassword / hashedPasswordFile here
#   unless you intentionally want declarative password management. Setting any
#   of those will override the preserved /etc/shadow entry on the next switch.
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
in
{
  config = {
    # Explicitly preserve passwords from /etc/shadow across nixos-rebuild.
    # With mutableUsers = true NixOS never touches a user's password unless a
    # hashedPassword / initialPassword directive is present in the config.
    # This is the key guard that prevents the deploy script from resetting
    # the login password (NIX-ISSUE-PASSWORD-001).
    users.mutableUsers = lib.mkDefault true;

    users.users.${cfg.primaryUser} = {
      isNormalUser = true;
      # Base groups at normal priority (100) so role modules using lib.mkAfter
      # (also priority 100) correctly *merge* with this list via listOf's concat
      # merge strategy, rather than replacing it (which lib.mkDefault would cause
      # since mkDefault = priority 1000 loses to any normal-priority definition).
      extraGroups = [
        "wheel"           # sudo / polkit access
        "networkmanager"  # manage network connections without sudo
        "video"           # GPU / backlight access
        "audio"           # ALSA fallback (PipeWire covers most cases)
        "input"           # evdev device access for Wayland compositors
      ];
      # SSH authorized keys — set mySystem.sshAuthorizedKeys in per-host default.nix.
      openssh.authorizedKeys.keys = lib.mkDefault cfg.sshAuthorizedKeys;
      # NO hashedPassword / initialPassword / hashedPasswordFile here.
      # Passwords are managed by the OS via passwd(1); they survive rebuilds
      # because users.mutableUsers = true preserves /etc/shadow.
    };

    # Force default login shell to zsh so it wins over upstream bash defaults.
    users.defaultUserShell = lib.mkForce pkgs.zsh;

    # zsh must be enabled system-wide when used as a login shell.
    programs.zsh.enable = lib.mkDefault true;
  };
}
