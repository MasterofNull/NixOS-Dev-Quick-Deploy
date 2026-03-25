{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  flatpakProfiles = import ../../data/flatpak-profiles.nix;
  profilePackages = import ../../data/profile-system-packages.nix;
in
{
  config = lib.mkIf (cfg.profile == "ai-dev") {
    # ── Role Activation ─────────────────────────────────────────────────────────
    mySystem.roles.aiStack.enable = lib.mkDefault true;
    mySystem.roles.virtualization.enable = lib.mkDefault true;
    mySystem.roles.gaming.enable = lib.mkDefault false;
    mySystem.roles.desktop.enable = lib.mkDefault true;
    mySystem.mcpServers.enable = lib.mkDefault true;
    mySystem.monitoring.enable = lib.mkDefault true;
    mySystem.monitoring.commandCenter.enable = lib.mkDefault true;
    mySystem.localhostIsolation.enable = lib.mkDefault true;
    mySystem.profileData.flatpakApps = lib.mkDefault flatpakProfiles.ai_workstation;
    mySystem.profileData.systemPackageNames = lib.mkDefault profilePackages.ai-dev;

    # ── System Improvement Plan March 2026 ──────────────────────────────────────
    # These features are profile-driven: any host using ai-dev gets them.
    # Override in host/default.nix with lib.mkForce if needed.

    # Kernel: 6.19-latest for AMD GPU boost (+30%), HDR, ext4 improvements
    mySystem.kernel.track = lib.mkDefault "6.19-latest";

    # Security: Maximum kernel hardening (CFI, shadow call stack, lockdown)
    mySystem.kernel.hardening = {
      enable = lib.mkDefault true;
      level = lib.mkDefault "maximum";
      mitigations = {
        spectre = lib.mkDefault true;
        meltdown = lib.mkDefault true;
        mds = lib.mkDefault true;
        srso = lib.mkDefault true;  # AMD Zen specific
      };
    };

    # Security: CrowdSec IPS - community threat intelligence
    # Disabled by default - enable in host config when CrowdSec is available/configured
    # mySystem.security.crowdsec = {
    #   enable = lib.mkDefault true;
    #   watchSshd = lib.mkDefault true;
    #   watchNginx = lib.mkDefault true;
    #   enableFirewallBouncer = lib.mkDefault false;  # Requires apiKeyFile
    # };

    # Security: Secure Boot via lanzaboote
    mySystem.secureboot.enable = lib.mkDefault true;

    # CVE tracking: daily NVD sync
    services.nvd-sync = {
      enable = lib.mkDefault true;
      interval = lib.mkDefault "daily";
      onBoot = lib.mkDefault true;
    };

    # Kernel development: lore.kernel.org patch monitoring
    services.lore-sync = {
      enable = lib.mkDefault true;
      subsystems = lib.mkDefault [ "dri-devel" "netdev" "linux-hardening" "rust-for-linux" ];
      interval = lib.mkDefault "6h";
    };

    # ── Desktop Environment Polish ──────────────────────────────────────────────

    # Polkit rules for COSMIC/desktop power settings - password-free power mgmt
    security.polkit.extraConfig = ''
      polkit.addRule(function(action, subject) {
        if ((action.id == "org.freedesktop.UPower.PowerProfiles.switch-profile" ||
             action.id == "org.freedesktop.UPower.PowerProfiles.hold-profile" ||
             action.id == "org.freedesktop.UPower.PowerProfiles.configure-action" ||
             action.id == "org.freedesktop.login1.suspend" ||
             action.id == "org.freedesktop.login1.hibernate" ||
             action.id == "org.freedesktop.login1.power-off") &&
            subject.isInGroup("wheel")) {
          return polkit.Result.YES;
        }
      });
    '';

    # Firmware updates for hardware stability
    hardware.enableRedistributableFirmware = lib.mkDefault true;
    services.fwupd.enable = lib.mkDefault true;

    # Developer fonts baseline
    fonts = {
      fontconfig.enable = true;
      fontDir.enable = true;
      packages = with pkgs; [
        nerd-fonts.meslo-lg
        nerd-fonts.jetbrains-mono
        nerd-fonts.fira-code
        nerd-fonts.hack
        noto-fonts
        noto-fonts-color-emoji
      ];
    };

    # ── Touchpad defaults for modern laptops ────────────────────────────────────
    # clickfinger eliminates accidental middle-click on ClickPads
    services.libinput.touchpad = {
      middleEmulation    = lib.mkDefault false;
      clickMethod        = lib.mkDefault "clickfinger";
      disableWhileTyping = lib.mkDefault true;
      tapping            = lib.mkDefault true;
      scrollMethod       = lib.mkDefault "twofinger";
      naturalScrolling   = lib.mkDefault false;
    };
  };
}
