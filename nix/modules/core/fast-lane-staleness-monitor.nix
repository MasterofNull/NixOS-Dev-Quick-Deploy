# Split-channel packaging (.agents/plans/split-channel-packaging/DESIGN.md
# sc-2): declarative timer for the fast-lane package staleness checker
# (scripts/health/fast-lane-staleness-check.py). NOTIFY-ONLY — this service
# never runs `nix flake update` or a rebuild; it only reads flake.lock +
# does read-only `nix eval` against the live nixpkgs-unstable ref and
# writes a status JSON + attention-queue alert. Mirrors the
# disk-health-monitor.nix / ai-stack-health-monitor.py pattern already used
# elsewhere in this harness.
{
  lib,
  pkgs,
  config,
  ...
}: let
  cfg = config.mySystem;
  fcfg = cfg.deployment.fastLaneStaleness;
  interval = toString fcfg.intervalMinutes;
  checkerPython = pkgs.python3; # stdlib only — json/subprocess/dataclasses/pathlib/time
in {
  config = lib.mkIf fcfg.enable {
    systemd.services.fast-lane-staleness-check = {
      description = "Fast-lane (nixpkgs-unstable) package staleness checker — notify-only";
      after = ["network-online.target"];
      wants = ["network-online.target"];
      serviceConfig = {
        Type = "oneshot";
        User = cfg.primaryUser;
        WorkingDirectory = cfg.mcpServers.repoPath;
        Environment = [
          "REPO_ROOT=${cfg.mcpServers.repoPath}"
          "FAST_LANE_PIN_STALE_DAYS=${toString fcfg.maxPinAgeDays}"
          "PATH=/run/current-system/sw/bin:/run/wrappers/bin"
        ];
        ExecStart = let
          script = "${cfg.mcpServers.repoPath}/scripts/health/fast-lane-staleness-check.py";
        in "${checkerPython}/bin/python3 ${script}";
        StandardOutput = "journal";
        StandardError = "journal";
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        # Status JSON + attention-queue writes both live under .agents/ in the repo.
        ReadWritePaths = ["${cfg.mcpServers.repoPath}/.agents"];
        PrivateTmp = true;
        TimeoutStartSec = "180";
        MemoryMax = "256M";
      };
    };

    systemd.timers.fast-lane-staleness-check = {
      description = "Fast-lane staleness checker timer";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnBootSec = "10min";
        OnUnitActiveSec = "${interval}min";
        RandomizedDelaySec = "10min";
        Persistent = true;
        Unit = "fast-lane-staleness-check.service";
      };
    };
  };
}
