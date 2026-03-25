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
    ./autonomous-improvement.nix
    ./meta-optimization.nix
    ./crowdsec.nix
    ./lore-sync.nix
    ./nvd-sync.nix
  ];
}
