# Declarative NixOS module for SOTA Proactive Durable Agent Sweeper
# Provides scheduled cron-ticked sweeps for SOTA software factory intelligence
{
  lib,
  config,
  pkgs,
  ...
}:
with lib; let
  cfg = config.mySystem.aiStack.durableSweeper;
  repoPath = config.mySystem.mcpServers.repoPath;
  sweeperScript = "${repoPath}/scripts/ai/aq-durable-sweeper";

  tickRunner = pkgs.writeShellScript "aq-durable-sweeper-tick" ''
    set -u
    export PATH="/run/current-system/sw/bin:/run/wrappers/bin:$PATH"
    if [ -x "${sweeperScript}" ]; then
      exec ${pkgs.python3}/bin/python3 "${sweeperScript}" tick
    fi
  '';
in {
  options.mySystem.aiStack.durableSweeper = {
    enable = mkOption {
      type = types.bool;
      default = true;
      description = ''
        Enable proactive durable agent sweeper daemon and scheduled cron timers.
        Maintains state checkpoints across host reboots and surfaces frontier intelligence.
      '';
    };

    intervalMinutes = mkOption {
      type = types.ints.positive;
      default = 60;
      description = "Interval in minutes between autonomous intelligence sweeps.";
    };
  };

  config = mkIf cfg.enable {
    systemd.user.services.aq-durable-sweeper = {
      description = "AQ-OS Proactive Durable Agent Sweeper & Signal Classifier";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${tickRunner}";
      };
    };

    systemd.user.timers.aq-durable-sweeper = {
      description = "Scheduled timer for proactive durable agent sweeps";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnBootSec = "5m";
        OnUnitActiveSec = "${toString cfg.intervalMinutes}m";
        Unit = "aq-durable-sweeper.service";
      };
    };
  };
}
