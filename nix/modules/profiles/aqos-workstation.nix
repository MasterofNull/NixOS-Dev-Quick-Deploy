{
  lib,
  config,
  pkgs,
  ...
}: let
  cfg = config.mySystem;
  flatpakProfiles = import ../../data/flatpak-profiles.nix;
  profilePackages = import ../../data/profile-system-packages.nix;
  # Local AI is OPTIONAL. The operator opts in by setting
  # mySystem.roles.aiStack.enable = true (the installer projects
  # selection.include_local_ai onto this). Everything AI hangs off this flag so
  # the AI-off golden path pulls in ZERO AI dependencies.
  aiOn = cfg.roles.aiStack.enable;
in {
  # The AQ-OS Workstation golden profile: one super-tuned, hardware-adaptive path
  # for professional development + gaming, with OPTIONAL local AI. It is a curated
  # resolved plan over the modular mySystem.* engine — experts retain every role
  # toggle and direct-Nix option; the installer just projects a good default here.
  config = lib.mkIf (cfg.profile == "aqos-workstation") (lib.mkMerge [
    {
      # ── Golden base: professional dev + gaming (always on) ──────────────────
      mySystem.roles.desktop.enable = lib.mkDefault true;
      mySystem.roles.cppDev.enable = lib.mkDefault true;
      mySystem.roles.gaming.enable = lib.mkDefault true;
      mySystem.roles.virtualization.enable = lib.mkDefault true;
      # OPTIONAL local AI — OFF by default, never on the install critical path.
      # Flip to true (or via installer include_local_ai) to opt in; the guarded
      # block below is the ONLY place AI dependencies are introduced.
      mySystem.roles.aiStack.enable = lib.mkDefault false;

      mySystem.monitoring.enable = lib.mkDefault true;
      mySystem.localhostIsolation.enable = lib.mkDefault true;
      mySystem.profileData.flatpakApps = lib.mkDefault flatpakProfiles.ai_workstation;
      mySystem.profileData.systemPackageNames = lib.mkDefault profilePackages.aqos-workstation;

      # ── Workstation kernel + security posture ───────────────────────────────
      # Track the newest supported stable kernel for workstation-class workloads.
      mySystem.kernel.track = lib.mkDefault "latest-stable";
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
      mySystem.kernel.cveTracking = {
        enable = lib.mkDefault true;
        autoScan = lib.mkDefault true;
      };
      mySystem.security.crowdsec = {
        enable = lib.mkDefault true;
        watchSshd = lib.mkDefault true;
        watchNginx = lib.mkDefault true;
        # Firewall bouncer only when secrets are configured (needs a SOPS API key).
        enableFirewallBouncer = lib.mkDefault config.mySystem.secrets.enable;
        apiKeyFile =
          lib.mkIf config.mySystem.secrets.enable
          (lib.mkDefault "/run/secrets/${config.mySystem.secrets.names.crowdsecBouncerApiKey}");
      };
      mySystem.secureboot.enable = lib.mkDefault true;

      # ── Gaming ──────────────────────────────────────────────────────────────
      programs.gamemode.enable = lib.mkDefault true;

      # ── Hardware-adaptive polish ────────────────────────────────────────────
      # Vendor-specific CPU/GPU/storage tuning is delegated to nix/modules/hardware/*
      # (they gate on mySystem.hardware.{cpuVendor,gpuVendor,storageType,systemRamGb,
      # isMobile}, which the installer sets from the detected hardware). When local
      # AI is enabled, model sizing is delegated to the versioned AI-fit policy —
      # no fixed model/threshold is hardcoded in this profile.
      hardware.enableRedistributableFirmware = lib.mkDefault true;
      services.fwupd.enable = lib.mkDefault true;

      # Password-free power management for the wheel group (COSMIC/desktop).
      security.polkit.extraConfig = ''
        polkit.addRule(function(action, subject) {
          if ((action.id == "org.freedesktop.UPower.PowerProfiles.switch-profile" ||
               action.id == "org.freedesktop.UPower.PowerProfiles.hold-profile" ||
               action.id == "org.freedesktop.login1.suspend" ||
               action.id == "org.freedesktop.login1.hibernate" ||
               action.id == "org.freedesktop.login1.power-off") &&
              subject.isInGroup("wheel")) {
            return polkit.Result.YES;
          }
        });
      '';

      # Developer fonts baseline.
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

      # Modern-laptop touchpad defaults (clickfinger avoids ClickPad mis-clicks).
      services.libinput.touchpad = {
        middleEmulation = lib.mkDefault false;
        clickMethod = lib.mkDefault "clickfinger";
        disableWhileTyping = lib.mkDefault true;
        tapping = lib.mkDefault true;
        scrollMethod = lib.mkDefault "twofinger";
        naturalScrolling = lib.mkDefault false;
      };
    }

    # ── OPTIONAL local AI (only when the operator opts in) ─────────────────────
    # This is the ONLY block that introduces AI dependencies. With aiOn = false
    # the golden path is a clean pro-dev/gaming system with no AI stack, model,
    # coordinator, switchboard, or network requirement. The stable core inference
    # stack only (aiStack role brings llama.cpp + AIDB + coordinator); the
    # experimental Foundation-C capability-lease/execution-cell activations are
    # intentionally NOT part of the blessed default.
    (lib.mkIf aiOn {
      mySystem.mcpServers.enable = lib.mkDefault true;
      mySystem.aiStack.switchboard.enable = lib.mkDefault true;
      mySystem.monitoring.commandCenter.enable = lib.mkDefault true;
    })
  ]);
}
