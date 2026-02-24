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
  ];
}
