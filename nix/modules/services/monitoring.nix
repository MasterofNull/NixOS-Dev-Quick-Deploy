{ lib, config, ... }:
let
  cfg = config.mySystem;
  mon = cfg.monitoring;
  mcp = cfg.mcpServers;
  ai = cfg.aiStack;
in
{
  config = lib.mkIf mon.enable {
    services.prometheus = {
      enable = true;
      port = mon.prometheusPort;
      scrapeConfigs = [
        {
          job_name = "node";
          static_configs = [{ targets = [ "127.0.0.1:${toString mon.nodeExporterPort}" ]; }];
        }
      ] ++ lib.optionals (cfg.roles.aiStack.enable && mcp.enable && ai.backend == "llamacpp") [
        {
          job_name = "aidb";
          metrics_path = "/metrics";
          static_configs = [{ targets = [ "127.0.0.1:${toString mcp.aidbPort}" ]; }];
        }
        {
          job_name = "hybrid-coordinator";
          metrics_path = "/metrics";
          static_configs = [{ targets = [ "127.0.0.1:${toString mcp.hybridPort}" ]; }];
        }
      ];
    };

    services.prometheus.exporters.node = {
      enable = true;
      port = mon.nodeExporterPort;
      enabledCollectors = [
        "cpu"
        "diskstats"
        "filesystem"
        "loadavg"
        "meminfo"
        "netdev"
        "processes"
        "systemd"
      ];
    };

    networking.firewall.allowedTCPPorts = lib.mkIf mon.listenOnLan [
      mon.prometheusPort
      mon.nodeExporterPort
    ];
  };
}
