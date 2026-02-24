# Security Setup Guide - Production Hardening

This guide covers setting up secure secrets management for the AI stack (K3s + SOPS/age).

## Overview

The AI stack stores secrets in SOPS-encrypted Kubernetes manifests. **Never commit plaintext secrets to git.**

## Files Involved

- **`ai-stack/kubernetes/secrets/secrets.sops.yaml`** - Encrypted K8s secrets (source of truth)
- **`~/.config/sops/age/keys.txt`** - Age key used by SOPS
- **`config/settings.sh`** - Secrets paths and toggles
- **`~/.config/nixos-ai-stack/.env`** - Optional local overrides (never commit)

## Quick Setup

0. **Recommended (production): edit the encrypted secrets bundle:**
   ```bash
   sops ai-stack/kubernetes/secrets/secrets.sops.yaml
   ```

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
   # Re-apply manifests and restart affected workloads
   kubectl apply -k ai-stack/kustomize/overlays/dev
   kubectl rollout restart deployment/postgres -n ai-stack
   kubectl rollout restart deployment/aidb -n ai-stack
   ```

## Secret Priority (P1-SEC-003)

The system loads secrets in this order (later sources override earlier ones):

1. **Config file value** (`config.yaml`)
2. **Environment variable** (`.env` file)
3. **Kubernetes Secret** (K3s-managed secrets)

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
- ✅ **Kubernetes Secrets override config values**
- ✅ **Environment variables (`.env`) are used for local/dev overrides**
- ✅ **Defaults in config.yaml are fallbacks only**

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

## Internal TLS / mTLS Strategy (Phase 1.2.6)

Current state: edge TLS via ingress; **internal pod-to-pod traffic is still HTTP**.
To close this gap, choose one of the following strategies:

### Option A: Cilium (Recommended if enabling NetworkPolicy enforcement)
- **Why:** Cilium provides both NetworkPolicy enforcement and mTLS via service mesh.
- **Impact:** One CNI to manage policies + encryption.
- **Plan:**
  1. Install Cilium with kube-proxy replacement disabled (K3s) unless explicitly required.
  2. Enable Cilium service mesh and mTLS for `ai-stack` namespace.
  3. Validate connectivity + mTLS metrics.

### Option B: Linkerd (Lightweight mTLS, keep existing CNI)
- **Why:** Minimal footprint and strong mTLS defaults.
- **Impact:** Requires running Linkerd control-plane + sidecars.
- **Plan:**
  1. Install Linkerd.
  2. Inject Linkerd into `ai-stack` namespace.
  3. Validate mTLS with `linkerd viz` and pod-to-pod tests.

### Option C: Per‑service TLS (Fallback)
- **Why:** Works without service mesh, but requires client changes.
- **Impact:** Each service must trust the internal CA; all clients must be updated.
- **Plan:**
  1. Issue per-service certs via cert-manager.
  2. Update service configs to use HTTPS and validate CA.
  3. Update all internal clients (AIDB ↔ Qdrant/Postgres/Redis/etc).

### Recommended Path
- If we adopt **Cilium** for NetworkPolicy enforcement, use **Cilium mTLS** to solve both acceptance gaps together.
- If policy enforcement is delayed, **Linkerd** can be adopted independently for mTLS.

## TLS Secret Inventory (K3s)

The following TLS secrets are present in `ai-stack` (cert-manager managed), but
**internal clients still use HTTP** until 1.2.7 is completed:

- `aidb-tls-secret`
- `embeddings-tls-secret`
- `grafana-tls-secret`
- `hybrid-coordinator-tls-secret`
- `nginx-tls-secret`
- `postgres-tls-secret`
- `ralph-wiggum-tls-secret`
- `redis-tls-secret`

Once internal TLS is enabled, update service configs to use the HTTPS endpoints
and validate against the cluster CA.

### Client Env Overrides (Internal TLS)

These variables are now supported by AIDB and Hybrid to enable TLS **when**
the backing services are configured for it:

```bash
# AIDB Postgres/Redis
AIDB_POSTGRES_SSLMODE=verify-full
AIDB_POSTGRES_SSLROOTCERT=/etc/ssl/certs/ai-stack-ca.crt
AIDB_REDIS_TLS=true
AIDB_REDIS_SSL_CA=/etc/ssl/certs/ai-stack-ca.crt

