{ lib, config, ... }:
# ---------------------------------------------------------------------------
# Affective Engine — Phase 19
#
# Injects affective engine env vars into the ai-hybrid-coordinator service so
# signal detectors, reciprocity tracker, and output modulator are activated.
#
# Activated when:
#   mySystem.roles.aiStack.enable = true
#   mySystem.mcpServers.enable = true
#   mySystem.aiStack.affectiveEngine.enable = true
#
# No separate systemd unit needed: the affective pipeline runs inline inside
# the hybrid coordinator's handle_query() via affective_handlers.init().
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  mcp = cfg.mcpServers;
  ai  = cfg.aiStack;
  ae  = ai.affectiveEngine;

  active = cfg.roles.aiStack.enable && mcp.enable && ae.enable;
in
lib.mkIf active {
  # Inject affective engine env vars into the hybrid coordinator service.
  systemd.services.ai-hybrid-coordinator.serviceConfig.Environment =
    lib.mkAfter [
      "AFFECTIVE_ENABLED=true"
      "AFFECTIVE_COMPASSION_WORD_THRESHOLD=${toString ae.compassionWordThreshold}"
      "AFFECTIVE_RECIPROCITY_TTL_DAYS=${toString ae.reciprocityTtlDays}"
      "AFFECTIVE_EMPATHY_RETRY_THRESHOLD=${toString ae.empathyRetryThreshold}"
    ];
}
