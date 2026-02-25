# AI Stack Secrets Management Guide

**Last Updated:** February 2, 2026
**Tool Version:** 1.0.0
**Status:** ✅ Production Ready

---

## Quick Start

### Initialize All Secrets (First Time)

```bash
# Interactive TUI mode (recommended)
./scripts/manage-secrets.sh

# Or command-line mode
./scripts/manage-secrets.sh init
```

This will generate:
- 3 database passwords (32 bytes each, 256-bit entropy)
- 9 API keys (64 bytes each, 512-bit entropy)

## SOPS Bundle (Phase 9)

The deployment now supports (and can enforce) a single encrypted secrets bundle:

- **Config:** `.sops.yaml` (repo root)
- **Enforce encrypted secrets:** set `REQUIRE_ENCRYPTED_SECRETS=true`

### Deprecated Plaintext Manifests

All secret creation must happen via the SOPS bundle + Phase 9 gate.

### History Cleanup (Requires Explicit Approval)

Because gitleaks found historical secrets, the repo history must be rewritten and credentials rotated.
Recommended approach:

1. Ensure all secrets are rotated and re-applied (Phase 9) after the rewrite.
2. Use `git filter-repo` to remove the leaked files from history.
3. Force-push the rewritten history and notify collaborators.

This is a destructive operation and should be done only after coordination.

### Create or Refresh Bundle

```bash
```

### Rotate Secrets (SOPS)

```bash
# Rotate all keys in the bundle
./scripts/rotate-secrets.sh all

# Rotate specific keys
./scripts/rotate-secrets.sh postgres_password grafana_admin_password
```


### No-Downtime Rotation Procedure (K3s)

```bash
# 0) Ensure cluster is healthy before rotation
./scripts/ai-stack-health.sh

# 1) Rotate secrets (bundle update)
./scripts/rotate-secrets.sh all

# 2) Apply updated secrets to the cluster

# 3) Restart only the affected deployments (preferred) or all deployments
# Example: restart all deployments in ai-stack

# 4) Wait for rollouts to complete

# 5) Verify stack health
./scripts/ai-stack-health.sh
```

Notes:
- Prefer restarting only deployments that consume the rotated secrets to minimize blast radius.
- Some services read secrets only on startup; a rollout restart is required to pick up new values.

### Check Secret Status

```bash
./scripts/manage-secrets.sh status
```

Output shows all secrets with:
- ✅ Status (OK or MISSING)
- File size
- Type (password or API key)
- Affected services
- Last rotation date

---

## Features

### 🔐 Secure Password Generation
- Cryptographically secure random generation
- Database-safe characters (no `/`, `+`, `=`)
- Configurable length (32B passwords, 64B API keys)
- 256-bit to 512-bit entropy

### 🔄 Password Rotation
- Rotate individual secrets
- Rotate all secrets at once
- Automatic backup before rotation
- Service restart guidance

### 💾 Backup & Restore
- Timestamped backups
- Easy restoration
- Config file backup included
- List available backups

### ✅ Validation
- Check file existence
- Verify permissions (should be 644)
- Validate content length
- Check for empty/corrupted files

### 📊 Status Dashboard
- Beautiful TUI with tables (if `rich` installed)
- Fallback to basic CLI
- Shows all secrets at a glance
- Service mapping

---

## Installation

### Prerequisites

```bash
# Python 3 (already included in NixOS)
python3 --version  # Should be 3.9+

# Optional: Install rich for fancy TUI
pip install rich
# Or with nix:
nix-shell -p python3Packages.rich
```

### Make Scripts Executable

```bash
chmod +x scripts/manage-secrets.sh
chmod +x scripts/manage-secrets.py
```

---

## Usage

### Interactive Mode (Recommended)

```bash
./scripts/manage-secrets.sh
```

**Menu Options:**
1. **Initialize all secrets** - First-time setup
2. **Rotate a secret** - Change one password/key
3. **Rotate all secrets** - Change everything
4. **Backup secrets** - Create timestamped backup
5. **Restore from backup** - Restore previous version
6. **Show status** - View all secrets
7. **Validate secrets** - Check for issues
8. **Exit**

### Command-Line Mode

```bash
# Initialize all secrets
./scripts/manage-secrets.sh init

# Force re-initialize (overwrites existing)
./scripts/manage-secrets.sh init --force

# Rotate a specific secret
./scripts/manage-secrets.sh rotate postgres_password

# Rotate all secrets
./scripts/manage-secrets.sh rotate all

# Create backup
./scripts/manage-secrets.sh backup

# Restore from backup
./scripts/manage-secrets.sh restore backups/secrets/secrets_20260124_120000

# Show status
./scripts/manage-secrets.sh status

# Validate secrets
./scripts/manage-secrets.sh validate

# List available backups
./scripts/manage-secrets.sh list-backups
```

