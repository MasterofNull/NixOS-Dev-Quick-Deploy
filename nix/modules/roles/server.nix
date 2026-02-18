{ lib, config, ... }:
# ---------------------------------------------------------------------------
# Server role — headless optimisations for machines that don't run a GUI.
#
# Activated when: mySystem.roles.server.enable = true
#
# Removes display manager, GUI audio, and Bluetooth.
# Hardens SSH, enables fail2ban, and tightens the firewall default.
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  serverEnabled = cfg.roles.server.enable;
in
{
  config = lib.mkIf serverEnabled {

    # ---- Headless boot target ----------------------------------------------
    systemd.defaultUnit = lib.mkDefault "multi-user.target";

    # ---- Disable GUI services ----------------------------------------------
    # Force-off so they cannot be accidentally enabled by desktop modules
    # imported alongside this role.
    services.xserver.enable            = lib.mkForce false;
    services.displayManager.gdm.enable = lib.mkForce false;

    # Pipewire and rtkit are not needed without a display session.
    services.pipewire.enable = lib.mkDefault false;
    security.rtkit.enable    = lib.mkDefault false;

    # Bluetooth is not needed on servers.
    hardware.bluetooth.enable = lib.mkDefault false;

    # ---- SSH hardening -----------------------------------------------------
    services.openssh = {
      enable = lib.mkDefault true;
      settings = {
        PermitRootLogin            = lib.mkDefault "no";
        PasswordAuthentication     = lib.mkDefault false;
        KbdInteractiveAuthentication = lib.mkDefault false;
        X11Forwarding              = lib.mkDefault false;
        # Allow only the declared primary user and members of the wheel group.
        AllowUsers = lib.mkDefault [ cfg.primaryUser ];
      };
      # Restrict to strong ciphers/MACs to reduce attack surface.
      extraConfig = lib.mkDefault ''
        Ciphers aes256-gcm@openssh.com,chacha20-poly1305@openssh.com
        MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
        KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org
      '';
    };

    # ---- Fail2ban ----------------------------------------------------------
    services.fail2ban = {
      enable = lib.mkDefault true;
      maxretry = lib.mkDefault 5;
      bantime  = lib.mkDefault "1h";
    };

    # ---- Firewall defaults -------------------------------------------------
    # Server role uses deny-all default; open specific ports in host config.
    networking.firewall = {
      enable          = lib.mkDefault true;
      allowedTCPPorts = lib.mkDefault [ 22 ];
    };

    # ---- Nix daemon: restrict build users ---------------------------------
    nix.settings.trusted-users = lib.mkDefault [ "root" cfg.primaryUser ];
  };
}
