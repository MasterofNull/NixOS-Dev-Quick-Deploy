# Security Setup Guide - Production Hardening

This guide covers setting up secure secrets management for the AI stack.

## Overview

The AI stack uses environment variables for all secrets. **Never commit actual passwords to git.**

## Files Involved

- **`.env`** - Contains actual secrets (**NEVER commit this file**)
- **`.env.example`** - Template with placeholder values (safe to commit)
- **`.gitignore`** - Ensures `.env` is never committed
- **`~/.config/nixos-ai-stack/.env`** - Active environment configuration

## Quick Setup

1. **Copy the example environment file:**
   ```bash
   cp ~/.config/nixos-ai-stack/.env.example ~/.config/nixos-ai-stack/.env
   ```

2. **Generate strong passwords:**
   ```bash
   # PostgreSQL password (20+ characters)
   openssl rand -base64 32

   # API Key (32+ characters)
   openssl rand -hex 32
   ```

3. **Edit ~/.config/nixos-ai-stack/.env:**
   ```bash
   nano ~/.config/nixos-ai-stack/.env
   ```

4. **Set the following secrets:**
   ```bash
   # Database passwords
   POSTGRES_PASSWORD=<your-strong-password-here>
   AIDB_POSTGRES_PASSWORD=<same-password-as-above>

   # API keys (optional but recommended)
   STACK_API_KEY=<your-api-key-here>

   # Cloud API keys (if using remote LLMs)
   ANTHROPIC_API_KEY=<your-key>
   OPENAI_API_KEY=<your-key>
   ```

5. **Verify permissions:**
   ```bash
   chmod 600 ~/.config/nixos-ai-stack/.env
   ls -la ~/.config/nixos-ai-stack/.env
   # Should show: -rw------- (only you can read/write)
   ```

6. **Restart services:**
   ```bash
   cd ai-stack/compose
   podman-compose down
   podman-compose up -d
   ```

## Secret Priority (P1-SEC-003)

The system loads secrets in this order (later sources override earlier ones):

1. **Config file value** (`config.yaml`)
2. **Environment variable** (`.env` file)
3. **Secret file** (Docker secrets)

Example for postgres password:
```python
# settings_loader.py
pg_password = (
    _read_secret(postgres_cfg.get("password_file"))  # 1. Check secret file
    or postgres_cfg.get("password", "")              # 2. Check config
    or os.environ.get("AIDB_POSTGRES_PASSWORD", "")  # 3. Check environment (WINS)
)
```

This means:
- ✅ **Environment variables (`.env`) override config values**
- ✅ **Docker secrets override everything**
- ✅ **Default values in config.yaml are fallbacks only**

## Security Best Practices

### Password Requirements

- **Minimum 20 characters**
- **Mix of uppercase, lowercase, numbers, symbols**
- **No dictionary words**
- **Unique per service**

### File Permissions

```bash
# Production environment file (contains secrets)
chmod 600 ~/.config/nixos-ai-stack/.env

# Example file (no secrets)
chmod 644 ~/.config/nixos-ai-stack/.env.example
```

### Git Safety

Ensure `.gitignore` contains:
```
.env
*.secret
*.key
```

Verify with:
```bash
git status --ignored
```

### Rotation Policy

- **Change passwords every 90 days**
- **Change immediately if:**
  - System compromise suspected
  - Employee with access leaves
  - Service account leaked

## Verification

### Test 1: Environment Variables Loaded
```bash
# From inside AIDB container
podman exec local-ai-aidb env | grep POSTGRES_PASSWORD
# Should show: AIDB_POSTGRES_PASSWORD=<your-password>
```

### Test 2: Database Connection Works
```bash
curl -s http://localhost:8091/health | jq .database
# Should show: "ok"
```

### Test 3: No Secrets in Git
```bash
git grep -i "change_me_in_production" || echo "✓ No default passwords in code"
git ls-files | xargs grep -l "POSTGRES_PASSWORD.*=" | grep -v ".env.example" || echo "✓ No .env committed"
```

### Test 4: File Permissions
```bash
stat -c "%a %n" ~/.config/nixos-ai-stack/.env
# Should show: 600 /home/user/.config/nixos-ai-stack/.env
```

## Troubleshooting

### Issue: "password authentication failed"
**Cause:** Environment variable not loaded or mismatch between services

**Fix:**
1. Check environment is set:
   ```bash
   grep POSTGRES_PASSWORD ~/.config/nixos-ai-stack/.env
   ```

2. Ensure both services use same password:
   ```bash
   # Both should match
   echo $POSTGRES_PASSWORD
   echo $AIDB_POSTGRES_PASSWORD
   ```

3. Restart all services:
   ```bash
   podman-compose restart postgres aidb
   ```

### Issue: "AIDB_POSTGRES_PASSWORD not set"
**Cause:** Environment file not loaded by docker-compose

**Fix:**
1. Check compose is using env file:
   ```bash
   grep AI_STACK_ENV_FILE docker-compose.yml
   ```

2. Export the path:
   ```bash
   export AI_STACK_ENV_FILE=~/.config/nixos-ai-stack/.env
   ```

3. Restart compose:
   ```bash
   podman-compose up -d
   ```

### Issue: "Still using change_me_in_production"
**Cause:** Old container with cached environment

**Fix:**
1. Remove containers completely:
   ```bash
   podman-compose down -v
   ```

2. Rebuild with fresh environment:
   ```bash
   podman-compose up -d --force-recreate
   ```

## Production Checklist

Before deploying to production:

- [ ] All passwords changed from defaults
- [ ] `.env` file has 600 permissions
- [ ] `.env` is in `.gitignore`
- [ ] Passwords meet complexity requirements (20+ chars)
- [ ] API keys rotated and unique per environment
- [ ] Database connections tested
- [ ] Health checks passing
- [ ] No secrets in git history (`git log -S "change_me_in_production"`)
- [ ] Password rotation policy documented
- [ ] Backup of `.env` stored securely (encrypted)

## Related Tasks

- **P1-SEC-001**: Dashboard proxy security ✅
- **P1-SEC-002**: Rate limiting ✅
- **P1-SEC-003**: Secrets management ✅ (this document)

## Next Steps

After securing secrets, implement:
- **P2-REL-001**: Checkpointing for continuous learning
- **P2-REL-002**: Circuit breakers for external dependencies