---

## Secret Types

### Passwords (32 bytes, 256-bit entropy)

| Secret | Used By | Purpose |
|--------|---------|---------|
| `postgres_password` | postgres, aidb, hybrid-coordinator, health-monitor, ralph-wiggum | PostgreSQL database authentication |
| `redis_password` | redis, aidb, nixos-docs, autogpt, ralph-wiggum | Redis cache authentication |
| `grafana_admin_password` | grafana | Grafana web UI admin login |

### API Keys (64 bytes, 512-bit entropy)

| Secret | Used By | Purpose |
|--------|---------|---------|
| `stack_api_key` | global | Main stack API authentication |
| `aidb_api_key` | aidb | AIDB service API |
| `aider_wrapper_api_key` | aider-wrapper | Aider wrapper service API |
| `container_engine_api_key` | container-engine | Container engine API |
| `dashboard_api_key` | dashboard | Dashboard API |
| `embeddings_api_key` | embeddings | Embeddings service API |
| `hybrid_coordinator_api_key` | hybrid-coordinator | Coordinator API |
| `nixos_docs_api_key` | nixos-docs | NixOS docs service API |
| `ralph_wiggum_api_key` | ralph-wiggum | Ralph orchestrator API |

---

## Common Tasks

### First-Time Setup

```bash
# 1. Initialize secrets
./scripts/manage-secrets.sh init

# 2. Verify all secrets created
./scripts/manage-secrets.sh status

# 3. Start the stack
export AI_STACK_ENV_FILE=/path/to/.env
```

### Rotate a Database Password

```bash
# 1. Rotate the password
./scripts/manage-secrets.sh rotate postgres_password

# 2. Update PostgreSQL user password (for existing databases)
  -c "ALTER USER mcp WITH PASSWORD '$NEW_PASS';"

# 3. Restart affected services
```

### Rotate All API Keys

```bash
# 1. Create backup first
./scripts/manage-secrets.sh backup

# 2. Rotate all secrets
./scripts/manage-secrets.sh rotate all

# 3. Restart all services
```

### Backup Before Maintenance

```bash
# Create backup
./scripts/manage-secrets.sh backup

# Output shows backup path:
# ✅ Backed up 12 secrets to:
#    /path/to/backups/secrets/secrets_20260124_153045
```

### Restore After Issue

```bash
# List available backups
./scripts/manage-secrets.sh list-backups

# Restore specific backup
./scripts/manage-secrets.sh restore backups/secrets/secrets_20260124_153045

# Restart services
```

---

## Troubleshooting

### Issue: Permission Denied

**Error:**
```
Permission denied reading /run/secrets/postgres_password
```

**Fix:**
```bash
# Ensure secrets file is readable (sops-managed)
```

### Issue: Empty or Missing Secrets

**Error:**
```
❌ postgres_password: MISSING
```

**Fix:**
```bash
# Initialize missing secrets
./scripts/manage-secrets.sh init

# Or force reinitialize all
./scripts/manage-secrets.sh init --force
```

### Issue: Validation Fails

**Error:**
```
⚠️ postgres_password: Size is 31B, expected 32B
```

**Fix:**
```bash
# Regenerate the corrupted secret
./scripts/manage-secrets.sh rotate postgres_password
```

### Issue: Service Can't Connect After Rotation

**Problem:** Rotated password but service still can't connect

**Fix:**
```bash
# For existing databases, you must update the password manually

# PostgreSQL:
  -c "ALTER USER mcp WITH PASSWORD '$NEW_PASS';"

# Grafana: Delete data directory and restart
docker stop local-ai-grafana
podman unshare rm -rf ~/.local/share/nixos-ai-stack/grafana/*
docker start local-ai-grafana

# Redis: Just restart (reads password on startup)
```

---

## Security Best Practices

### ✅ DO:
- Use `init` command for first-time setup
- Run `validate` regularly to check for issues
- Create backups before rotating secrets
- Use strong, random passwords (tool does this automatically)
- Keep secrets directory readable by containers (644)
- Rotate secrets periodically (quarterly or after incidents)

### ❌ DON'T:
- Don't commit secrets to git (`.gitignore` handles this)
- Don't share secrets in plaintext (use backup files securely)
- Don't use weak permissions (600 will prevent container access)
- Don't edit secrets manually (use the tool)
- Don't reuse passwords across environments

