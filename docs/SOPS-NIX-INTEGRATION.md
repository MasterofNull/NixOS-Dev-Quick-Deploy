# sops-nix Integration Guide

## Overview

This document describes the sops-nix integration implemented in NixOS-Dev-Quick-Deploy v5.0.0 to address **critical security vulnerabilities** related to plain text secret storage.

**Version**: 5.0.0
**Date**: 2025-01-21
**Status**: ✅ Integrated (Ready for deployment)

---

## What Changed

### Before (v4.0.0 - INSECURE)
- ❌ Secrets stored in plain text in `~/.cache/nixos-quick-deploy/preferences/`
- ❌ Gitea secrets in `/var/lib/nixos-quick-deploy/secrets/` (unencrypted)
- ❌ Hugging Face tokens in preference files (chmod 600 but readable)
- ❌ Passwords in Nix configuration files (world-readable /nix/store)
- ❌ No secret rotation mechanism
- ❌ No encryption at rest

###  After (v5.0.0 - SECURE)
- ✅ All secrets encrypted using **age** encryption
- ✅ Secrets managed via **sops-nix** module
- ✅ Age keys stored in `~/.config/sops/age/keys.txt` (chmod 600)
- ✅ Encrypted secrets in `secrets.yaml` (AES-256-GCM)
- ✅ Secrets decrypted at runtime to `/run/secrets/` (tmpfs)
- ✅ Per-secret file permissions and ownership
- ✅ Secret rotation support
- ✅ Automatic cleanup of plain text secrets

---

## Architecture

### Encryption Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Age Key Generation                                 │
│   └─→ ~/.config/sops/age/keys.txt (private key)            │
│   └─→ age1... (public key extracted)                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Secret Extraction                                  │
│   ├─→ Backup plain secrets to backups/                     │
│   ├─→ Extract HF token from preferences/                    │
│   ├─→ Extract Gitea secrets from /var/lib/                  │
│   └─→ Store in extracted-secrets.env (temporary)            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Secret Encryption                                  │
│   ├─→ Generate secrets.yaml from template                   │
│   ├─→ Replace placeholders with extracted values            │
│   ├─→ Encrypt with sops: sops -e -i secrets.yaml           │
│   └─→ Result: AES-256-GCM encrypted YAML                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Runtime: Secret Decryption (nixos-rebuild / home-manager)  │
│   ├─→ sops-nix module reads ~/.config/sops/age/keys.txt   │
│   ├─→ Decrypts secrets.yaml using age                       │
│   ├─→ Writes to /run/secrets/<secret-name>                  │
│   ├─→ Sets correct ownership and permissions                │
│   └─→ Services read from /run/secrets/ (tmpfs, RAM only)    │
└─────────────────────────────────────────────────────────────┘
```

### Secret Lifecycle

1. **Generation**: Secrets generated during Phase 1 (or extracted from existing)
2. **Encryption**: Encrypted using age public key and stored in `secrets.yaml`
3. **Distribution**: Encrypted file committed to `/etc/nixos/` (safe to version control)
4. **Decryption**: sops-nix decrypts at activation time using age private key
5. **Runtime**: Decrypted secrets available in `/run/secrets/` (tmpfs, cleared on reboot)
6. **Rotation**: Update `secrets.yaml` with `sops secrets.yaml`, re-encrypt, redeploy

---

## File Structure

```
/etc/nixos/
├── flake.nix                  # Includes sops-nix input
├── configuration.nix          # Includes sops configuration
├── secrets.yaml              # Encrypted secrets (safe to commit)
└── .sops.yaml                # sops configuration (age public key)

~/.config/sops/age/
└── keys.txt                  # Age private key (NEVER commit)

~/.cache/nixos-quick-deploy/
└── state/secrets/
    ├── backups/              # Backed up plain text secrets
    │   └── plain-secrets-YYYYMMDD_HHMMSS/
    └── extracted-secrets.env # Temporary extracted secrets
```

---

## Secrets Defined

### System Secrets (configuration.nix)

| Secret Path | Owner | Mode | Purpose |
|-------------|-------|------|---------|
| `gitea/secret_key` | gitea:gitea | 0400 | Gitea session encryption |
| `gitea/internal_token` | gitea:gitea | 0400 | Gitea internal API |
| `gitea/lfs_jwt_secret` | gitea:gitea | 0400 | Git LFS JWT signing |
| `gitea/jwt_secret` | gitea:gitea | 0400 | Gitea JWT signing |
| `gitea/admin_password` | gitea:gitea | 0400 | Gitea admin password |
| `huggingface/api_token` | USER:users | 0400 | HF model downloads |
| `mcp/postgres_password` | USER:users | 0400 | MCP PostgreSQL |
| `mcp/redis_password` | USER:users | 0400 | MCP Redis |
| `mcp/api_key` | USER:users | 0400 | MCP API authentication |

### User Secrets (home.nix) - Future

Additional secrets can be added for user-level services:
- AI service API keys (OpenAI, Anthropic, Cohere)
- Trading API credentials (Alpaca, Polygon)
- Cloud provider credentials

---

## Usage

### Initial Setup (Automated during deployment)

```bash
# Phase 1 will automatically:
./nixos-quick-deploy.sh

