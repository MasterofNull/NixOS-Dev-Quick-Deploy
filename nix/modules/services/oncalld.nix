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

    repoDir = mkOption {
      type = types.str;
      default = "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy";
      description = "Owner checkout the daemon runs from. Read-only to the unit; used only as the clone source.";
    };

    cloneDir = mkOption {
      type = types.str;
      default = "/var/lib/aq-oncalld/repo";
      description = "Daemon-owned clone (git clone --no-hardlinks from repoDir, local fetch only). Repair worktrees are created from it, never from repoDir.";
    };

    repairs.enable = mkOption {
      type = types.bool;
      default = false;
      description = "Allow repair worktrees. Off: the daemon only records incidents (monitoring). Enable after the clone path is validated live (see evidence 2026-11-27-oncalld-activation.md).";
    };

    interval = mkOption {
      type = types.int;
      default = 60;
      description = "Interval in seconds between oncalld autonomous incident scanning passes.";
    };
  };

  config = mkIf cfg.enable {
    # The engine derives the worktree root from AQ_DELEGATION_DIR + "/worktrees"; keep them in step.
    assertions = [{
      assertion = cfg.cloneDir != cfg.repoDir;
      message = "services.aiOncalld.cloneDir must differ from repoDir (the owner checkout is never written).";
    } {
      assertion = baseNameOf cfg.worktreesDir == "worktrees";
      message = "services.aiOncalld.worktreesDir must end in /worktrees (engine appends it to AQ_DELEGATION_DIR).";
    }];

    systemd.tmpfiles.rules = [
      "d '${cfg.stateDir}' 0750 hyperd users - -"
      "d '${cfg.worktreesDir}' 0750 hyperd users - -"
      "d '${cfg.cloneDir}' 0750 hyperd users - -"
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
          ${cfg.cloneDir}/** rwk,

          ${cfg.repoDir}/** r,
        }
      '';
    };

    systemd.services.ai-oncalld = {
      description = "Autonomous On-Call Incident Daemon (aq-oncalld)";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      # git: clone + worktree creation; bubblewrap + bash: confined reproduction. Without git here
      # every claim failed with ENOENT 'git' (unit PATH is not the login PATH).
      path = [ pkgs.git pkgs.bubblewrap pkgs.bash ];
      environment = {
        AQ_DELEGATION_DIR = dirOf cfg.worktreesDir;
        AQ_ONCALL_CLONE_DIR = cfg.cloneDir;
        AQ_ONCALL_SOURCE_REPO = cfg.repoDir;
        AQ_ONCALL_REPAIRS = if cfg.repairs.enable then "1" else "0";
      };

      serviceConfig = {
        Type = "simple";
        User = "hyperd";
        Group = "users";
        ExecStart = "${pkgs.python3}/bin/python3 scripts/ai/aq-oncalld --daemon --interval ${toString cfg.interval} --state-dir ${cfg.stateDir}";
        WorkingDirectory = cfg.repoDir;
        Restart = "on-failure";
        RestartSec = "10s";

        # Resource limits & isolation (Rule 14 & Rule 13)
        MemoryMax = "2G";
        CPUQuota = "100%";
        ProtectHome = "read-only";
        ReadWritePaths = [
          cfg.stateDir
          cfg.worktreesDir
          cfg.cloneDir
        ];
      };
    };
  };
}
