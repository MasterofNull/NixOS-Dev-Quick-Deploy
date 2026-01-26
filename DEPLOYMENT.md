# AI Stack Deployment Guide

**Last Updated:** January 25, 2026
**Version:** 6.0.0 (K3s Production)

---

## Overview

This guide covers deploying the NixOS AI Stack in two configurations:

1. **K3s Kubernetes** (Recommended for production/hospital environments)
2. **Podman Compose** (Development/testing)

---

## Prerequisites

### Hardware Requirements

| Tier | RAM | CPU | Storage | Use Case |
|------|-----|-----|---------|----------|
| Minimum | 16GB | 4 cores | 50GB SSD | Development, small models |
| Recommended | 32GB | 8 cores | 100GB NVMe | Production, 7B models |
| Optimal | 64GB+ | 16 cores | 200GB+ NVMe | Large models, multi-user |

### Software Requirements

- NixOS 24.11+ or compatible Linux distribution
- Podman 5.0+ (for container runtime)
- kubectl (for K3s)
- Python 3.11+ (for scripts)

---

## Quick Start (5 Minutes)

### Option A: K3s (Production)

```bash
# 1. Clone the repository
git clone https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy.git
cd NixOS-Dev-Quick-Deploy

# 2. Initialize secrets
./scripts/manage-secrets.sh init

# 3. Verify K3s is running
kubectl get nodes

# 4. Deploy to K3s
kubectl apply -f ai-stack/kubernetes/kompose/ -n ai-stack

# 5. Verify services
kubectl get pods -n ai-stack
```

### Option B: Podman Compose (Development)

```bash
# 1. Clone the repository
git clone https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy.git
cd NixOS-Dev-Quick-Deploy

# 2. Initialize configuration
./scripts/setup-config.sh

# 3. Initialize secrets
./scripts/manage-secrets.sh init

# 4. Start the stack
export AI_STACK_ENV_FILE=$(pwd)/ai-stack/compose/.env
cd ai-stack/compose
podman compose up -d

# 5. Verify services
podman compose ps
```

---

## Detailed K3s Deployment

### Step 1: Install K3s (NixOS)

Add to `/etc/nixos/configuration.nix`:

```nix
services.k3s = {
  enable = true;
  role = "server";
  extraFlags = toString [
    "--disable traefik"
    "--write-kubeconfig-mode 644"
  ];
};
```

Then rebuild:

```bash
sudo nixos-rebuild switch
```

### Step 2: Configure kubectl

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
kubectl get nodes  # Should show "Ready"
```

### Step 3: Create Namespace and Secrets

```bash
# Create namespace
kubectl create namespace ai-stack

# Initialize secrets locally first
./scripts/manage-secrets.sh init

# Create Kubernetes secrets from files
cd ai-stack/compose
kubectl create secret generic postgres-password \
  --from-file=postgres-password=secrets/postgres_password \
  -n ai-stack

kubectl create secret generic redis-password \
  --from-file=redis-password=secrets/redis_password \
  -n ai-stack

kubectl create secret generic grafana-admin-password \
  --from-file=grafana-admin-password=secrets/grafana_admin_password \
  -n ai-stack

