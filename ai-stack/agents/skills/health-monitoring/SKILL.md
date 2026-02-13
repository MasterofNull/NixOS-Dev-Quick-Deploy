# Skill Name: health-monitoring

## Description
Runs the comprehensive `./scripts/system-health-check.sh` routine to validate NixOS, Home Manager, AI tooling, Flatpaks, MCP services, and environment variables with actionable output.

## When to Use
- After running `nixos-quick-deploy.sh` to confirm success
- Before filing bugs or tuning phases to capture baseline
- Prior to MCP/AI service upgrades to ensure dependencies are healthy
- When AI services misbehave (Ollama/Qdrant/Open WebUI) to isolate root causes
- During CI to gate merges on reproducible health signals

## Prerequisites
- Completed deployment (Phase 8) or equivalent manual setup
- Access to `~/Documents/NixOS-Dev-Quick-Deploy`
- Python interpreter for package probes
- Flatpak/Podman configured per quick deploy defaults

## Usage

### Standard Health Check
```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
./scripts/system-health-check.sh
```
- Displays pass/warn/fail counts (defaults to brief mode).

### Detailed Output (per subsystem)
```bash
./scripts/system-health-check.sh --detailed
```
- Prints version strings, directory counts, and tool paths for each section.

### Auto-Fix Optional Issues
```bash
./scripts/system-health-check.sh --fix
```
- Attempts to reinstall missing npm/python packages and refresh Flatpak remotes.

## Output Interpretation

| Indicator | Meaning | Action |
|-----------|---------|--------|
| `✓` | Check passed | None |
| `⚠` | Optional component missing | Review instructions in output |
| `✗` | Required component failed | Inspect log, rerun with `--detailed` |

Summary block lists total counts and final verdict (`PASSED` / `FAILED`).

## Major Sections
1. Core system tools (Podman, Git, curl, etc.)
2. Programming runtimes (Python/Node/Go/Rust/Ruby)
3. Nix ecosystem (nix, nix-env, Home Manager, flakes)
4. Channel alignment (system/user/home-manager)
5. AI CLI packages & wrappers (Claude Code, GPT Codex, OpenAI CLI, Goose)
6. Python AI/ML modules (torch, tensorflow, langchain, etc.)
7. Editors/IDEs (Neovim, VSCodium, Cursor launcher)
8. Shell configuration (ZSH, Powerlevel10k)
9. Flatpak apps/remotes
10. Environment variables (`PATH`, `NPM_CONFIG_PREFIX`, `EDITOR`)
11. AI systemd services (Ollama, Qdrant, MindsDB, Open WebUI, Gitea)
12. Network services (Ollama availability check)
13. Nix store/profile health
14. Config files (`.npmrc`, `.gitconfig`)

## Related Skills
- `nixos-deployment`: Deploys full system before running health checks
- `ai-service-management`: Starts/stops AI services referenced by health check
- `ai-model-management`: Ensures Ollama/Qdrant models exist when tests probe them
- `mcp-database-setup`: Preps PostgreSQL/Redis that health check verifies

## Examples

### Example 1 – Fresh Deployment Confirmation
```bash
./scripts/system-health-check.sh
# Output: Passed 90 / Warnings 14 / Failed 0
```
Use summary to document success in `DEPLOYMENT-SUCCESS-V5.md`.

### Example 2 – Detailed Investigation
```bash
./scripts/system-health-check.sh --detailed | tee "${TMPDIR:-/tmp}/health.log"
```
Attach `${TMPDIR:-/tmp}/health.log` to issue reports.

### Example 3 – Optional Fixes
```bash
./scripts/system-health-check.sh --fix
# Reinstalls missing npm/pip packages, updates remotes, reruns checks
```

## MCP Integration
- Register `health-monitoring` as a tool in the AIDB MCP server
- Returns structured JSON summary so clients can programmatically gate workflows
- Supports progressive disclosure (basic vs. detailed vs. fix modes)

## Skill Metadata
- **Version**: 1.0.0
- **Last Updated**: 2025-11-22
- **Category**: diagnostics
- **Tags**: health-check, diagnostics, validation, nixos, ai-stack
