{
  lib,
  pkgs,
  config,
  ...
}: let
  cfg = config.mySystem.deployment.fsIntegrityMonitor;
  interval = toString cfg.intervalMinutes;

  fsIntegrityCheck = pkgs.writeShellApplication {
    name = "fs-integrity-check";
    runtimeInputs = with pkgs; [
      coreutils
      gnugrep
      util-linux
      systemd
    ];
    # Single source: the repo script (also exercised by tests/unit/fs-integrity-helpers.bats).
    text = builtins.readFile ../../../scripts/health/fs-integrity-check.sh;
  };
in {
  config = lib.mkIf cfg.enable {
    environment.systemPackages = [fsIntegrityCheck];

    systemd.services.fs-integrity-monitor = {
      description = "Filesystem Integrity Monitor";
      after = ["multi-user.target"];
      onFailure = ["deploy-guardrail-alert@%n.service"];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${fsIntegrityCheck}/bin/fs-integrity-check";
        # Bounded contract: the check streams logs through grep and needs only a few MB;
        # a regression must fail visibly here, not consume host RAM (27 GB budget).
        MemoryMax = "512M";
        MemorySwapMax = "0";
        TimeoutSec = 900;
        Nice = 19;
        IOSchedulingClass = "idle";
        CPUSchedulingPolicy = "idle";
      };
    };

    systemd.timers.fs-integrity-monitor = {
      description = "Periodic filesystem integrity monitor";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnBootSec = "3min";
        OnUnitActiveSec = "${interval}min";
        RandomizedDelaySec = "2min";
        Persistent = true;
        Unit = "fs-integrity-monitor.service";
      };
    };
  };
}
