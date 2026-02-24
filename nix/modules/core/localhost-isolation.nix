{ lib, config, ... }:
let
  cfg = config.mySystem;
  ports = cfg.ports;

  protectedPorts = lib.unique [
    ports.postgres
    ports.redis
    ports.qdrantHttp
    ports.qdrantGrpc
    ports.mcpAidb
    ports.mcpHybrid
    ports.mcpRalph
  ];

  portSet = lib.concatStringsSep ", " (map toString protectedPorts);
  gidSet = lib.concatStringsSep ", " (map toString cfg.localhostIsolation.allowedServiceGids);
in
{
  config = lib.mkIf cfg.localhostIsolation.enable {
    networking.nftables.enable = true;

    # Localhost service segmentation for host-network mode.
    # Restricts connection attempts to protected ports to service groups only.
    networking.nftables.ruleset = lib.mkAfter ''
      table inet ai_localhost_isolation {
        chain output {
          type filter hook output priority 0; policy accept;
          oifname "lo" tcp dport { ${portSet} } meta skgid != { ${gidSet} } counter reject with icmpx type admin-prohibited
        }
      }
    '';
  };
}
