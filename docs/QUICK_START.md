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

## Core Commands

```bash
# show supported options
./nixos-quick-deploy.sh --help

# run preflight checks only (no build/switch)
./nixos-quick-deploy.sh --analyze-only

# evaluate/build only (no live switch)
./nixos-quick-deploy.sh --build-only

# stage next boot generation
./nixos-quick-deploy.sh --boot

# skip specific execution blocks when needed
./nixos-quick-deploy.sh --skip-system-switch
./nixos-quick-deploy.sh --skip-home-switch
./nixos-quick-deploy.sh --skip-health-check
./nixos-quick-deploy.sh --skip-discovery
./nixos-quick-deploy.sh --skip-flatpak-sync
./nixos-quick-deploy.sh --skip-readiness-check
./nixos-quick-deploy.sh --skip-ai-secrets-bootstrap
```

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
./scripts/system-health-check.sh --detailed
./scripts/run-all-checks.sh
```
