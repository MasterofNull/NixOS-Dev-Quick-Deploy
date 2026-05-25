{
  lib,
  config,
  ...
}:
# ---------------------------------------------------------------------------
# World Model: Predictive Context Warming — Phase 20
#
# Injects world model env vars into the ai-hybrid-coordinator service.
# The ai-context-warmer.timer/service is defined in ai-stack.nix and also
# guarded by mySystem.aiStack.worldModel.enable.
#
# Activated when:
#   mySystem.roles.aiStack.enable = true
#   mySystem.mcpServers.enable = true
#   mySystem.aiStack.worldModel.enable = true
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  mcp = cfg.mcpServers;
  ai = cfg.aiStack;
  wm = ai.worldModel;

  active = cfg.roles.aiStack.enable && mcp.enable && wm.enable;
in
  lib.mkIf active {
    # Inject world model env vars into the hybrid coordinator service.
    systemd.services.ai-hybrid-coordinator.serviceConfig.Environment = lib.mkAfter [
      "WORLD_MODEL_ENABLED=true"
      "WORLD_MODEL_WARM_THRESHOLD=${wm.warmThreshold}"
      "WORLD_MODEL_MAX_WARM_QUERIES=${toString wm.maxWarmQueriesPerRun}"
      "WORLD_MODEL_PATTERN_RETENTION_DAYS=${toString wm.patternRetentionDays}"
    ];
  }
