# Workflow Executor Security Guide

**Date:** 2026-04-09
**Status:** Production security configuration
**Audience:** System administrators, DevOps engineers

---

## Overview

The workflow executor requires LLM API keys to function. This guide covers **secure** API key management using your existing sops-nix infrastructure, avoiding plaintext secrets in config files, environment variables, or version control.

---

## Security Architecture

### Key Management Hierarchy

The LLM client searches for API keys in this priority order:

1. **Environment variable** (runtime override for testing)
2. **Explicit file path** (`ANTHROPIC_API_KEY_FILE`)
3. **sops-nix decrypted secret** (`/run/secrets/*`) ⭐ **RECOMMENDED**
4. **Local dev file** (`~/.config/anthropic/api-key`) - development only

### sops-nix Integration (Production)

Your system uses **sops-nix** for declarative secret management:

```
Encrypted secrets file              sops-nix activation          Runtime access
───────────────────────            ────────────────────         ──────────────
secrets.sops.yaml                  AGE decryption               /run/secrets/
(encrypted with AGE)         →     (uses /var/lib/sops-nix)  →  (tmpfs, 0400)
├─ remote_llm_api_key                                           ├─ remote_llm_api_key
├─ anthropic_api_key                                            ├─ anthropic_api_key
└─ workflow_executor_api_key                                    └─ workflow_executor_api_key
```

**Benefits:**
- ✅ Secrets encrypted at rest in `/etc/nixos/secrets/`
- ✅ Decrypted only at activation time with AGE key
- ✅ Runtime secrets on tmpfs (never written to disk)
- ✅ Strict permissions (mode 0400, owner-only)
- ✅ Zero secrets in Nix store or version control
- ✅ Declarative management via NixOS configuration

---

## Production Setup (sops-nix)

### Prerequisites

Your system already has sops-nix configured in [nix/modules/core/secrets.nix](../../nix/modules/core/secrets.nix).

### Step 1: Enable Secret Management

In `nix/hosts/<hostname>/deploy-options.local.nix`:

```nix
{
  mySystem.secrets.enable = true;
  mySystem.secrets.sopsFile = "/etc/nixos/secrets/secrets.sops.yaml";
}
```

### Step 2: Add Anthropic API Key to Secrets File

**Option A: Reuse existing `remote_llm_api_key`** (simplest)

```bash
# Edit encrypted secrets file
sops /etc/nixos/secrets/secrets.sops.yaml

# Add or update:
remote_llm_api_key: sk-ant-api03-...
```

**Option B: Add dedicated `anthropic_api_key`**

```bash
sops /etc/nixos/secrets/secrets.sops.yaml

# Add:
anthropic_api_key: sk-ant-api03-...
```

**Option C: Add dedicated `workflow_executor_api_key`**

```bash
sops /etc/nixos/secrets/secrets.sops.yaml

# Add:
workflow_executor_api_key: sk-ant-api03-...
```

### Step 3: Update Secrets Configuration

If using a new secret key (Option B or C), add it to `nix/modules/core/secrets.nix`:

```nix
secrets = {
  # ... existing secrets ...

  # Option B
  "anthropic_api_key" = {
    mode = "0400";
    owner = secretsOwner;
    group = secretsGroup;
  };

  # OR Option C
  "workflow_executor_api_key" = {
    mode = "0400";
    owner = secretsOwner;
    group = secretsGroup;
  };
};
```

### Step 4: Rebuild System

```bash
# Rebuild NixOS configuration
sudo nixos-rebuild switch

# Verify secret decryption
ls -la /run/secrets/
# Should show:
# -r-------- 1 hyperd users 107 Apr  9 18:00 remote_llm_api_key
```

### Step 5: Test Workflow Executor

```bash
# No environment variables needed!
# Executor automatically finds /run/secrets/remote_llm_api_key
python3 -m ai-stack.mcp-servers.hybrid-coordinator.workflow_executor

# Should show:
# INFO - Using Anthropic API key from sops-nix: /run/secrets/remote_llm_api_key
# INFO - LLM client initialized (provider: anthropic)
```

---

## Development Setup (Local)

### For Developers Without sops-nix

**Option 1: Local config file** (recommended for dev)

```bash
# Create config directory
mkdir -p ~/.config/anthropic

# Store API key with restricted permissions
echo "sk-ant-api03-..." > ~/.config/anthropic/api-key
chmod 600 ~/.config/anthropic/api-key

# Test
python3 -m ai-stack.mcp-servers.hybrid-coordinator.workflow_executor
```

**Option 2: Environment variable** (temporary/testing)

```bash
# Set for current session only
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Test
python3 -m ai-stack.mcp-servers.hybrid-coordinator.workflow_executor

# IMPORTANT: Don't put this in .bashrc or .zshrc!
# Environment variables can leak via process listings (ps aux)
```

**Option 3: Explicit file path**

```bash
# Store in a secure location
echo "sk-ant-api03-..." > /secure/path/anthropic.key
chmod 600 /secure/path/anthropic.key

# Point to it
export ANTHROPIC_API_KEY_FILE="/secure/path/anthropic.key"

# Test
python3 -m ai-stack.mcp-servers.hybrid-coordinator.workflow_executor
```

---

## Security Best Practices

### ✅ DO

1. **Use sops-nix in production**
   - Encrypted at rest
   - Declarative management
   - Automatic rotation support

2. **Use strict file permissions**
   ```bash
   chmod 600 ~/.config/anthropic/api-key  # Owner-only read/write
   ```

3. **Validate secret access**
   ```bash
   # Check runtime secrets
   ls -la /run/secrets/

   # Test executor can read it
   python3 -c "
   import os
   key = open('/run/secrets/remote_llm_api_key').read().strip()
   print(f'Key loaded: {key[:10]}...')
   "
   ```

