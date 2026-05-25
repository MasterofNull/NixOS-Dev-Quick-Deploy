# Quick Start Guide
## NixOS Quick Deploy (Flake-First)

This guide covers the currently supported `nixos-quick-deploy.sh` workflow.

## Prerequisites

- NixOS host
- sudo access
- repo cloned locally

```bash
git clone https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy.git ~/NixOS-Dev-Quick-Deploy
cd ~/NixOS-Dev-Quick-Deploy
chmod +x nixos-quick-deploy.sh
```

## First Run

```bash
./nixos-quick-deploy.sh --host nixos --profile ai-dev
```

If `--host` is omitted, the script auto-resolves from current hostname and flake hosts.

## Day 2 Operations

Once deployed, use the `deploy` CLI for ongoing maintenance:

```bash
./deploy help          # List all available commands
./deploy status        # Show active profile and system facts
./deploy health        # Run tiered health checks (L1-L7)
./deploy ai-stack      # Manage inference, embeddings, and MCP servers
./deploy build         # Rebuild configuration without switching
```

## System Verification

Confirm the platform is operational:

| Check | Command |
|-------|---------|
| **Dashboard** | `curl http://127.0.0.1:8889/api/health` |
| **QA Suite** | `aq-qa 0` |
| **Hints Engine** | `aq-hints "how do I update NixOS"` |
| **Integrity** | `scripts/governance/tier0-validation-gate.sh --pre-commit` |

---

## Safe Recovery

```bash
# rollback system generation
sudo nixos-rebuild switch --rollback

# inspect previous home-manager generations
home-manager generations
```

## AI Stack Notes

For `ai-dev` profile, AI stack services are declarative and started by systemd.
There is no `--with-ai-stack` deploy flag.

## Troubleshooting

```bash
systemctl --failed --no-pager
journalctl -u ai-aidb.service -u ai-hybrid-coordinator.service -u ai-ralph-wiggum.service -b --no-pager -n 200
```

## Validation

```bash
./scripts/health/system-health-check.sh --detailed
./scripts/automation/run-all-checks.sh
```
