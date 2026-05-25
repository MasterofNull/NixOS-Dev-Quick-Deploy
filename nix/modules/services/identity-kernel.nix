{
  lib,
  config,
  ...
}:
# ---------------------------------------------------------------------------
# Identity Kernel — Phase 16
#
# Injects identity kernel env vars into the ai-hybrid-coordinator service so
# the persistent narrative engine, value constitution, and checkpoint service
# start automatically inside the coordinator process.
#
# Activated when:
#   mySystem.roles.aiStack.enable = true
#   mySystem.mcpServers.enable = true
#   mySystem.aiStack.identityKernel.enable = true
#
# No separate systemd unit is needed: the checkpoint thread runs inside the
# hybrid coordinator via identity_handlers.init().
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  mcp = cfg.mcpServers;
  ai = cfg.aiStack;
  ik = ai.identityKernel;

  active = cfg.roles.aiStack.enable && mcp.enable && ik.enable;
  aiGroup = "ai-stack";
  hybridUser = "ai-hybrid";

  repoSource =
    if mcp.flakeRepoPath != null
    then mcp.flakeRepoPath
    else
      builtins.path {
        path = mcp.repoPath;
        name = "nixos-quick-deploy-repo";
      };

  journalDir = ik.journalPath;
  journalFile = "${journalDir}/journal.jsonl";
  checkpointFile = "${journalDir}/checkpoint.json";

  constitutionFile =
    if ik.valueConstitutionFile != ""
    then ik.valueConstitutionFile
    else "${toString repoSource}/config/identity-values.yaml";
in
  lib.mkIf active {
    # Ensure the identity state is writable by the coordinator service even when
    # older mutable files were created by the primary human operator.
    systemd.tmpfiles.rules = [
      "d ${journalDir} 0750 ${hybridUser} ${aiGroup} - -"
      "z ${journalDir} 0750 ${hybridUser} ${aiGroup} - -"
      "f ${journalFile} 0660 ${hybridUser} ${aiGroup} - -"
      "z ${journalFile} 0660 ${hybridUser} ${aiGroup} - -"
      "f ${checkpointFile} 0660 ${hybridUser} ${aiGroup} - -"
      "z ${checkpointFile} 0660 ${hybridUser} ${aiGroup} - -"
    ];

    # Inject identity kernel env vars into the hybrid coordinator service.
    systemd.services.ai-hybrid-coordinator.serviceConfig.Environment = lib.mkAfter [
      "IDENTITY_JOURNAL_PATH=${journalFile}"
      "IDENTITY_CHECKPOINT_PATH=${journalDir}"
      "IDENTITY_CHECKPOINT_INTERVAL_SECONDS=${toString ik.checkpointIntervalSeconds}"
      "IDENTITY_VALUE_CONSTITUTION=${constitutionFile}"
    ];
  }
