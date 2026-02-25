{ lib, config, ... }:
let
  cfg = config.mySystem;
  logCfg = cfg.logging;
  auditWatchRules = map (path: "-w ${path} -p rwxa -k ${logCfg.audit.key}") logCfg.audit.watchPaths;
  remoteSyslogConfig = ''
    # Keep a disk-backed queue so outages on the remote endpoint do not
    # drop security/compliance events.
    action(
      type="omfwd"
      target="${logCfg.remoteSyslog.host}"
      port="${toString logCfg.remoteSyslog.port}"
      protocol="${logCfg.remoteSyslog.protocol}"
      queue.type="LinkedList"
      queue.filename="forward-remote-syslog"
      queue.maxdiskspace="10g"
      queue.saveonshutdown="on"
      action.resumeRetryCount="-1"
    )
  '';
in
{
  options.mySystem.logging = {
    journald = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Enable declarative journald retention policy management.";
      };

      storage = lib.mkOption {
        type = lib.types.enum [ "persistent" "volatile" "auto" "none" ];
        default = "persistent";
        description = "journald storage backend.";
      };

      systemMaxUse = lib.mkOption {
        type = lib.types.str;
        default = "2G";
        description = "Maximum disk space used by persistent journal data.";
      };

      runtimeMaxUse = lib.mkOption {
        type = lib.types.str;
        default = "512M";
        description = "Maximum disk space used by runtime journal data.";
      };

      maxFileSec = lib.mkOption {
        type = lib.types.str;
        default = "1month";
        description = "Maximum age of a single journal file before rotation.";
      };

      maxRetentionSec = lib.mkOption {
        type = lib.types.str;
        default = "14day";
        description = "Maximum retention period for journal entries.";
      };
    };

    loki = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Enable local Loki log aggregation service.";
      };

      promtailEnable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Enable Promtail to scrape systemd journal into Loki.";
      };

      listenAddress = lib.mkOption {
        type = lib.types.str;
        default = "127.0.0.1";
        description = "Loki HTTP listen address.";
      };

      port = lib.mkOption {
        type = lib.types.port;
        default = 3100;
        description = "Loki HTTP listen port.";
      };

      promtailPort = lib.mkOption {
        type = lib.types.port;
        default = 9080;
        description = "Promtail HTTP listen port.";
      };

      exposeOnLan = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Expose Loki/Promtail ports on LAN.";
      };
    };
  };

  config = lib.mkMerge [
    (lib.mkIf logCfg.journald.enable {
      services.journald.extraConfig = ''
        Storage=${logCfg.journald.storage}
        SystemMaxUse=${logCfg.journald.systemMaxUse}
        RuntimeMaxUse=${logCfg.journald.runtimeMaxUse}
        MaxFileSec=${logCfg.journald.maxFileSec}
        MaxRetentionSec=${logCfg.journald.maxRetentionSec}
        Compress=yes
        Seal=yes
      '';
    })

    (lib.mkIf logCfg.loki.enable {
      services.loki = {
        enable = true;
        configuration = {
          auth_enabled = false;
          server = {
            http_listen_address = logCfg.loki.listenAddress;
            http_listen_port = logCfg.loki.port;
          };
          common = {
            path_prefix = "/var/lib/loki";
            replication_factor = 1;
            ring = {
              instance_addr = "127.0.0.1";
              kvstore.store = "inmemory";
            };
            storage.filesystem = {
              chunks_directory = "/var/lib/loki/chunks";
              rules_directory = "/var/lib/loki/rules";
            };
          };
          schema_config.configs = [
            {
              from = "2024-01-01";
              store = "tsdb";
              object_store = "filesystem";
              schema = "v13";
              index = {
                prefix = "index_";
                period = "24h";
              };
            }
          ];
        };
      };
    })

    (lib.mkIf (logCfg.loki.enable && logCfg.loki.promtailEnable) {
      services.promtail = {
        enable = true;
        configuration = {
          server = {
            http_listen_address = "127.0.0.1";
            http_listen_port = logCfg.loki.promtailPort;
            grpc_listen_port = 0;
          };
          positions.filename = "/var/lib/promtail/positions.yaml";
          clients = [
            { url = "http://${logCfg.loki.listenAddress}:${toString logCfg.loki.port}/loki/api/v1/push"; }
          ];
          scrape_configs = [
            {
              job_name = "systemd-journal";
              journal = {
                path = "/var/log/journal";
                max_age = "12h";
                labels = {
                  job = "systemd-journal";
                  host = cfg.hostName;
                };
              };
              relabel_configs = [
                {
                  source_labels = [ "__journal__systemd_unit" ];
                  target_label = "unit";
                }
                {
                  source_labels = [ "__journal_priority_keyword" ];
                  target_label = "level";
                }
              ];
            }
          ];
        };
      };
    })

    (lib.mkIf (logCfg.loki.enable && logCfg.loki.exposeOnLan) {
      networking.firewall.allowedTCPPorts =
        [ logCfg.loki.port ]
        ++ lib.optional (logCfg.loki.promtailEnable) logCfg.loki.promtailPort;
    })

    (lib.mkIf logCfg.audit.enable {
      # Ensure watched paths exist before auditctl loads rules.
      # auditctl fails the unit when a -w target path is missing.
      systemd.tmpfiles.rules =
        map (path: "d ${path} 0750 root root -") logCfg.audit.watchPaths;

      # When audit is already immutable (enabled=2), reloading rules during
      # switch returns non-zero even though policy enforcement is active.
      # Treat these auditctl statuses as non-fatal to keep switch idempotent.
      systemd.services.audit-rules-nixos.serviceConfig.SuccessExitStatus = [ "1" "255" ];

      security.audit = {
        enable = true;
        # Keep rules limited to watch declarations; NixOS appends control
        # directives (including final -e) when rendering audit.rules.
        # Appending our own -e 2 here conflicts with the generated tail and can
        # produce auditctl load errors during boot.
        rules = auditWatchRules;
        backlogLimit = 8192;
      };
      security.auditd.enable = true;
    })

    (lib.mkIf logCfg.remoteSyslog.enable {
      assertions = [
        {
          assertion = logCfg.remoteSyslog.host != "";
          message = "mySystem.logging.remoteSyslog.host must be set when remote syslog forwarding is enabled.";
        }
      ];

      services.rsyslogd = {
        enable = true;
        extraConfig = remoteSyslogConfig;
      };

      # Route journal entries into syslog forwarding pipeline.
      services.journald.extraConfig = lib.mkAfter ''
        ForwardToSyslog=yes
      '';
    })
  ];
}