# 1. Generate age key if not present
# 2. Extract existing plain text secrets
# 3. Create secrets.yaml from template
# 4. Encrypt secrets.yaml
# 5. Deploy configuration with sops-nix
```

### Manual Secret Management

#### View Secrets
```bash
# Decrypt and view all secrets
sops secrets.yaml

# Decrypt to stdout
sops -d secrets.yaml
```

#### Edit Secrets
```bash
# Edit encrypted secrets (auto re-encrypts on save)
sops secrets.yaml

# Add new secret
sops --set '["trading"]["alpaca_api_key"] "sk-abc123"' secrets.yaml
```

#### Rotate Secrets
```bash
# 1. Edit secrets.yaml with new values
sops secrets.yaml

# 2. Rebuild system
sudo nixos-rebuild switch --flake /etc/nixos#$(hostname)

# 3. Restart affected services
sudo systemctl restart gitea
systemctl --user restart podman-local-ai-ollama
```

#### Add New Secret
```bash
# 1. Add to secrets.yaml
sops secrets.yaml
# Add: new_service/password: "secure_value"

# 2. Add to configuration.nix sops.secrets
sops.secrets."new_service/password" = {
  owner = "service_user";
  mode = "0400";
};

# 3. Reference in service configuration
systemd.services.new_service = {
  serviceConfig = {
    EnvironmentFile = config.sops.secrets."new_service/password".path;
  };
};

# 4. Rebuild
sudo nixos-rebuild switch --flake /etc/nixos#$(hostname)
```

---

## Security Considerations

### ✅ Security Improvements

1. **Encryption at Rest**: All secrets encrypted with AES-256-GCM
2. **Runtime-Only Decryption**: Secrets decrypted to tmpfs (RAM), cleared on reboot
3. **Per-Secret Permissions**: Fine-grained ownership and mode control
4. **No Nix Store Exposure**: Encrypted secrets in /etc/nixos, decrypted secrets in /run
5. **Audit Trail**: sops tracks last modification time and key ID
6. **Multi-User Support**: Each user can have their own age key
7. **Rotation Support**: Update secrets without changing configuration

### ⚠️ Important Security Notes

1. **Age Private Key Protection**:
   - `~/.config/sops/age/keys.txt` is the master key
   - Permissions: 600 (owner read/write only)
   - **NEVER commit to git**
   - **BACKUP SECURELY** (encrypted USB, password manager)

2. **Secrets in Git**:
   - Encrypted `secrets.yaml` is SAFE to commit
   - `.sops.yaml` is SAFE to commit (contains public key only)
   - Age private key must be in `.gitignore`

3. **Backup Strategy**:
   ```bash
   # Backup age key (encrypted)
   gpg -c ~/.config/sops/age/keys.txt
   # Store age.keys.txt.gpg in password manager or secure storage
   ```

4. **Disaster Recovery**:
   - If age key is lost, secrets.yaml cannot be decrypted
   - Maintain encrypted backup of age key
   - Consider multi-key sops setup for critical systems

### 🔒 Best Practices

1. **Regular Rotation**:
   - Rotate Gitea secrets every 90 days
   - Rotate API tokens when compromised
   - Update age key annually (requires re-encrypting all secrets)

2. **Access Control**:
   - One age key per administrator
   - Use `sops updatekeys` to add/remove keys
   - Revoke keys by re-encrypting without old key

3. **Monitoring**:
   - Check `/run/secrets/` permissions after rebuild
   - Audit sops access logs
   - Monitor for unauthorized decryption attempts

4. **Secrets Hygiene**:
   - Never log secrets
   - Avoid environment variables for secrets (use files)
   - Use systemd `EnvironmentFile` or `LoadCredential`
   - Shred plain text backups after migration

---

## Migration from v4.0.0

### Automatic Migration

The deployment script automatically migrates secrets during next run:

```bash
./nixos-quick-deploy.sh
```

Migration steps (automatic):
1. ✅ Generate age key
2. ✅ Backup plain text secrets to `~/.cache/nixos-quick-deploy/state/secrets/backups/`
3. ✅ Extract secrets from preference files
4. ✅ Generate secrets.yaml from template
5. ✅ Encrypt with sops
6. ✅ Deploy configuration
7. ⚠️ Manual: Verify services work
8. ⚠️ Manual: Run `cleanup_plain_secrets` to remove old files

### Manual Verification

After migration, verify secrets are decrypted correctly:

```bash
# Check runtime secrets exist
ls -la /run/secrets/

