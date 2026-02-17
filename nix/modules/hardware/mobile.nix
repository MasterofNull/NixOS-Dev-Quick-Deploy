{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  mobile = cfg.hardware.isMobile;
in
{
  # Mobile / laptop platform settings.
  # Gates on mySystem.hardware.isMobile so desktop deployments are unaffected.

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

  # Battery charge thresholds (ThinkPad-specific via tp_smapi / tpacpi-bat).
  # These are no-ops on non-ThinkPad hardware.
  services.tlp.settings = lib.mkIf (mobile && false) {  # disabled — tlp conflicts with ppd
    START_CHARGE_THRESH_BAT0 = 20;
    STOP_CHARGE_THRESH_BAT0  = 80;
  };

  # Kernel parameters for mobile power management.
  boot.kernelParams = lib.mkIf mobile (lib.mkAfter [
    "quiet"    # Cleaner boot on laptop screens
    "splash"
  ]);
}