---

## File Locations

### Secrets Directory
```
├── postgres_password           # 32B password
├── redis_password              # 32B password
├── grafana_admin_password      # 32B password
├── stack_api_key               # 64B API key
├── aidb_api_key                # 64B API key
├── aider_wrapper_api_key       # 64B API key
├── container_engine_api_key    # 64B API key
├── dashboard_api_key           # 64B API key
├── embeddings_api_key          # 64B API key
├── hybrid_coordinator_api_key  # 64B API key
├── nixos_docs_api_key          # 64B API key
└── ralph_wiggum_api_key        # 64B API key
```

### Backup Directory
```
backups/secrets/
├── secrets_20260124_120000/   # Timestamped backup 1
│   ├── postgres_password
│   ├── redis_password
│   └── ...
└── secrets_20260124_153045/   # Timestamped backup 2
    ├── postgres_password
    ├── redis_password
    └── ...
```

### Configuration File
```
{
  "postgres_password": {
    "created": "2026-01-24T12:00:00",
    "hash": "a1b2c3d4e5f6...",
    "type": "password",
    "rotated": "2026-01-24T15:30:00"
  },
  ...
}
```

---

## Integration with Kubernetes Secrets

### Apply Secrets (sops-managed)

```bash
```

### How Services Read Secrets

**Kubernetes envFrom / secretKeyRef:**
```yaml
env:
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: postgres-password
        key: password
```

**Python services (helper library):**
```python
from shared.secrets_loader import load_secret, build_postgres_url

# Load password from secret
password = load_secret("postgres_password", fallback_env_var="POSTGRES_PASSWORD")

# Build connection URL
db_url = build_postgres_url(password=password)
```

---

## Automation

### Automated Rotation Script

Create a cron job or systemd timer:

```bash
# /etc/cron.weekly/rotate-ai-stack-secrets
#!/bin/bash
cd /path/to/NixOS-Dev-Quick-Deploy

# Backup first
./scripts/manage-secrets.sh backup

# Rotate all secrets
./scripts/manage-secrets.sh rotate all

# Restart stack

# Send notification (optional)
echo "AI Stack secrets rotated on $(date)" | mail -s "Secret Rotation" admin@example.com
```

### CI/CD Integration

```yaml
# .github/workflows/rotate-secrets.yml
name: Rotate Secrets
on:
  schedule:
    - cron: '0 0 1 * *'  # First day of each month
  workflow_dispatch:      # Manual trigger

jobs:
  rotate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install rich

      - name: Rotate secrets
        run: |
          ./scripts/manage-secrets.sh backup
          ./scripts/manage-secrets.sh rotate all

      - name: Commit changes
        run: |
          git commit -m "chore: rotate secrets (automated)"
          git push
```

---

## FAQ

**Q: What happens if I lose my secrets?**
A: Restore from the most recent backup using `restore` command. If no backups exist, you'll need to reinitialize and manually update database passwords.

**Q: Can I use my own passwords?**

**Q: How often should I rotate secrets?**
A: Quarterly rotation is recommended. Rotate immediately after:
- Security incident
- Employee departure
- Suspected compromise
- Compliance requirement

**Q: What if I rotate a password and services break?**
A: Restore from backup: `./scripts/manage-secrets.sh restore <backup_path>`

**Q: Can I use this in production?**
A: Yes! The tool is production-ready. Just ensure:
- Regular backups
- Secure backup storage
- Documented recovery procedures
- Team training on secret rotation

**Q: How do I apply secrets to Kubernetes?**
A: Encrypt and apply the sops file:
```bash
```

---

## Related Documentation

- [docs/archive/DAY5-INTEGRATION-TESTING-RESULTS.md](docs/archive/DAY5-INTEGRATION-TESTING-RESULTS.md) - Password migration testing
- [docs/archive/CONTAINER-ORCHESTRATION-ANALYSIS-2026.md](docs/archive/CONTAINER-ORCHESTRATION-ANALYSIS-2026.md) - Orchestration recommendations
- [90-DAY-REMEDIATION-PLAN.md](90-DAY-REMEDIATION-PLAN.md) - Security roadmap
- [ai-stack/mcp-servers/shared/secrets_loader.py](ai-stack/mcp-servers/shared/secrets_loader.py) - Python helper library

---

**Tool Location:** `scripts/manage-secrets.py` and `scripts/manage-secrets.sh`
**Maintainer:** AI Stack Team
**License:** Same as project
**Version:** 1.0.0
