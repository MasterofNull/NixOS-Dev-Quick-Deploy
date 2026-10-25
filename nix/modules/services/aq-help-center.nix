{
  lib,
  config,
  pkgs,
  ...
}: let
  cfg = config.mySystem;
  ports = cfg.ports;
in {
  options.mySystem.services.helpCenter = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable the AQ-OS SOTA Help Center, user manual, and training service.";
    };
    port = lib.mkOption {
      type = lib.types.port;
      default = 8890;
      description = "Port to serve AQ-OS Help Center.";
    };
  };

  config = lib.mkIf (cfg.services.helpCenter.enable) {
    systemd.services.aq-help-center = {
      description = "AQ-OS Interactive SOTA Help Center & Training Manual";
      wantedBy = ["multi-user.target"];
      after = ["network.target"];
      serviceConfig = {
        Type = "simple";
        User = cfg.primaryUser;
        WorkingDirectory = "${cfg.mcpServers.repoPath}";
        ExecStart = "${pkgs.python3}/bin/python3 ${cfg.mcpServers.repoPath}/scripts/ai/aq-help-center --port ${toString cfg.services.helpCenter.port} --no-open";
        Restart = "on-failure";
        RestartSec = "5s";
      };
    };
  };
}
