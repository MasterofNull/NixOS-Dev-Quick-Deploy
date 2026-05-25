{
  lib,
  config,
  ...
}:
# ---------------------------------------------------------------------------
# Agent Mesh Collective Memory — Phase 18
#
# Injects agent mesh env vars into the ai-hybrid-coordinator service and the
# agent spawner so Redis blackboard + AIDB collaboration archive are activated.
#
# Activated when:
#   mySystem.roles.aiStack.enable = true
#   mySystem.mcpServers.enable = true
#   mySystem.aiStack.agentMesh.enable = true
#
# collective_memory.py and experience_replay.py run inside agent_spawner.py;
# mesh status endpoints are served by agents_task_handlers inside coordinator.
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  mcp = cfg.mcpServers;
  ai = cfg.aiStack;
  am = ai.agentMesh;

  active = cfg.roles.aiStack.enable && mcp.enable && am.enable;
in
  lib.mkIf active {
    # Inject agent mesh env vars into the hybrid coordinator service.
    systemd.services.ai-hybrid-coordinator.serviceConfig.Environment = lib.mkAfter [
      "AGENT_MESH_ENABLED=true"
      "AGENT_MESH_BLACKBOARD_TTL=${toString am.blackboardTtlSeconds}"
      "AGENT_MESH_DISTANCE_THRESHOLD=${am.distanceThreshold}"
      "AGENT_MESH_COLLABORATION_RETENTION_DAYS=${toString am.collaborationRetentionDays}"
    ];
  }
