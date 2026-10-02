# Tiered unattended update pipeline (slice U3, tiered-auto-update FREEZE.md).
# DISABLED unless mySystem.autoUpdate.enable. All decisions live in
# scripts/maintenance/aq-auto-update (deterministic, no LLM); this module only
# schedules it as root:
#   - aq-auto-update-check: daily, notify-only (never builds or switches)
#   - aq-auto-update-run:   every 15 min inside Sun 02:00-04:00 UTC so the
#     15-minute idle lease can mature; the script itself re-checks the window,
#     so a Persistent catch-up after the window closes refuses to start.
{
  lib,
  pkgs,
  config,
  ...
}: let
  cfg = config.mySystem;
  acfg = cfg.autoUpdate;
  repo = cfg.mcpServers.repoPath;
  # Root executes a store snapshot taken at rebuild time, never the user-writable checkout;
  # repo helpers it calls run as the owner (AQ_AUTO_UPDATE_RUN_AS).
  script = ../../../scripts/maintenance/aq-auto-update;

  common = {
    after = ["network-online.target"];
    wants = ["network-online.target"];
    path = with pkgs; [
      python3
      git
      nix
      nixos-rebuild
      systemd
      util-linux
      coreutils
      gnugrep
      gawk
    ];
    environment = {
      AQ_AUTO_UPDATE_REPO = repo;
      AQ_AUTO_UPDATE_STATE_DIR = acfg.stateDir;
      AQ_AUTO_UPDATE_FLAKE_ATTR = acfg.flakeAttr;
      AQ_AUTO_UPDATE_RUN_AS = cfg.primaryUser;
      AQ_AUTO_UPDATE_LLAMA_URL = "http://127.0.0.1:${toString cfg.aiStack.llamaCpp.port}";
      AQ_AUTO_UPDATE_COORDINATOR_URL = "http://127.0.0.1:${toString cfg.ports.mcpHybrid}";
    };
  };
in {
  config = lib.mkIf acfg.enable {
    systemd.tmpfiles.rules = ["d ${acfg.stateDir} 0750 root root -"];

    systemd.services.aq-auto-update-check =
      common
      // {
        description = "aq-auto-update daily notify-only check";
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${pkgs.python3}/bin/python3 ${script} check";
          TimeoutStartSec = "10min";
        };
      };

    systemd.timers.aq-auto-update-check = {
      description = "aq-auto-update daily notify-only check";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnCalendar = "daily";
        Persistent = true;
        RandomizedDelaySec = "15min";
      };
    };

    # AQ_SUSPEND_CONTRACT: aq-auto-update-run
    systemd.services.aq-auto-update-run =
      common
      // {
        description = "aq-auto-update gated activation run (weekly window)";
        serviceConfig = {
          Type = "oneshot";
          # Sleep mid-run (llama stopped, switch in flight) is unsafe: hold an inhibitor for the run.
          ExecStart = "${pkgs.systemd}/bin/systemd-inhibit --what=sleep:shutdown:handle-lid-switch --who=aq-auto-update --why='system update in progress' --mode=block ${pkgs.python3}/bin/python3 ${script} run";
          # Build + switch + 300s health gate + rollback; never auto-restarted.
          TimeoutStartSec = "110min";
          Restart = "no";
        };
      };

    systemd.timers.aq-auto-update-run = {
      description = "aq-auto-update activation attempts inside Sun 02:00-04:00 UTC";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnCalendar = "Sun *-*-* 02..03:00/15:00 UTC";
        # Persistent catch-up is safe: the script refuses to start outside the window.
        Persistent = true;
      };
    };
  };
}
