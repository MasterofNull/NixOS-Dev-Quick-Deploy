{
  lib,
  config,
  pkgs,
  ...
}: let
  cfg = config.mySystem;
  # Active when the hardware flag OR the explicit role toggle is set.
  # roles.mobile.enable lets users force mobile power management on machines
  # that are not auto-detected as laptops (e.g. a NUC running on battery).
  mobile = cfg.hardware.isMobile || cfg.roles.mobile.enable;
in {
  # Mobile / laptop platform settings.
  # Gates on hardware.isMobile OR roles.mobile.enable.

  powerManagement = lib.mkIf mobile {
    enable = lib.mkDefault true;
  };

  # power-profiles-daemon: modern kernel-integrated power profile switching.
  # Preferred over TLP on kernels 5.12+ with AMD P-state or Intel EPP support.
  # TLP is disabled here to avoid conflicts (they must not run simultaneously).
  services.power-profiles-daemon.enable = lib.mkIf mobile (lib.mkDefault true);
  services.tlp.enable = lib.mkIf mobile (lib.mkForce false);

  # Lid close / power-button behaviour (safe defaults for laptops).
  services.logind.settings = lib.mkIf mobile {
    Login = {
      HandleLidSwitch = lib.mkDefault "suspend";
      HandleLidSwitchExternalPower = lib.mkDefault "suspend";
      HandleLidSwitchDocked = lib.mkDefault "ignore";
      HandlePowerKey = lib.mkDefault "suspend";
      HandleSuspendKey = lib.mkDefault "suspend";
      IdleAction = lib.mkDefault "suspend";
      IdleActionSec = lib.mkDefault "20min";
    };
  };

  # Phase 5.3.1 — Battery charge thresholds via thinkpad-acpi sysfs.
  # Works with kernels 5.9+ and the thinkpad_acpi module. The systemd service
  # conditions on the sysfs node existing, so it is a no-op on non-ThinkPad
  # hardware (desktop, SBC, non-ThinkPad laptops).
  # TLP is disabled above (conflicts with power-profiles-daemon); thresholds
  # are written directly to /sys/class/power_supply/BAT*/charge_control_*.
  #
  # Configurable via mySystem.hardware.battery.* options:
  # - chargeThresholds.enable: Master toggle (false = charge to 100%)
  # - chargeThresholds.startThreshold: When to start charging (default: 20%)
  # - chargeThresholds.stopThreshold: When to stop charging (default: 80%)
  # - conservationMode.enable: Override for always-plugged-in use (default: false)
  # - conservationMode.startThreshold: Conservation start (default: 50%)
  # - conservationMode.stopThreshold: Conservation stop (default: 60%)
  #
  # COSMIC Desktop Integration:
  # When COSMIC desktop is active (roles.desktop.enable = true), this service
  # is disabled to avoid conflicts with COSMIC's built-in battery threshold
  # management (Settings → Power → Battery Lifespan). Use the COSMIC GUI or
  # scripts/utils/battery-toggle.sh for runtime control instead.
  systemd.services.battery-charge-thresholds = lib.mkIf (mobile && !cfg.roles.desktop.enable) {
    description = "Set battery charge start/stop thresholds via thinkpad-acpi";
    wantedBy = ["multi-user.target" "suspend.target"];
    after = ["multi-user.target"];
    # Only run when the sysfs interface is present — no-op on non-ThinkPad.
    unitConfig.ConditionPathExists = "/sys/class/power_supply/BAT0/charge_control_start_threshold";
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      ExecStart = pkgs.writeShellScript "battery-thresholds" ''
        set -euo pipefail

        # Determine which thresholds to use
        if ${lib.boolToString cfg.hardware.battery.conservationMode.enable}; then
          start_thresh=${toString cfg.hardware.battery.conservationMode.startThreshold}
          stop_thresh=${toString cfg.hardware.battery.conservationMode.stopThreshold}
        elif ${lib.boolToString cfg.hardware.battery.chargeThresholds.enable}; then
          start_thresh=${toString cfg.hardware.battery.chargeThresholds.startThreshold}
          stop_thresh=${toString cfg.hardware.battery.chargeThresholds.stopThreshold}
        else
          # Thresholds disabled — allow full 100% charge
          start_thresh=0
          stop_thresh=100
        fi

        for bat in /sys/class/power_supply/BAT*/; do
          start="''${bat}charge_control_start_threshold"
          stop="''${bat}charge_control_end_threshold"
          [[ -w "$start" ]] && echo "$start_thresh" > "$start"
          [[ -w "$stop"  ]] && echo "$stop_thresh" > "$stop"
        done
      '';
    };
  };

  # Kernel parameters for mobile power management.
  boot.kernelParams = lib.mkIf mobile (lib.mkAfter [
    "quiet" # Cleaner boot on laptop screens
    "splash"
  ]);
}
