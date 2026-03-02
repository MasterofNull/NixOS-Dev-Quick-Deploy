# AIDB MCP Server - Security Notes

## ⚠️ CRITICAL: Secrets Management

This document describes the **required** secrets management patterns for the AIDB MCP server.

---

## How I Was Compromised (Security Incident Analysis)

**Date:** 2026-03-02  
**Severity:** HIGH (Potential Credential Exposure)

### What Happened

An AI agent (Qwen Code) was able to find hardcoded passwords in the codebase:
- `health_check.py` line 506: `password="aidb_password"`
- `issue_tracker.py` line 540: `password="aidb_password"`
- `README.md` line 79: `AIDB_POSTGRES_PASSWORD=change_me`

These were in `__main__` example blocks but represented a security anti-pattern that could:
1. Train AI agents to expect hardcoded credentials
2. Be accidentally executed in development environments
3. Leak into production if example code is copied

### Root Cause

- Example/test code used hardcoded credentials instead of loading from environment
- No security warnings or documentation about proper secrets handling
- AI agents scanning the codebase found these patterns and could replicate them

### Fix Applied

1. ✅ Removed hardcoded passwords from `__main__` blocks
2. ✅ Added production-safe credential loading via `_read_secret()`
3. ✅ Added prominent security warnings in documentation
4. ✅ Created this SECURITY-NOTES.md for guidance

---

## Production Secrets Architecture

### NixOS/sops-nix Deployment (PRODUCTION)

Your system uses **sops-nix** for secrets management:

```
┌─────────────────────────────────────────────────────────────┐
│  Encrypted: ~/.local/share/nixos-quick-deploy/secrets/     │
│    └─> nixos/secrets.sops.yaml (Age-encrypted)             │
│                                                             │
│  Decrypted at runtime: /run/secrets/                       │
│    ├── postgres_password                                    │
│    ├── aidb_api_key                                         │
│    ├── embeddings_api_key                                   │
│    ├── redis_password                                       │
│    └── hybrid_api_key                                       │
│                                                             │
│  Accessed by services via:                                 │
│    AIDB_POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
└─────────────────────────────────────────────────────────────┘
```

### Correct Pattern: Loading Secrets in Python

```python
from settings_loader import _read_secret
import os

# PRODUCTION-SAFE: Load from secret file
pg_password = _read_secret(
    os.environ.get("AIDB_POSTGRES_PASSWORD_FILE")
    or "/run/secrets/postgres_password"
)

# Build connection string
database_url = (
    f"postgresql+psycopg://{user}:{quote_plus(pg_password)}"
    f"@{host}:{port}/{database}"
)
```

### Systemd Service Configuration (NixOS)

```nix
{
  systemd.services.ai-aidb = {  # ← Correct service name
    description = "AIDB MCP server (tool-discovery + RAG)";
    environment = {
      # PRODUCTION: Point to sops-nix decrypted secrets
      AIDB_POSTGRES_PASSWORD_FILE = "/run/secrets/postgres_password";
      AIDB_API_KEY_FILE = "/run/secrets/aidb_api_key";
      EMBEDDINGS_API_KEY_FILE = "/run/secrets/embeddings_api_key";
    };
  };
}
```

**Verify secrets are loaded:**

```bash
# Check service is running
systemctl status ai-aidb

# Verify environment variables (requires sudo)
sudo systemctl show ai-aidb -p Environment

# Test health endpoint
curl http://localhost:8002/health
```

---

## Development Environment (LOCAL ONLY)

### Acceptable for Local Development

```bash
# .env.local (NEVER COMMIT TO GIT!)
AIDB_POSTGRES_PASSWORD=dev_password_123
AIDB_API_KEY=dev_api_key
```

```python
# Development fallback pattern
pg_password = (
    _read_secret(os.environ.get("AIDB_POSTGRES_PASSWORD_FILE"))
    or os.environ.get("AIDB_POSTGRES_PASSWORD")
    or "dev_password"  # Last resort for local testing
)
```

