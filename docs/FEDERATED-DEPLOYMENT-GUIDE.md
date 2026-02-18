# Federated Learning Deployment Guide

**Version**: 1.0.0
**Created**: 2025-12-21
**Agent Guide**: [43-FEDERATED-DEPLOYMENT.md](/docs/agent-guides/43-FEDERATED-DEPLOYMENT.md)

> **Note**: This document is symlinked to the modular agent documentation at `docs/agent-guides/43-FEDERATED-DEPLOYMENT.md`

## Quick Reference

For detailed deployment instructions, see the complete guide at:
- **Agent Guide**: [docs/agent-guides/43-FEDERATED-DEPLOYMENT.md](/docs/agent-guides/43-FEDERATED-DEPLOYMENT.md)
- **Federation Strategy**: [FEDERATED-DATA-STRATEGY.md](FEDERATED-DATA-STRATEGY.md)
- **Automation Templates**: [scripts/cron-templates.sh](/scripts/cron-templates.sh)

## Essential Commands

```bash
# Sync learning data (runtime → git repo)
bash scripts/sync-learning-data.sh

# Export Qdrant collections (Qdrant → git repo)
bash scripts/export-collections.sh

# Import collections on new system (git repo → Qdrant)
bash scripts/import-collections.sh
```

## Quick Start Paths

### First Deployment (No Existing Data)
1. `sudo bash nixos-quick-deploy.sh`
2. `bash scripts/initialize-ai-stack.sh`
3. Use the system to generate patterns
4. `bash scripts/sync-learning-data.sh`
5. `git commit && git push`

### Subsequent Deployment (With Federated Data)
1. `git clone` (includes federated patterns in `data/`)
2. `sudo bash nixos-quick-deploy.sh`
3. `bash scripts/initialize-ai-stack.sh` (auto-imports patterns!)
4. System starts with collective knowledge ✨

---

For complete documentation, deployment workflows, troubleshooting, and best practices, see:
**[docs/agent-guides/43-FEDERATED-DEPLOYMENT.md](/docs/agent-guides/43-FEDERATED-DEPLOYMENT.md)**
