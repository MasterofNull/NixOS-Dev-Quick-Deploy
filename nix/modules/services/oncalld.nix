# nix/modules/services/oncalld.nix
# Autonomous On-Call Incident Daemon (`aq-oncalld`, Slice W2-S3)
{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.services.aiOncalld;
in {
  options.services.aiOncalld = {
    enable = mkEnableOption "Autonomous On-Call Incident Daemon (aq-oncalld)";

    stateDir = mkOption {
      type = types.str;
      default = "/var/lib/aq-oncalld";
      description = "Directory where aq-oncalld persists incident records and triage database.";
    };

    worktreesDir = mkOption {
      type = types.str;
      default = "/var/lib/aq-oncalld/worktrees";
      description = "Directory where sandboxed incident reproduction worktrees are provisioned.";
    };

    interval = mkOption {
      type = types.int;
      default = 60;
      description = "Interval in seconds between oncalld autonomous incident scanning passes.";
    };
  };

  config = mkIf cfg.enable {
    systemd.tmpfiles.rules = [
      "d '${cfg.stateDir}' 0750 hyperd users - -"
      "d '${cfg.worktreesDir}' 0750 hyperd users - -"
    ];

    security.apparmor.policies."aq-oncalld" = mkIf config.security.apparmor.enable {
      state = "complain";
      profile = ''
        #include <tunables/global>

        profile aq-oncalld flags=(attach_disconnected,mediate_deleted) {
          #include <abstractions/base>
          #include <abstractions/nameservice>

          /nix/store/** mr,
          /run/current-system/** mr,
          /usr/bin/** rix,
          /bin/** rix,

          # Deny secrets access per OWASP Agentic Top 10
          deny /run/secrets/** rwmklx,
          deny /etc/secrets/** rwmklx,
          deny @{HOME}/.ssh/** rwmklx,
          deny @{HOME}/.gnupg/** rwmklx,

          # Storage paths
          ${cfg.stateDir}/** rwk,
          ${cfg.worktreesDir}/** rwk,
          /tmp/** rwk,

          /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/** r,
        }
      '';
    };

    systemd.services.ai-oncalld = {
      description = "Autonomous On-Call Incident Daemon (aq-oncalld)";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        User = "hyperd";
        Group = "users";
        ExecStart = "${pkgs.python3}/bin/python3 scripts/ai/aq-oncalld --daemon --interval ${toString cfg.interval} --state-dir ${cfg.stateDir}";
        WorkingDirectory = "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy";
        Restart = "on-failure";
        RestartSec = "10s";

        # Resource limits & isolation (Rule 14 & Rule 13)
        MemoryMax = "2G";
        CPUQuota = "100%";
        ProtectHome = "read-only";
        ReadWritePaths = [
          cfg.stateDir
          cfg.worktreesDir
        ];
      };
    };
  };
}