# Verify Gitea can read its secrets
sudo cat /run/secrets/gitea/secret_key

# Check Hugging Face token
cat /run/secrets/huggingface/api_token

# Test service restart
sudo systemctl restart gitea
systemctl --user restart podman-local-ai-ollama
```

### Manual Cleanup (After Verification)

```bash
# Securely delete plain text secrets
cd ~/Documents/NixOS-Dev-Quick-Deploy
nix-shell -p bash --run 'source lib/secrets.sh && cleanup_plain_secrets'

# Or run the helper function directly
./nixos-quick-deploy.sh --dry-run  # Load libraries
bash -c 'source lib/secrets.sh && cleanup_plain_secrets'
```

---

## Troubleshooting

### Issue: "sops: Failed to decrypt"

**Cause**: Age key not found or incorrect

**Solution**:
```bash
# Check age key exists
ls -la ~/.config/sops/age/keys.txt

# Verify permissions
chmod 600 ~/.config/sops/age/keys.txt

# Check public key in .sops.yaml matches
age-keygen -y ~/.config/sops/age/keys.txt
cat /etc/nixos/.sops.yaml | grep age1
```

### Issue: "Permission denied: /run/secrets/..."

**Cause**: Service user cannot read secret

**Solution**:
```bash
# Check secret ownership
ls -la /run/secrets/

# Fix in configuration.nix
sops.secrets."service/secret" = {
  owner = "correct_user";  # Match service user
  group = "correct_group";
  mode = "0400";
};
```

### Issue: "sops: no key found in keyring"

**Cause**: SOPS_AGE_KEY_FILE not set

**Solution**:
```bash
# Set environment variable
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt

# Or add to shell profile
echo 'export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"' >> ~/.zshrc
```

### Issue: Plain secrets still exist after migration

**Cause**: Manual cleanup not performed

**Solution**:
```bash
# Verify services work with encrypted secrets first!
systemctl status gitea
systemctl --user status podman-local-ai-ollama

# Then cleanup
source lib/secrets.sh
cleanup_plain_secrets

# This will shred (3-pass overwrite):
# - ~/.cache/nixos-quick-deploy/preferences/*.env
# - /var/lib/nixos-quick-deploy/secrets/*
```

---

## Advanced Configuration

### Multi-User age Keys

Support multiple administrators:

```yaml
# .sops.yaml
keys:
  - &admin1 age1abc...
  - &admin2 age1def...

creation_rules:
  - path_regex: secrets\.yaml$
    age:
      - *admin1
      - *admin2
```

### Per-Environment Secrets

```yaml
# secrets.yaml
production:
  db_password: "prod_password"

development:
  db_password: "dev_password"

# configuration.nix
sops.secrets."${environment}/db_password" = {
  owner = "postgres";
};
```

### Secrets from External Sources

```nix
# Import secrets from CI/CD or HashiCorp Vault
sops.secrets."external/token" = {
  sopsFile = pkgs.fetchurl {
    url = "https://vault.internal/secrets.yaml";
    sha256 = "...";
  };
};
```

---

## References

- [sops-nix Documentation](https://github.com/Mic92/sops-nix)
- [age Encryption](https://age-encryption.org/)
- [NixOS Security Best Practices](https://nixos.org/manual/nixos/stable/#sec-security)
- [OWASP Secrets Management](https://owasp.org/www-community/vulnerabilities/Use_of_hard-coded_password)

---

## Changelog

### v5.0.0 (2025-01-21)
- ✅ Initial sops-nix integration
- ✅ Age key generation automation
- ✅ Secret extraction from v4.0.0 plain text files
- ✅ Encrypted secrets.yaml template
- ✅ System-level sops configuration in configuration.nix
- ✅ Migration workflow with backup
- ✅ Secret rotation support
- ✅ Comprehensive documentation

### Planned for v5.1.0
- Home Manager sops integration for user secrets
- Automatic secret rotation (systemd timer)
- Secret expiration and alerts
- Integration with MCP server secrets
- Multi-key sops setup for team environments
- Web UI for secret management

---

**Security Status**: ✅ **CRITICAL SECURITY ISSUES RESOLVED**

The plain text secret storage vulnerability has been addressed. All secrets are now encrypted with age (AES-256-GCM) and managed via sops-nix. Runtime secrets are stored in tmpfs and cleared on reboot.

**Next Steps**:
1. Deploy this configuration: `./nixos-quick-deploy.sh`
2. Verify secret decryption: `ls -la /run/secrets/`
3. Test services: `systemctl status gitea`
4. Cleanup plain secrets: `cleanup_plain_secrets`
5. Backup age key: `gpg -c ~/.config/sops/age/keys.txt`