# Create API key secrets
for key in aidb aider-wrapper container-engine dashboard embeddings \
           hybrid-coordinator nixos-docs ralph-wiggum stack; do
  kubectl create secret generic ${key}-api-key \
    --from-file=${key}-api-key=secrets/${key//-/_}_api_key \
    -n ai-stack 2>/dev/null || true
done
```

### Step 4: Deploy Services

```bash
# Apply all manifests
kubectl apply -f ai-stack/kubernetes/kompose/ -n ai-stack

# Watch deployment progress
kubectl get pods -n ai-stack -w
```

### Step 5: Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n ai-stack

# Test core services
kubectl exec -n ai-stack deployment/aidb -- curl -s http://localhost:8091/health

# Access Grafana (ClusterIP via port-forward)
kubectl port-forward -n ai-stack svc/grafana 3002:3002
echo "Grafana: http://localhost:3002"

# Verify Prometheus targets (requires port-forward)
kubectl port-forward -n ai-stack svc/prometheus 9091:9090
curl -s http://localhost:9091/api/v1/targets | jq -r '.data.activeTargets[] | "\(.labels.instance)\t\(.health)"'
```

### Step 6: Enable Automated Backups (K3s)

```bash
# Create backups namespace + secrets (once)
kubectl create namespace backups
kubectl get secret -n ai-stack postgres-password -o json > /tmp/postgres-password.json
python - <<'PY'
import json
with open("/tmp/postgres-password.json") as f:
    secret = json.load(f)
secret["metadata"]["namespace"] = "backups"
for key in ["resourceVersion", "uid", "selfLink", "creationTimestamp", "managedFields", "ownerReferences"]:
    secret["metadata"].pop(key, None)
secret["metadata"].pop("annotations", None)
print(json.dumps(secret))
PY | kubectl apply -f -
kubectl create secret generic backup-encryption -n backups --from-literal=key=$(openssl rand -hex 32)

# Apply backup CronJobs
kubectl apply -n backups -f ai-stack/kubernetes/backup-cronjobs.yaml
kubectl get cronjobs -n backups
```

### Step 7: Enable Log Aggregation (Loki + Promtail)

```bash
kubectl apply -f ai-stack/kubernetes/logging/namespace.yaml
kubectl apply -f ai-stack/kubernetes/logging/loki.yaml
kubectl apply -f ai-stack/kubernetes/logging/promtail.yaml
kubectl get pods -n logging
```

### Step 8: TLS Certificates (External Access)

TLS issuance requires a domain + email. Use `scripts/renew-tls-certificate.sh` once details are available.

### Step 9: Network Policies (Baseline)

```bash
# Baseline policies (requires Calico/Cilium for enforcement)
kubectl apply -f ai-stack/kubernetes/network-policies/ai-stack-allow-internal.yaml
```

---

## Detailed Podman Compose Deployment

### Step 1: Initialize Configuration

```bash
# Create config directory
mkdir -p ~/.config/nixos-ai-stack

# Copy and customize environment
cp ai-stack/compose/.env.example ~/.config/nixos-ai-stack/.env

# Or use setup script
./scripts/setup-config.sh
```

### Step 2: Initialize Secrets

```bash
# Run secrets manager
./scripts/manage-secrets.sh init

# Verify secrets created
./scripts/manage-secrets.sh status
```

### Step 3: Start Services

```bash
export AI_STACK_ENV_FILE=/home/$USER/NixOS-Dev-Quick-Deploy/ai-stack/compose/.env
cd ai-stack/compose
podman compose up -d
```

### Step 4: Verify Services

```bash
# Check service status
podman compose ps

# Test health endpoints
curl -s http://localhost:8091/health | jq .

# View logs
podman compose logs -f aidb
```

---

## Service Endpoints

### Core Services

| Service | Port | Health Check |
|---------|------|--------------|
| AIDB | 8091 | `/health` |
| Embeddings | 8081 | `/health` |
| Hybrid Coordinator | 8092 | `/health` |
| PostgreSQL | 5432 | TCP connect |
| Redis | 6379 | `PING` |
| Qdrant | 6333 | `/healthz` |

### AI Services

| Service | Port | Purpose |
|---------|------|---------|
| llama-cpp | 8080 | LLM inference |
| Open WebUI | 3001 | Chat interface |
| MindsDB | 47334 | AutoML |

### Monitoring

| Service | Port | Access |
|---------|------|--------|
| Grafana | 3002 (30300 K3s) | Dashboards |
| Prometheus | 9090 | Metrics |
| Jaeger | 16686 | Tracing |

### MCP Servers

| Service | Port | Purpose |
|---------|------|---------|
| NixOS Docs | 8094 | Documentation search |
| Ralph Wiggum | 8096 | Task orchestration |
| Aider Wrapper | 8099 | Coding assistance |
| Container Engine | 8095 | Container management |
| Dashboard API | 8889 | Web dashboard backend |

---

## Configuration

### Environment Variables

Key configuration in `.env`:

```bash
# Models
LLAMA_CPP_DEFAULT_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# Memory Optimization
LLAMA_CTX_SIZE=8192
LLAMA_CACHE_TYPE_K=q4_0
LLAMA_CACHE_TYPE_V=q4_0

# Token Optimization (reduces API costs)
QUERY_EXPANSION_ENABLED=false
REMOTE_LLM_FEEDBACK_ENABLED=false
DEFAULT_MAX_TOKENS=1000

# Features
HYBRID_MODE_ENABLED=true
CONTINUOUS_LEARNING_ENABLED=true
SELF_HEALING_ENABLED=true
```

### Secrets Management

```bash
# Check secret status
./scripts/manage-secrets.sh status

# Rotate a password
./scripts/manage-secrets.sh rotate postgres_password

# Backup before changes
./scripts/manage-secrets.sh backup

# Restore from backup
./scripts/manage-secrets.sh restore backups/secrets/secrets_YYYYMMDD_HHMMSS
```

---

## Health Checks

### Quick Health Check Script

```bash
#!/bin/bash
# health-check.sh

echo "=== AI Stack Health Check ==="

# For K3s
if command -v kubectl &>/dev/null; then
    echo "K3s Pods:"
    kubectl get pods -n ai-stack --no-headers | awk '{print $1, $3}'
fi

# For Podman
if command -v podman &>/dev/null; then
    echo "Podman Containers:"
    podman ps --format "{{.Names}} {{.Status}}" | grep local-ai
fi

# Test endpoints
echo ""
echo "Service Health:"
for svc in "AIDB:8091" "Embeddings:8081" "Coordinator:8092"; do
    name=${svc%%:*}
    port=${svc##*:}
    status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health 2>/dev/null)
    if [ "$status" = "200" ]; then
        echo "  $name: OK"
    else
        echo "  $name: FAILED ($status)"
    fi
done
```

---

## Troubleshooting

### Common Issues

#### 1. Pods stuck in ContainerCreating

```bash
# Check events
kubectl describe pod <pod-name> -n ai-stack

# Common causes:
# - Secret not found: Create missing secret
# - Volume mount error: Check PVC status
# - Image pull error: Check imagePullPolicy
```

#### 2. Database Connection Failures

```bash
# Verify PostgreSQL is running
kubectl exec -n ai-stack deployment/postgres -- pg_isready

# Check password
kubectl get secret postgres-password -n ai-stack -o jsonpath='{.data.postgres-password}' | base64 -d
```

#### 3. Service Cannot Connect to Redis

```bash
# Verify Redis is running with auth
kubectl exec -n ai-stack deployment/redis -- redis-cli -a $(cat /run/secrets/redis-password) PING

# Should return: PONG
```

#### 4. llama-cpp Model Not Loading

```bash
# Check model file exists
ls -la ~/.local/share/nixos-ai-stack/llama-cpp-models/

# View logs
kubectl logs -n ai-stack deployment/llama-cpp --tail=50
```

#### 5. Permission Denied on Secrets

```bash
# Fix permissions (must be 644 for container access)
chmod 644 ai-stack/compose/secrets/*
```

#### 6. Prometheus Target Down (Ralph `/metrics` 404)

This usually means k3s is running an older Ralph image without `/metrics`.

```bash
# Rebuild image
AI_STACK_ENV_FILE=ai-stack/compose/.env podman-compose -f ai-stack/compose/docker-compose.yml build ralph-wiggum

# Import updated image into k3s (requires sudo)
ONLY_IMAGES="ralph-wiggum" FORCE_IMPORT=1 sudo -E ./scripts/import-k3s-images.sh

# Restart deployment
kubectl rollout restart -n ai-stack deployment/ralph-wiggum
```

#### 7. Open WebUI CrashLoopBackOff (Exit 137)

If Open WebUI restarts repeatedly, it may be memory‑pressure or liveness related.

```bash
# Option A: scale to 0 (optional UI)
kubectl scale -n ai-stack deployment/open-webui --replicas=0

# Option B: raise memory limits and relax liveness (edit manifest then apply)
kubectl apply -n ai-stack -f ai-stack/kubernetes/kompose/open-webui-deployment.yaml
kubectl rollout restart -n ai-stack deployment/open-webui
```

---

## Backup and Recovery

### Database Backup

```bash
# PostgreSQL
kubectl exec -n ai-stack deployment/postgres -- \
  pg_dump -U mcp mcp | gzip > backup-$(date +%Y%m%d).sql.gz

# Qdrant (snapshot)
curl -X POST http://localhost:6333/collections/nixos_docs/snapshots
```

### Secrets Backup

```bash
./scripts/manage-secrets.sh backup
```

### Full Recovery

```bash
# 1. Restore secrets
./scripts/manage-secrets.sh restore backups/secrets/secrets_YYYYMMDD_HHMMSS

# 2. Restore database
gunzip < backup-YYYYMMDD.sql.gz | kubectl exec -i -n ai-stack deployment/postgres -- psql -U mcp mcp

# 3. Restart services
kubectl rollout restart deployment -n ai-stack
```

---

## Scaling

### Horizontal Scaling (K3s)

```bash
# Scale embedding service
kubectl scale deployment embeddings -n ai-stack --replicas=3

# Scale AIDB
kubectl scale deployment aidb -n ai-stack --replicas=2
```

### Resource Limits

Edit deployment to add limits:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

---

## Security Checklist

### Pre-Deployment

- [ ] Secrets initialized (no defaults)
- [ ] `.env` not in git
- [ ] API authentication enabled
- [ ] TLS certificates configured (production)
- [ ] Network policies applied (production)

### Post-Deployment

- [ ] Health endpoints responding
- [ ] Logs show no auth failures
- [ ] Metrics being collected
- [ ] Backups scheduled

### Hospital/HIPAA

- [ ] All inference local (no cloud API for patient data)
- [ ] Audit logging enabled
- [ ] Data encryption at rest
- [ ] Access controls documented
- [ ] Incident response plan

---

## Local Registry + Kustomize Workflow

### Start local registry

```bash
./scripts/local-registry.sh start
```

### Publish locally built images

```bash
TAG=dev ALSO_TAG_DEV=1 ./scripts/publish-local-registry.sh
```

### Deploy with Kustomize (dev overlay)

```bash
kubectl apply -k ai-stack/kustomize/overlays/dev
```

### Skaffold (optional)

```bash
DOCKER_HOST=unix:///run/user/$(id -u)/podman/podman.sock \
  skaffold dev
```

---

## Support

- **Documentation:** See `/docs/` directory
- **Troubleshooting:** [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- **Secrets Guide:** [SECRETS-MANAGEMENT-GUIDE.md](SECRETS-MANAGEMENT-GUIDE.md)
- **K3s Migration:** [K3S-PORTAINER-MIGRATION-PLAN.md](K3S-PORTAINER-MIGRATION-PLAN.md)
- **Issues:** https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy/issues

---

**Version:** 6.0.0
**Deployment Target:** K3s v1.34.2+k3s1
**Container Runtime:** containerd/Podman 5.7.0
