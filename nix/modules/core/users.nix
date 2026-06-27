{
  lib,
  config,
  pkgs,
  ...
}:
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
in {
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
        "wheel" # sudo / polkit access
        "networkmanager" # manage network connections without sudo
        "video" # GPU / backlight access
        "audio" # ALSA fallback (PipeWire covers most cases)
        "input" # evdev device access for Wayland compositors
      ];
      # SSH authorized keys — set mySystem.sshAuthorizedKeys in per-host default.nix.
      openssh.authorizedKeys.keys = lib.mkDefault cfg.sshAuthorizedKeys;
      # NO hashedPassword / initialPassword / hashedPasswordFile here.
      # Passwords are managed by the OS via passwd(1); they survive rebuilds
      # because users.mutableUsers = true preserves /etc/shadow.

      # Allow AI stack service users (ai-hybrid, ai-aidb, etc.) to traverse the
      # home directory tree to reach live repo config files (e.g., the hot-reload
      # intent-routing-map.json).  Mode 0711 = owner rwx, others --x (traverse
      # only; no directory listing for non-owners).
      # homeMode sets the mode at home-directory CREATION only — it does not
      # update existing directories on rebuild. The activation script below
      # (deps=["users"]) handles existing installs.
      homeMode = "0711";
    };

    # Ensure home directory is traversable by AI service users.
    # Three-layer approach (homeMode alone does not update existing dirs):
    # 1. homeMode="0711" above — sets mode at home directory CREATION (new installs)
    # 2. activationScripts — sets mode on every nixos-rebuild switch
    # 3. systemd.tmpfiles.rules — adjusts existing paths on every boot and
    #    on systemd-tmpfiles --create (independent of activation script ordering)
    system.activationScripts.aiStackHomeDirTraversal = {
      deps = [ "users" ];
      text = ''
        if [ -d /home/${config.mySystem.primaryUser} ]; then
          chmod o+x /home/${config.mySystem.primaryUser}
        fi
      '';
    };

    # z-type tmpfiles rule: "adjust access mode of existing path".
    # Runs via systemd-tmpfiles on every boot and after nixos-rebuild switch,
    # independent of activation script ordering. Belt-and-suspenders for the
    # activation script above.
    systemd.tmpfiles.rules = [
      "z /home/${cfg.primaryUser} 0711 ${cfg.primaryUser} users -"
    ];

    # Force default login shell to zsh so it wins over upstream bash defaults.
    users.defaultUserShell = lib.mkForce pkgs.zsh;

    # zsh must be enabled system-wide when used as a login shell.
    programs.zsh.enable = lib.mkDefault true;
  };
}