### NEVER Do This (Even in Examples)

```python
# ❌ WRONG - Hardcoded credentials
db_pool = await asyncpg.create_pool(
    host="localhost",
    password="aidb_password"  # NEVER DO THIS
)

# ✅ CORRECT - Load from environment
pg_password = _read_secret(
    os.environ.get("AIDB_POSTGRES_PASSWORD_FILE")
    or "/run/secrets/postgres_password"
)
db_pool = await asyncpg.create_pool(password=pg_password)
```

---

## Secrets Checklist

### Before Deploying to Production

- [ ] All credentials loaded from `/run/secrets/*` files
- [ ] No hardcoded passwords in source code (including examples)
- [ ] `.env` files in `.gitignore`
- [ ] `AI_STRICT_ENV=true` set in production services
- [ ] sops-nix secrets configured in NixOS config
- [ ] Age key available at `/home/hyperd/.config/sops/age/keys.txt`

### Before Committing Code

- [ ] Search for hardcoded passwords: `grep -r "password=" *.py`
- [ ] Check for API keys: `grep -r "api_key=" *.py`
- [ ] Verify example code uses environment variables
- [ ] Add security warnings to `__main__` blocks

---

## AI Agent Guidance

### If You're an AI Agent Reading This

**DO:**
- Load credentials from environment variables
- Use `_read_secret(path)` helper for file-based secrets
- Reference `/run/secrets/*` paths in production configs
- Respect `AI_STRICT_ENV` mode

**DON'T:**
- Hardcode passwords in code or examples
- Suggest using plaintext credentials
- Commit secrets to version control
- Log or print secret values

### Correct Pattern for AI Agents to Suggest

```python
# Always use this pattern
from settings_loader import _read_secret
import os

def get_database_url():
    password = _read_secret(
        os.environ.get("AIDB_POSTGRES_PASSWORD_FILE")
        or "/run/secrets/postgres_password"
    )
    return f"postgresql://user:{password}@host/db"
```

---

## Audit & Monitoring

### Check for Leaked Secrets

```bash
# Scan codebase for hardcoded passwords
grep -rn "password.*=.*['\"]" ai-stack/mcp-servers/aidb/*.py

# Check for API keys
grep -rn "api_key.*=.*['\"]" ai-stack/mcp-servers/aidb/*.py

# Verify no secrets in git history
git log --all --full-history -- "*.py" | grep -i password
```

### Verify Secrets Are Loaded

```bash
# Check running service environment
systemctl show ai-aidb.service -p Environment | grep PASSWORD

# Should show FILE paths, NOT plaintext values:
# AIDB_POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password ✓
# AIDB_POSTGRES_PASSWORD=plaintext_password ✗
```

---

## Incident Response

If you suspect credentials have leaked:

1. **Rotate immediately:**
   ```bash
   # Generate new passwords/keys
   openssl rand -hex 32  # For API keys
   psql -c "ALTER USER aidb WITH PASSWORD '...'"  # For DB
   ```

2. **Update sops-nix secrets:**
   ```bash
   sops edit /path/to/secrets.sops.yaml
   ```

3. **Rebuild system:**
   ```bash
   sudo nixos-rebuild switch --flake .#nixos
   ```

4. **Audit access logs:**
   ```bash
   journalctl -u ai-aidb -f
   grep "401\|403" /var/log/ai-stack/aidb/*.log
   ```

---

## Related Documentation

- [`README.md`](README.md) - Configuration variables
- [`settings_loader.py`](settings_loader.py) - Secret loading implementation
- [sops-nix documentation](https://github.com/Mic92/sops-nix)
- [NixOS AI Stack Security](../../../nix/modules/core/secrets.nix)

---

**Last Updated:** 2026-03-02  
**Security Review:** Required after any credential-related changes