# Hybrid learning pipeline (Postgres)
POSTGRES_SSLMODE=verify-full
POSTGRES_SSLROOTCERT=/etc/ssl/certs/ai-stack-ca.crt
```

Mount the CA cert into pods before enabling these flags (e.g., via a dedicated
secret/configmap overlay).

---

## Firewall / Ingress Audit

Run the audit to confirm exposed ports match the intended surface area and that the firewall is enabled:

```bash
./scripts/firewall-audit.sh
```

Checklist:
- Only required ports are open (dashboard, registry, ingress as needed).
- Dashboard services bind to localhost by default (`DASHBOARD_BIND_ADDRESS=127.0.0.1`, `DASHBOARD_API_BIND_ADDRESS=127.0.0.1`).
- Podman TCP API (2375) is localhost-only or disabled unless explicitly required.
- If container-engine runs with `hostNetwork`, restrict host port `8095` via firewall or change the bind address.
- Local registry binds to localhost (`127.0.0.1:5000`) to avoid LAN exposure.
- K3s API is not exposed publicly unless explicitly required.
- Document any public-facing services in this file.

Note: The template firewall now allowlists `8095`, `10250`, and `6443` only for
pod/service CIDRs (10.42.0.0/16, 10.43.0.0/16). Apply via NixOS rebuild to take
effect on hosts.

## Podman TCP API Lockdown

The Podman TCP API is high-risk if exposed on `0.0.0.0`. Use the helper to bind it
to localhost (or disable it entirely). The container-engine MCP service now uses
`hostNetwork: true` with `PODMAN_API_URL=http://127.0.0.1:2375` to preserve access
without exposing the API to the LAN.

```bash
# Bind Podman API to localhost (recommended)
./scripts/configure-podman-tcp.sh --bind 127.0.0.1

# Or disable the TCP API entirely
./scripts/configure-podman-tcp.sh --disable
```

## Verification

### Test 1: Secrets Loaded
```bash
# Ensure the secret exists and is non-empty
kubectl get secret postgres-password -n ai-stack -o jsonpath='{.data.password}' | grep -q . && echo "PASS"
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
# Should show: 600 $HOME/.config/nixos-ai-stack/.env
```

### Test 5: TLS Log Scan
```bash
./scripts/check-tls-log-warnings.sh
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
   kubectl rollout restart deployment/postgres -n ai-stack
   kubectl rollout restart deployment/aidb -n ai-stack
   ```

### Issue: "AIDB_POSTGRES_PASSWORD not set"
**Cause:** Secret not applied or env file not converted into K8s secrets

**Fix:**
1. Check the secret bundle exists and is decrypted:
   ```bash
   ls -la ai-stack/kubernetes/secrets/secrets.sops.yaml
   ```

2. Ensure SOPS/age is available and decryptible:
   ```bash
   sops -d ai-stack/kubernetes/secrets/secrets.sops.yaml >/dev/null
   ```

3. Re-apply secrets:
   ```bash
   ./nixos-quick-deploy.sh --run-phase 9
   ```

### Issue: "Still using change_me_in_production"
**Cause:** Old container with cached environment

**Fix:**
1. Remove the stale secret:
   ```bash
   kubectl delete secret postgres-password -n ai-stack
   ```

2. Re-apply encrypted secrets and restart:
   ```bash
   ./nixos-quick-deploy.sh --run-phase 9
   kubectl rollout restart deployment/postgres -n ai-stack
   kubectl rollout restart deployment/aidb -n ai-stack
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
