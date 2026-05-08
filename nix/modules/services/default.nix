{ ... }:
{
  imports = [
    ./ai-stack.nix
    ./mcp-servers.nix
    ./monitoring.nix
    ./command-center-dashboard.nix
    ./ingress.nix
    ./capability-registry.nix
    ./switchboard.nix
    ./cli-bridge.nix
    ./autonomous-improvement.nix
    ./identity-kernel.nix
    ./affective-engine.nix
    ./agent-mesh.nix
    ./world-model.nix
    ./meta-optimization.nix
    ./crowdsec.nix
    ./lore-sync.nix
    ./nvd-sync.nix
    ./data-retention.nix
  ];
}
