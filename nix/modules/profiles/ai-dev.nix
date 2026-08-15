{
  lib,
  config,
  pkgs,
  ...
}: let
  cfg = config.mySystem;
  flatpakProfiles = import ../../data/flatpak-profiles.nix;
  profilePackages = import ../../data/profile-system-packages.nix;
in {
  config = lib.mkIf (cfg.profile == "ai-dev") {
    # ── Role Activation ─────────────────────────────────────────────────────────
    mySystem.roles.aiStack.enable = lib.mkDefault true;
    mySystem.roles.cppDev.enable = lib.mkDefault true;
    mySystem.roles.virtualization.enable = lib.mkDefault true;
    mySystem.roles.gaming.enable = lib.mkDefault false;
    mySystem.roles.desktop.enable = lib.mkDefault true;
    mySystem.mcpServers.enable = lib.mkDefault true;
    mySystem.monitoring.enable = lib.mkDefault true;
    mySystem.monitoring.commandCenter.enable = lib.mkDefault true;
    mySystem.localhostIsolation.enable = lib.mkDefault true;
    mySystem.aiStack.switchboard.enable = lib.mkDefault true;
    # Foundation C — R6 activation STEP 1 (2026-08-02, owner-authorized). The
    # runner-deployment-hardening slice (rev4, accepted + integrated 0cf1192e) fixed
    # the 5 R5-shadow deploy bugs: it now adopts the systemd socket-activation fd
    # (preserving SocketGroup=aq-execution-cell-clients) and authenticates the
    # switchboard's effective UID via AQ_EXECUTION_CELL_RUNNER_CLIENT_USER. This turns
    # the runner ON (socket-activated, bwrap-confined) WITHOUT the switchboard shadow
    # adapter — CAPABILITY_CELL_ADAPTER stays 0 (switchboard.nix). Nothing submits to
    # the runner yet; this step is the DEPLOY-EXERCISE: prove the runner starts clean,
    # the socket keeps its client group after start, and a client passes SO_PEERCRED.
    # Step 2 (a separate owner act) flips CAPABILITY_CELL_ADAPTER=1 for the full
    # mint->sign->UDS->bwrap-cell->validator shadow round-trip. REVERT: both to false.
    mySystem.aiStack.executionCellRunner.enable = true;
    mySystem.aiStack.executionCellRunner.flagOn = true;
    # ALA activation Phase 1 (2026-08-06): enable the confined lease-signing authority so its
    # dedicated user + UDS + SOPS-provisioned Ed25519 private key come up, but leave the switchboard
    # flag CAPABILITY_ASYMMETRIC_LEASE=0 (Phase 2) — the gate keeps in-process HMAC, so this rebuild
    # is a no-behavior-change canary (prove the signer is healthy before any first-party lease flows
    # through it). REVERT: enable=false. Runbook: ASYMMETRIC-LEASE-AUTHORITY-ACTIVATION-RUNBOOK-20260806.md.
    mySystem.aiStack.leaseSigningAuthority.enable = true;
    # Auto-nudge the Antigravity IDE when an advisory task is dropped into its inbox, so multi-agent
    # rounds don't need a manual IDE prompt. Per-user systemd path unit in the owner's own session,
    # firing the owner-gated wake. No-op when the IDE isn't open. REVERT: enable=false.
    mySystem.aiStack.antigravityAutoWake.enable = true;
    # C2-SCI (Foundation C Q-C6-1): confined scheduler-lease-context issuer. Activated 2026-08-15 with the
    # real owner-provisioned SOPS signer key + verifier-allowlist public key. Pairs with the switchboard
    # CAPABILITY_SCHEDULER_CONTEXT_ISSUER=1 flag. REVERT: enable=false → default-OFF byte-parity.
    mySystem.aiStack.c2SchedulerContextIssuer.enable = true;
    mySystem.profileData.flatpakApps = lib.mkDefault flatpakProfiles.ai_workstation;
    mySystem.profileData.systemPackageNames = lib.mkDefault profilePackages.ai-dev;

    # ── System Improvement Plan March 2026 ──────────────────────────────────────
    # These features are profile-driven: any host using ai-dev gets them.
    # Override in host/default.nix with lib.mkForce if needed.

    # Kernel: track the newest supported stable kernel for workstation-class AI workloads.
    mySystem.kernel.track = lib.mkDefault "latest-stable";

    # Security: Maximum kernel hardening (CFI, shadow call stack, lockdown)
    mySystem.kernel.hardening = {
      enable = lib.mkDefault true;
      level = lib.mkDefault "maximum";
      mitigations = {
        spectre = lib.mkDefault true;
        meltdown = lib.mkDefault true;
        mds = lib.mkDefault true;
        srso = lib.mkDefault true; # AMD Zen specific
      };
    };

    # Security: Kernel CVE tracking - auto-scan on boot
    mySystem.kernel.cveTracking = {
      enable = lib.mkDefault true;
      autoScan = lib.mkDefault true;
    };

    # Security: CrowdSec IPS - community threat intelligence
    # Watches SSH and Nginx logs for malicious patterns, blocks via nftables bouncer.
    # Firewall bouncer only enabled when secrets are configured.
    mySystem.security.crowdsec = {
      enable = lib.mkDefault true;
      watchSshd = lib.mkDefault true;
      watchNginx = lib.mkDefault true;
      # Bouncer requires API key from sops - only enable when secrets are available
      enableFirewallBouncer = lib.mkDefault config.mySystem.secrets.enable;
      apiKeyFile =
        lib.mkIf config.mySystem.secrets.enable
        (lib.mkDefault "/run/secrets/${config.mySystem.secrets.names.crowdsecBouncerApiKey}");
    };

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
      subsystems = lib.mkDefault ["dri-devel" "netdev" "linux-hardening" "rust-for-linux"];
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

    # ── AGI Scaffold — Phases 16–20 ─────────────────────────────────────────────
    # Any host running the ai-dev profile gets the full AGI scaffold.
    # Override with lib.mkForce false in host/default.nix to disable.
    mySystem.aiStack.identityKernel.enable = lib.mkDefault true;
    mySystem.aiStack.agentMesh.enable = lib.mkDefault true;
    mySystem.aiStack.affectiveEngine.enable = lib.mkDefault true;
    mySystem.aiStack.worldModel.enable = lib.mkDefault true;

    # ── Touchpad defaults for modern laptops ────────────────────────────────────
    # clickfinger eliminates accidental middle-click on ClickPads
    services.libinput.touchpad = {
      middleEmulation = lib.mkDefault false;
      clickMethod = lib.mkDefault "clickfinger";
      disableWhileTyping = lib.mkDefault true;
      tapping = lib.mkDefault true;
      scrollMethod = lib.mkDefault "twofinger";
      naturalScrolling = lib.mkDefault false;
    };
  };
}
