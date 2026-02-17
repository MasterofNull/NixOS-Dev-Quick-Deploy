{ lib, config, ... }:
let
  cfg = config.mySystem;
  skipRootFsck = cfg.deployment.rootFsckMode == "skip";
in
{
  config = {
    # Avoid initrd lockout loops: keep emergency shell accessible for local recovery.
    boot.initrd.systemd.emergencyAccess = lib.mkDefault cfg.deployment.initrdEmergencyAccess;

    # Recovery-only escape hatch for hosts stuck in fsck failure loops.
    fileSystems."/".noCheck = lib.mkIf skipRootFsck (lib.mkForce true);
    boot.kernelParams = lib.mkIf skipRootFsck (lib.mkAfter [
      "fsck.mode=skip"
      "fsck.repair=no"
    ]);

  };
}