4. **Rotate keys regularly**
   ```bash
   # Update encrypted file
   sops /etc/nixos/secrets/secrets.sops.yaml

   # Rebuild to decrypt new key
   sudo nixos-rebuild switch

   # Restart services
   sudo systemctl restart workflow-executor
   ```

5. **Audit secret access**
   ```bash
   # Check which processes access secrets
   sudo lsof /run/secrets/remote_llm_api_key
   ```

### ❌ DON'T

1. **Never commit plaintext API keys**
   - ❌ `export ANTHROPIC_API_KEY="sk-ant-..."` in shell scripts
   - ❌ API keys in `.env` files tracked by git
   - ❌ Keys in NixOS configuration files

2. **Never use world-readable permissions**
   - ❌ `chmod 644 api-key.txt`
   - ✅ `chmod 600 api-key.txt`

3. **Never log API keys**
   - LLM client logs key source, not key value
   - Check logs: `journalctl -u workflow-executor | grep -i "api"`

4. **Never share keys between environments**
   - Production: Use dedicated production key
   - Development: Use separate dev key
   - CI/CD: Use separate testing key

---

## Key Priority Resolution

The LLM client checks sources in order and uses the **first valid key found**:

```python
# 1. Environment variable (highest priority)
ANTHROPIC_API_KEY="sk-ant-..."

# 2. Explicit file path
ANTHROPIC_API_KEY_FILE="/path/to/key.txt"

# 3. sops-nix decrypted secrets (production)
/run/secrets/anthropic_api_key
/run/secrets/remote_llm_api_key
/run/secrets/workflow_executor_api_key

# 4. Local development files (lowest priority)
~/.config/anthropic/api-key
~/.anthropic-api-key
```

**Testing priority:**

```bash
# Temporarily override sops key for testing
ANTHROPIC_API_KEY="sk-ant-test-key" python3 -m workflow_executor

# Check which source was used
# Logs will show: "Using Anthropic API key from ANTHROPIC_API_KEY"
```

---

## Systemd Service Integration

When running executor as a systemd service, use `LoadCredential`:

```nix
systemd.services.workflow-executor = {
  description = "Workflow Executor for AI Harness";
  serviceConfig = {
    ExecStart = "${python3}/bin/python3 -m workflow_executor";
    WorkingDirectory = "/srv/ai-harness";
    User = "ai-harness";

    # Load decrypted secret as systemd credential
    LoadCredential = [
      "anthropic-api-key:/run/secrets/remote_llm_api_key"
    ];

    # Executor reads from systemd credential directory
    Environment = [
      "ANTHROPIC_API_KEY_FILE=%d/anthropic-api-key"
    ];
  };
};
```

This provides additional isolation:
- Credentials in `/run/credentials/workflow-executor.service/`
- Automatically cleaned up on service stop
- Not visible to other processes

---

## Troubleshooting

### No API Key Found

**Symptom:**
```
WARNING - No Anthropic API key found - client will fail on actual use
INFO - Mock execution mode (no LLM)
```

**Solution:**
```bash
# Check sops-nix secrets
ls -la /run/secrets/

# Check file permissions
stat /run/secrets/remote_llm_api_key

# Check if secrets module is enabled
nix eval --raw .#nixosConfigurations.<hostname>.config.mySystem.secrets.enable

# Rebuild with secrets enabled
sudo nixos-rebuild switch
```

### Permission Denied

**Symptom:**
```
PermissionError: [Errno 13] Permission denied: '/run/secrets/remote_llm_api_key'
```

**Solution:**
```bash
# Check file ownership
ls -la /run/secrets/remote_llm_api_key

# Should be owned by service user (e.g., hyperd or ai-harness)
# If not, update secrets.nix:
secretsOwner = cfg.primaryUser;  # Should match service user
```

### Wrong Key Loaded

**Symptom:**
Executor loads key from wrong source (e.g., dev file instead of sops)

**Solution:**
```bash
# Remove lower-priority sources
rm ~/.config/anthropic/api-key
rm ~/.anthropic-api-key

# Verify sops key exists
cat /run/secrets/remote_llm_api_key

# Test executor
python3 -m workflow_executor 2>&1 | grep "Using Anthropic"
# Should show: "Using Anthropic API key from sops-nix: /run/secrets/..."
```

---

## Migration Guide

### From Environment Variables to sops-nix

**Before:**
```bash
# ~/.bashrc
export ANTHROPIC_API_KEY="sk-ant-..."
```

**After:**
```bash
# Add to sops file
sops /etc/nixos/secrets/secrets.sops.yaml
# remote_llm_api_key: sk-ant-...

# Rebuild
sudo nixos-rebuild switch

# Remove from .bashrc
sed -i '/ANTHROPIC_API_KEY/d' ~/.bashrc

# Restart shell
exec $SHELL
```

### From Plain Files to sops-nix

**Before:**
```bash
cat ~/.anthropic-api-key
sk-ant-api03-...
```

**After:**
```bash
# Add to sops (copy key first)
API_KEY=$(cat ~/.anthropic-api-key)
sops /etc/nixos/secrets/secrets.sops.yaml
# remote_llm_api_key: <paste-key-here>

# Rebuild
sudo nixos-rebuild switch

# Securely delete old file
shred -u ~/.anthropic-api-key

# Verify migration
python3 -m workflow_executor 2>&1 | grep "sops-nix"
```

---

## Related Documentation

- [Workflow Executor Integration](./workflow-executor-integration.md)
- [NixOS Secrets Module](../../nix/modules/core/secrets.nix)
- [sops-nix Documentation](https://github.com/Mic92/sops-nix)

---

**Document Version:** 1.0.0
**Last Updated:** 2026-04-09
**Next Review:** After first production deployment
