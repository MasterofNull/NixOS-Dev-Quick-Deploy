# Workflow-deviation receipt broker — C1B, default-OFF.
{ config, lib, pkgs, ... }:
with lib; let
  cfg = config.mySystem.aiStack.workflowDeviationBroker;
  primaryUser = config.mySystem.primaryUser;
  primaryGroup = attrByPath ["users" "users" primaryUser "group"] "users" config;
  primaryUid = attrByPath ["users" "users" primaryUser "uid"] null config;
  mcp = config.mySystem.mcpServers;
  brokerPython = pkgs.python3;
  brokerBundle = pkgs.runCommand "aq-workflow-deviation-broker-bundle" {} ''
    mkdir -p $out
    cp ${../../../scripts/ai/lib/workflow_deviation.py} $out/workflow_deviation.py
    cp ${../../../scripts/ai/lib/workflow_deviation_io.py} $out/workflow_deviation_io.py
    cp ${../../../scripts/ai/lib/workflow_deviation_transport.py} $out/workflow_deviation_transport.py
  '';
in {
  options.mySystem.aiStack.workflowDeviationBroker = {
    enable = mkOption { type = types.bool; default = false; description = "Enable the C1B receipt broker socket and service. Default-OFF pending C2 Service Coverage."; };
    socketPath = mkOption { type = types.str; default = "/run/aq-workflow-deviation-broker/control.sock"; description = "Systemd-owned AF_UNIX-only broker socket."; };
    receiptPath = mkOption { type = types.str; default = "${mcp.dataDir}/hybrid/telemetry/workflow-deviations.jsonl"; description = "C1A-compatible append-only receipt log."; };
  };

  config = mkIf cfg.enable {
    assertions = [{
      assertion = primaryUid != null;
      message = "workflowDeviationBroker requires an explicit numeric primary-user UID for SO_PEERCRED verification.";
    }];
    users.groups.aq-workflow-deviation-clients = {};
    users.users.${primaryUser}.extraGroups = mkAfter ["aq-workflow-deviation-clients"];
    systemd.tmpfiles.rules = [
      "d ${builtins.dirOf cfg.socketPath} 0750 ${primaryUser} aq-workflow-deviation-clients -"
    ];
    systemd.sockets.aq-workflow-deviation-broker = {
      description = "C1B workflow-deviation receipt broker socket (default-OFF)";
      wantedBy = ["sockets.target"];
      socketConfig = {
        ListenStream = cfg.socketPath;
        SocketUser = primaryUser;
        SocketGroup = "aq-workflow-deviation-clients";
        SocketMode = "0660";
        Accept = false;
        RemoveOnStop = true;
      };
    };
    systemd.services.aq-workflow-deviation-broker = {
      description = "C1B workflow-deviation receipt broker (socket-activated, default-OFF)";
      requires = ["aq-workflow-deviation-broker.socket"];
      after = ["aq-workflow-deviation-broker.socket"];
      serviceConfig = {
        Type = "simple";
        ExecStart = "${brokerPython}/bin/python3 ${brokerBundle}/workflow_deviation_transport.py";
        User = primaryUser;
        Group = primaryGroup;
        Environment = [
          "AQ_WORKFLOW_DEVIATION_LOG_PATH=${cfg.receiptPath}"
          "AQ_WORKFLOW_DEVIATION_BROKER_SOCKET=${cfg.socketPath}"
          "AQ_WORKFLOW_DEVIATION_BROKER_UID=${toString primaryUid}"
        ];
        Restart = "on-failure";
        RestartSec = "5s";
        StandardError = "journal";
        NoNewPrivileges = true;
        CapabilityBoundingSet = "";
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        RestrictSUIDSGID = true;
        LockPersonality = true;
        RestrictAddressFamilies = ["AF_UNIX"];
        ReadWritePaths = [mcp.dataDir];
      };
    };
  };
}
