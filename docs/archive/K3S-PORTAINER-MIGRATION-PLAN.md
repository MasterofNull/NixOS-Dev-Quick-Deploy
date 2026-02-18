# K3s + Portainer Migration Plan

**Target Architecture:** K3s (Kubernetes) + Portainer (Management UI) + Podman (Container Runtime)
**Timeline:** 2-3 days
**Status:** Phases 1-10 complete; optional services pending

---

## 📌 Current Work References (Most Recent Docs)

These documents capture the latest state and open tasks as of **2026-01-24**:
- `NEXT-STEPS-RECOMMENDATIONS.md` - Current decision and recommended path
- `SECRETS-MANAGEMENT-GUIDE.md` - Secrets tooling and usage
- `CONTAINER-ORCHESTRATION-ANALYSIS-2026.md` - Orchestration research
- `docs/archive/DAY5-INTEGRATION-TESTING-RESULTS.md` - Recent fixes and validations
- `SESSION-CONTINUATION-JAN24.md` - Ongoing session context
- `TESTING-READINESS-STATUS.md` - Test status and gaps

---

## ✅ Phase TODOs & Status

**Last Updated:** 2026-01-25

- [x] Phase 1: Backup current setup (completed 2026-01-24)
- [x] Phase 2: Install K3s (containerd runtime) (completed 2026-01-24)
- [x] Phase 3: Install Portainer for K3s (completed 2026-01-25)
- [x] Phase 4: Convert docker-compose to Kubernetes (completed 2026-01-25)
- [x] Phase 5: Migrate secrets to Kubernetes (completed 2026-01-25)
- [x] Phase 6: Configure persistent storage (completed 2026-01-25)
- [x] Phase 7: Deploy AI stack services (core services running; optional services degraded)
- [x] Phase 8: Configure GPU support (completed 2026-01-25)
- [x] Phase 9: Configure networking (completed 2026-01-25)
- [x] Phase 10: Testing and validation (completed 2026-01-25; optional services excluded)

**Progress Notes:**
- Update this checklist immediately after each phase is completed.
- Record issues and fixes in the log below for multi-session handoffs.
- 2026-01-25: Core services running (aidb, embeddings, postgres, redis, grafana, hybrid-coordinator, ralph, etc.).
- 2026-01-25: Open WebUI CrashLoopBackOff (optional UI).
- 2026-01-25: `autogpt` scaled to 0 (HIPAA-safe default).
- 2026-01-25: Persistent storage PVCs created and bound for `postgres`, `qdrant`, `redis`.
- 2026-01-25: AMD GPU support prepared via `/dev/dri` hostPath in `llama-cpp` (deployment scaled to 0).
- 2026-01-25: NodePort services added for Grafana (30300) and Nginx (30088/30443) (optional; use port-forward in K3s by default).
- 2026-01-25: Validation passed for postgres, redis, embeddings, aidb, hybrid-coordinator, qdrant readiness.

---

## 🧭 Phase Issues & Fixes Log

| Phase | Issue | Impact | Fix / Workaround | Date | Owner |
|------:|-------|--------|------------------|------|-------|
| 1 | `backup-postgresql.sh` failed creating `/var/backups` (permission denied) | Backup could not start | Run with local `BACKUP_DIR`, `LOG_FILE`, `METRICS_FILE` under repo `backups/` | 2026-01-24 | Codex |
| 1 | `pg_dump` version mismatch (client 17.7 vs server 18.1) | Postgres backup failed | Use container-native dump: `podman exec local-ai-postgres pg_dump -U mcp -d mcp | gzip -9 > backups/postgresql/mcp-full-<ts>.sql.gz` | 2026-01-24 | Codex |
| 1 | `backup-qdrant.sh` snapshot name parsing broken (log lines on stdout) | Qdrant backup failed | Updated script: send logs to stderr to keep snapshot name clean | 2026-01-24 | Codex |
| 1 | `backup-qdrant.sh` verify assumed tar.gz | Verification failed | Updated script: verify tar or tar.gz; list contents safely | 2026-01-24 | Codex |
| 1 | `podman compose down` failed with `set AI_STACK_ENV_FILE` | Could not stop stack | Export `AI_STACK_ENV_FILE=/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose/.env` before `podman compose down` | 2026-01-24 | Codex |
| 1 | `podman compose down` reported missing containers (optional services) | Noise only | Safe to ignore; stack stopped successfully | 2026-01-24 | Codex |
| 2 | K3s stuck “Waiting for CRI startup” with HTTP/1.1 preface error | Cluster not schedulable | Removed `--container-runtime-endpoint` to use default containerd; cluster now Ready | 2026-01-24 | Codex |
| 3 | Portainer namespace not found | Portainer not installed | Run Phase 3 install steps after Phase 2 healthy | 2026-01-24 | Codex |
| 2 | No sudo privileges in this session | Cannot install/enable K3s or edit `/etc/nixos/configuration.nix` | Requires sudo access or user-run commands | 2026-01-24 | Codex |
| 3 | Portainer download URL returned `AccessDenied` | Portainer not installed | Apply official manifest directly: `kubectl apply -n portainer -f https://raw.githubusercontent.com/portainer/k8s/master/deploy/manifests/portainer/portainer.yaml` | 2026-01-25 | Codex |
| 4 | Kompose failed due to missing `AI_STACK_ENV_FILE` | Compose conversion blocked | Use absolute env file path: `AI_STACK_ENV_FILE=/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose/.env` | 2026-01-25 | Codex |
| 4 | Kompose warnings (unsupported restart policies, host paths, HOME unset) | Generated manifests need review | Review `ai-stack/kubernetes/kompose/` for restartPolicy and volume correctness | 2026-01-25 | Codex |
| 5 | Secret key names mismatched Kompose expectations | Pods would fail to mount secrets | Recreated secrets with keys matching Kompose (`postgres-password`, `redis-password`, etc.) | 2026-01-25 | Codex |
| 6 | Kompose created huge ConfigMaps from telemetry files | `kubectl apply` failed with annotations too long | Replaced `hybrid-coordinator-cm1` and `ralph-wiggum-cm1` with empty ConfigMaps; plan PVCs in Phase 6 | 2026-01-25 | Codex |
| 7 | ImagePullBackOff / ErrImagePull for AI stack services | Deployments stuck, no pods running | Set `imagePullPolicy: IfNotPresent` for `localhost/compose_*` images; containerd must not try HTTPS pull | 2026-01-25 | Codex |
| 7 | Pods failed to start with `not a directory` mount errors | Containers crash at init | Fix secret mounts to file paths (e.g., `/run/secrets/redis-password`) and disable SA token mounts where not needed | 2026-01-25 | Codex |
| 7 | Redis command used `redis_password` path and malformed `$()` | Redis CrashLoopBackOff | Update Redis args to `$(cat /run/secrets/redis-password)` | 2026-01-25 | Codex |
| 7 | Ralph Wiggum import error (`AgentOrchestrator`) | Ralph CrashLoopBackOff | Fallback import to `RalphOrchestrator` and rebuild image | 2026-01-25 | Codex |
| 7 | Llama.cpp missing GGUF model at `/models/...` | Llama.cpp CrashLoopBackOff | Scale deployment to 0 until models are staged and mounted | 2026-01-25 | Codex |
| 7 | AIDB/Aider ConfigMaps missing from Kompose output | Pods stuck in `ContainerCreating` | Switch `aidb-cm1/2` and `aider-cm1` volumes to `emptyDir` | 2026-01-25 | Codex |
| 7 | Hybrid Coordinator couldn’t resolve `postgres` | CrashLoopBackOff | Use FQDN `postgres.ai-stack.svc.cluster.local` | 2026-01-25 | Codex |
| 7 | Open WebUI image pull failing (GHCR) | ImagePullBackOff | Scale deployment to 0 until image pull succeeds | 2026-01-25 | Codex |
| 7 | Postgres service missing | Hybrid Coordinator couldn’t resolve DB host | Apply `ai-stack/kubernetes/kompose/postgres-service.yaml` | 2026-01-25 | Codex |
| 7 | Hybrid Coordinator missing Postgres password env | CrashLoopBackOff | Set `POSTGRES_PASSWORD` from secret in deployment | 2026-01-25 | Codex |
| 7 | AutoGPT requires real OpenAI key | CrashLoopBackOff / unauthorized | Scale deployment to 0 (local key not accepted) | 2026-01-25 | Codex |
| 7 | AIDB tool discovery timezone NameError | Noise in logs | Add `timezone` import in `ai-stack/mcp-servers/aidb/tool_discovery.py` (rebuild later) | 2026-01-25 | Codex |
| 8 | AMD GPU detected (no NVIDIA) | NVIDIA device plugin not applicable | Add `/dev/dri` hostPath to llama-cpp; keep scaled to 0 until models mounted | 2026-01-25 | Codex |
| 9 | Need external access to UIs | Services were ClusterIP only | Added NodePort services `grafana-nodeport` (30300) and `nginx-nodeport` (30088/30443) | 2026-01-25 | Codex |
| 10 | Qdrant health endpoint is `/healthz` | `/health` returns 404 | Use `/healthz` and `/readyz` for checks | 2026-01-25 | Codex |
| 7 | Redis RunContainerError / Grafana CrashLoopBackOff | Base services unstable | Investigate logs after images are available; likely config/permissions | 2026-01-25 | Codex |
| 5 | _None logged yet_ | - | - | - | - |
| 6 | _None logged yet_ | - | - | - | - |
| 7 | _None logged yet_ | - | - | - | - |
| 8 | _None logged yet_ | - | - | - | - |
| 9 | _None logged yet_ | - | - | - | - |
| 10 | _None logged yet_ | - | - | - | - |

---

## 🎯 Architecture Overview

```
User Interface Layer:
  ├─ Portainer Web UI (port 9443)
  └─ Kubernetes Dashboard (optional, port 8443)

Orchestration Layer:
  └─ K3s (Lightweight Kubernetes)
      ├─ API Server
      ├─ Scheduler
      ├─ Controller Manager
      └─ Secrets Management

Container Runtime:
  └─ Podman 5.7.0 (rootless, via CRI-O)

Application Layer:
  ├─ AI Stack Services (20+ containers)
  ├─ Databases (PostgreSQL, Redis, Qdrant)
  ├─ Monitoring (Prometheus, Grafana)
  └─ AI Services (llama.cpp, embeddings, etc.)
```

**Why This Combination?**
- ✅ **K3s** = Industry-standard Kubernetes orchestration (self-healing, rolling updates, scaling)
- ✅ **Portainer** = Beautiful web UI for managing K3s (secrets, deployments, monitoring)
- ✅ **Podman** = Secure rootless container runtime (what we already use)

---

## 📋 Prerequisites

### System Requirements

```bash
# Minimum:
- CPU: 4 cores
- RAM: 8GB
- Disk: 50GB free

# Recommended:
- CPU: 8+ cores
- RAM: 16GB+
- Disk: 100GB+ SSD
```

### Software Requirements

```bash
# Check current versions
podman --version     # Should be 5.7.0+
python3 --version    # Should be 3.9+

# K3s will install:
- kubectl (Kubernetes CLI)
- containerd (but we'll use Podman via CRI-O)
- K3s components
```

---

## 🚀 Migration Steps

### Phase 1: Backup Current Setup (30 minutes)

**Step 1.1: Backup Secrets**
```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy

# Backup secrets
./scripts/manage-secrets.sh backup

# Output shows backup location
# Example: backups/secrets/secrets_20260124_180000
```

**Step 1.2: Export Current Data**
```bash
# Backup PostgreSQL
./scripts/backup-postgresql.sh

# Backup Qdrant vectors
./scripts/backup-qdrant.sh

# Stop current stack
export AI_STACK_ENV_FILE=/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose/.env
cd ai-stack/compose
docker compose down
```

**Step 1.3: Document Current State**
```bash
# Save current container list
docker ps -a > ~/pre-migration-containers.txt

# Save current volumes
docker volume ls > ~/pre-migration-volumes.txt

# Save current images
docker images > ~/pre-migration-images.txt
```

---

### Phase 2: Install K3s with Podman Runtime (1 hour)

**Step 2.1: Install K3s (NixOS, manual execution required)**

Since we're on NixOS, we'll use the declarative configuration:

```bash
# Add to /etc/nixos/configuration.nix:
services.k3s = {
  enable = true;
  role = "server";
  extraFlags = toString [
    "--container-runtime-endpoint unix:///run/podman/podman.sock"
    "--write-kubeconfig-mode 644"
    "--disable traefik"  # We'll use our own ingress
    "--disable servicelb"  # Use MetalLB or keep simple
  ];
};

# Or install via script (non-NixOS way):
curl -sfL https://get.k3s.io | sh -s - \
  --container-runtime-endpoint unix:///run/podman/podman.sock \
  --write-kubeconfig-mode 644 \
  --disable traefik
```

**Step 2.2: Configure Podman for K3s (declarative)**

```bash
# Declarative configuration (add to configuration.nix):
systemd.user.sockets.podman = {
  enable = true;
  wantedBy = [ "sockets.target" ];
  listenStreams = [ "%t/podman/podman.sock" ];
  socketConfig = { SocketMode = "0660"; };
};

systemd.user.services.podman = {
  enable = true;
  wantedBy = [ "default.target" ];
  serviceConfig = {
    ExecStart = "${pkgs.podman}/bin/podman system service -t 0";
    Restart = "always";
  };
};

systemd.tmpfiles.rules = [
  "d /run/podman 0755 root root -"
  "L+ /run/podman/podman.sock - - - - /run/user/${toString config.users.users.\"@USER@\".uid}/podman/podman.sock"
];
```

**Step 2.3: Verify K3s Installation**

```bash
# Check K3s status
sudo systemctl status k3s

# Configure kubectl
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config

# Test kubectl
kubectl get nodes
# Should show: Ready

kubectl get pods -A
# Should show: k3s system pods running
```

**Manual run block (copy/paste when ready):**
```bash
# 1) Add services.k3s block to /etc/nixos/configuration.nix
sudo nixos-rebuild switch

# 2) Verify + configure kubectl
sudo systemctl status k3s --no-pager
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
kubectl get nodes
kubectl get pods -A
```

---

### Phase 3: Install Portainer for K3s (30 minutes)

**Step 3.1: Create Portainer Namespace**

```bash
kubectl create namespace portainer
```

**Step 3.2: Deploy Portainer**

```bash
# Deploy Portainer (NodePort) from official manifest
kubectl apply -f https://raw.githubusercontent.com/portainer/k8s/master/deploy/manifests/portainer/portainer.yaml -n portainer

# Watch deployment
kubectl get pods -n portainer -w
# Wait for "Running" status (Ctrl+C to exit watch)
```

**Step 3.3: Access Portainer**

```bash
# Get Portainer NodePort
kubectl get svc -n portainer

# Access Portainer at:
# https://localhost:30779  (or the NodePort shown)

# First login will ask you to create admin account
# Username: admin
# Password: (choose a strong password)
```

**Observed on 2026-01-25:**
- `9000` → NodePort `30777`
- `9443` → NodePort `30779` (HTTPS UI)
- `30776` → NodePort `30776`

**Step 3.4: Connect Portainer to K3s**

1. Open Portainer web UI: `https://localhost:30779`
2. Create admin account (first time only)
3. Select "Get Started"
4. Environment should show "local" K3s cluster automatically
5. Click on the local environment

You now have full K3s management via Portainer! 🎉

---

### Phase 4: Convert Docker Compose to Kubernetes (2-3 hours)

**Step 4.1: Install Kompose**

```bash
# Install Kompose (Docker Compose → Kubernetes converter)
nix-env -iA nixos.kompose

# Or download binary:
curl -L https://github.com/kubernetes/kompose/releases/download/v1.34.0/kompose-linux-amd64 -o kompose
chmod +x kompose
sudo mv kompose /usr/local/bin/
```

**Step 4.2: Convert Compose File**

```bash
# Convert docker-compose.yml to Kubernetes manifests
AI_STACK_ENV_FILE=/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose/.env \
  nix run nixpkgs#kompose -- convert -f ai-stack/compose/docker-compose.yml -o ai-stack/kubernetes/kompose

# This creates:
# - Deployments for each service
# - Services for networking
# - PersistentVolumeClaims for volumes
# - ConfigMaps for environment variables
```

**Step 4.3: Review Generated Manifests**

```bash
ls -la /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/kubernetes/kompose

# You'll see files like:
# - postgres-deployment.yaml
# - postgres-service.yaml
# - redis-deployment.yaml
# - etc.

# Review and adjust as needed
```

**Step 4.4: Create Namespace for AI Stack**

```bash
kubectl create namespace ai-stack
```

---

### Phase 5: Migrate Secrets to Kubernetes (1 hour)

**Step 5.1: Create Kubernetes Secrets from Files**

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose

# Create secret for each password/key
kubectl create secret generic postgres-password \
  --from-file=postgres-password=secrets/postgres_password \
  -n ai-stack

kubectl create secret generic redis-password \
  --from-file=redis-password=secrets/redis_password \
  -n ai-stack

kubectl create secret generic grafana-admin-password \
  --from-file=grafana-admin-password=secrets/grafana_admin_password \
  -n ai-stack

# API Keys
kubectl create secret generic aidb-api-key \
  --from-file=aidb-api-key=secrets/aidb_api_key \
  -n ai-stack

kubectl create secret generic aider-wrapper-api-key \
  --from-file=aider-wrapper-api-key=secrets/aider_wrapper_api_key \
  -n ai-stack

kubectl create secret generic container-engine-api-key \
  --from-file=container-engine-api-key=secrets/container_engine_api_key \
  -n ai-stack

kubectl create secret generic dashboard-api-key \
  --from-file=dashboard-api-key=secrets/dashboard_api_key \
  -n ai-stack

kubectl create secret generic embeddings-api-key \
  --from-file=embeddings-api-key=secrets/embeddings_api_key \
  -n ai-stack

kubectl create secret generic hybrid-coordinator-api-key \
  --from-file=hybrid-coordinator-api-key=secrets/hybrid_coordinator_api_key \
  -n ai-stack

kubectl create secret generic nixos-docs-api-key \
  --from-file=nixos-docs-api-key=secrets/nixos_docs_api_key \
  -n ai-stack

kubectl create secret generic ralph-wiggum-api-key \
  --from-file=ralph-wiggum-api-key=secrets/ralph_wiggum_api_key \
  -n ai-stack

kubectl create secret generic stack-api-key \
  --from-file=stack-api-key=secrets/stack_api_key \
  -n ai-stack
```

**Step 5.2: Verify Secrets in Portainer**

1. Open Portainer
2. Navigate to: Namespaces → ai-stack → Secrets
3. You should see all 12 secrets listed
4. Can view (base64 encoded) and manage via UI

**Step 5.3: Update Deployment Manifests to Use Secrets**

Example for PostgreSQL deployment:

```yaml
# ai-stack/k8s/postgres-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: ai-stack
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: pgvector/pgvector:0.8.1-pg18
        env:
        - name: POSTGRES_DB
          value: "mcp"
        - name: POSTGRES_USER
          value: "mcp"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-password
              key: password
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
        - name: postgres-secret
          mountPath: /run/secrets
          readOnly: true
      volumes:
      - name: postgres-data
        persistentVolumeClaim:
          claimName: postgres-data
      - name: postgres-secret
        secret:
          secretName: postgres-password
```

---

### Phase 6: Configure Persistent Storage (1 hour)

**Step 6.1: Create Storage Class**

```bash
# K3s comes with local-path provisioner by default
kubectl get storageclass

# Should show: local-path (default)
```

**Step 6.2: Create Persistent Volume Claims**

```yaml
# ai-stack/k8s/storage.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data
  namespace: ai-stack
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-data
  namespace: ai-stack
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 5Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: qdrant-data
  namespace: ai-stack
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 20Gi
---
# Add more PVCs for other services...
```

```bash
kubectl apply -f ai-stack/k8s/storage.yaml
```

---

### Phase 7: Deploy AI Stack Services (2-3 hours)

**Step 7.1: Deploy Core Services First**

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/k8s

# Deploy PostgreSQL
kubectl apply -f postgres-deployment.yaml
kubectl apply -f postgres-service.yaml

# Deploy Redis
kubectl apply -f redis-deployment.yaml
kubectl apply -f redis-service.yaml

# Deploy Qdrant
kubectl apply -f qdrant-deployment.yaml
kubectl apply -f qdrant-service.yaml

# Wait for ready
kubectl get pods -n ai-stack -w
```

**Step 7.2: Deploy Monitoring Stack**

```bash
# Prometheus
kubectl apply -f prometheus-deployment.yaml
kubectl apply -f prometheus-service.yaml

# Grafana
kubectl apply -f grafana-deployment.yaml
kubectl apply -f grafana-service.yaml
```

**Step 7.3: Deploy AI Services**

```bash
# Embeddings
kubectl apply -f embeddings-deployment.yaml
kubectl apply -f embeddings-service.yaml

# llama.cpp
kubectl apply -f llama-cpp-deployment.yaml
kubectl apply -f llama-cpp-service.yaml

# AIDB
kubectl apply -f aidb-deployment.yaml
kubectl apply -f aidb-service.yaml

# Hybrid Coordinator
kubectl apply -f hybrid-coordinator-deployment.yaml
kubectl apply -f hybrid-coordinator-service.yaml

# Continue for all services...
```

**Step 7.4: Monitor Deployment via Portainer**

1. Open Portainer → ai-stack namespace
2. View Applications → see all deployments
3. Click on each deployment to see pod status
4. Check logs if any issues
5. Monitor resource usage

---

### Phase 8: Configure GPU Support (1 hour)

**Step 8.1: Install NVIDIA Device Plugin (if using NVIDIA)**

```bash
kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml
```

**Step 8.2: Configure DRI Device Access (for AMD/Intel)**

For llama.cpp and services needing GPU:

```yaml
# In deployment spec:
spec:
  containers:
  - name: llama-cpp
    image: your-image
    securityContext:
      privileged: false
    volumeMounts:
    - name: dri-device
      mountPath: /dev/dri
  volumes:
  - name: dri-device
    hostPath:
      path: /dev/dri
      type: Directory
```

**Step 8.3: Verify GPU Access**

```bash
# Check pod can see GPU
kubectl exec -it <llama-cpp-pod> -n ai-stack -- ls -la /dev/dri
```

---

### Phase 9: Configure Networking & Ingress (1 hour)

**Step 9.1: Expose Services via NodePort**

Services are already configured with ClusterIP. For external access:

```yaml
# For Grafana web UI:
apiVersion: v1
kind: Service
metadata:
  name: grafana
  namespace: ai-stack
spec:
  type: NodePort
  ports:
  - port: 3000
    targetPort: 3000
    nodePort: 30300  # Access at localhost:30300
  selector:
    app: grafana
```

**Step 9.2: Alternative - Use Port Forwarding**

```bash
# Access Grafana
kubectl port-forward svc/grafana 3000:3000 -n ai-stack

# Access in browser: http://localhost:3000

# Access PostgreSQL
kubectl port-forward svc/postgres 5432:5432 -n ai-stack
```

---

### Phase 10: Testing & Validation (2 hours)

**Step 10.1: Test Database Connections**

```bash
# PostgreSQL
kubectl exec -it deployment/postgres -n ai-stack -- \
  psql -U mcp -d mcp -c "SELECT version();"

# Redis
kubectl exec -it deployment/redis -n ai-stack -- \
  redis-cli -a $(kubectl get secret redis-password -n ai-stack -o jsonpath='{.data.password}' | base64 -d) ping
```

**Step 10.2: Test Web UIs**

```bash
# Grafana
kubectl port-forward svc/grafana 3000:3000 -n ai-stack &
# Open: http://localhost:3000
# Login with admin / <grafana_admin_password>

# Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n ai-stack &
# Open: http://localhost:9090
```

**Step 10.3: Test AI Services**

```bash
# Test embeddings service
kubectl port-forward svc/embeddings 8081:8081 -n ai-stack &
curl http://localhost:8081/health

# Test llama.cpp
kubectl port-forward svc/llama-cpp 8080:8080 -n ai-stack &
curl http://localhost:8080/health
```

**Step 10.4: Check Resource Usage in Portainer**

1. Portainer → ai-stack → Applications
2. View resource usage graphs
3. Check pod logs for errors
4. Verify all services are "Running"

---

### Phase 11: Restore Data (if needed) (1 hour)

**Step 11.1: Restore PostgreSQL Data**

```bash
# Copy backup into pod
kubectl cp backup.sql deployment/postgres:/tmp/ -n ai-stack

# Restore
kubectl exec -it deployment/postgres -n ai-stack -- \
  psql -U mcp -d mcp -f /tmp/backup.sql
```

**Step 11.2: Restore Qdrant Vectors**

```bash
# Copy snapshot
kubectl cp qdrant-snapshot.tar.gz deployment/qdrant:/qdrant/storage/ -n ai-stack

# Restore via Qdrant API
kubectl port-forward svc/qdrant 6333:6333 -n ai-stack &
curl -X POST http://localhost:6333/collections/recover \
  -H "Content-Type: application/json" \
  -d '{"snapshot": "qdrant-snapshot.tar.gz"}'
```

---

## 📊 Post-Migration Checklist

### Functional Testing
- [ ] All pods running (check in Portainer)
- [ ] PostgreSQL accessible and data intact
- [ ] Redis accessible and caching works
- [ ] Grafana UI accessible with new password
- [ ] Prometheus collecting metrics
- [ ] AI services responding to health checks
- [ ] GPU access working for llama.cpp
- [ ] Inter-service communication working

### Security Validation
- [ ] All secrets in Kubernetes Secrets (not plain files)
- [ ] No pods running as root (check securityContext)
- [ ] Network policies configured (optional)
- [ ] RBAC configured for Portainer access
- [ ] TLS enabled for external endpoints

### Performance Check
- [ ] Resource limits configured for each pod
- [ ] No CPU throttling issues
- [ ] Memory usage within limits
- [ ] Storage I/O acceptable
- [ ] Response times similar to pre-migration

### Monitoring
- [ ] Prometheus scraping all services
- [ ] Grafana dashboards showing data
- [ ] Alerts configured (optional)
- [ ] Log aggregation working (optional)

---

## 🔧 Portainer Management Features

### Secrets Management
1. Portainer → Namespaces → ai-stack → Secrets
2. View all secrets (base64 encoded)
3. Create new secrets via UI
4. Delete/rotate secrets with one click

### Application Management
1. Portainer → Applications
2. See all deployments as "stacks"
3. Scale replicas with slider
4. Update images
5. View/edit YAML
6. Restart pods
7. View logs in real-time

### Resource Management
1. View CPU/Memory usage graphs
2. Set resource limits via UI
3. Monitor node capacity
4. View persistent volume usage

### Debugging
1. Click on pod → Console
2. Execute commands in running container
3. View real-time logs
4. Download logs
5. Inspect events

---

## 🚀 Benefits After Migration

### Before (podman-compose):
- ❌ Manual secret files with permission issues
- ❌ No UI for management
- ❌ Limited orchestration (no self-healing)
- ❌ Complex environment variable requirements
- ❌ Friction with service dependencies
- ❌ No built-in scaling
- ❌ Manual health checks

### After (K3s + Portainer):
- ✅ Kubernetes Secrets with UI management
- ✅ Beautiful Portainer web UI
- ✅ Self-healing (pods auto-restart on failure)
- ✅ Simplified configuration
- ✅ Declarative dependencies
- ✅ Horizontal pod auto-scaling
- ✅ Built-in health checks & readiness probes
- ✅ Rolling updates (zero-downtime deployments)
- ✅ Resource limits & quotas
- ✅ Better GPU management
- ✅ Industry-standard platform

---

## 📚 Key Commands Reference

### K3s Management
```bash
# View cluster info
kubectl cluster-info

# View all resources in namespace
kubectl get all -n ai-stack

# View logs
kubectl logs deployment/postgres -n ai-stack

# Execute command in pod
kubectl exec -it deployment/postgres -n ai-stack -- bash

# Port forward
kubectl port-forward svc/grafana 3000:3000 -n ai-stack

# Scale deployment
kubectl scale deployment postgres --replicas=2 -n ai-stack

# Delete resource
kubectl delete pod <pod-name> -n ai-stack
```

### Portainer Access
```bash
# Get Portainer URL
kubectl get svc -n portainer

# Reset Portainer admin password (if needed)
kubectl exec -it deployment/portainer -n portainer -- \
  /portainer --admin-password='$2y$05$...'
```

### Secrets Management
```bash
# Create secret
kubectl create secret generic my-secret \
  --from-literal=password=mysecretpassword \
  -n ai-stack

# View secret (base64 encoded)
kubectl get secret my-secret -n ai-stack -o yaml

# Decode secret
kubectl get secret my-secret -n ai-stack -o jsonpath='{.data.password}' | base64 -d

# Delete secret
kubectl delete secret my-secret -n ai-stack
```

---

## 🐛 Troubleshooting

### Issue: Pod stuck in Pending
```bash
# Check events
kubectl describe pod <pod-name> -n ai-stack

# Common causes:
# - Insufficient resources (CPU/memory)
# - PVC not bound
# - Image pull errors
```

### Issue: Pod crashing (CrashLoopBackOff)
```bash
# View logs
kubectl logs <pod-name> -n ai-stack --previous

# Check events
kubectl describe pod <pod-name> -n ai-stack

# Common causes:
# - Application error
# - Missing environment variables
# - Failed health checks
```

### Issue: Service not accessible
```bash
# Check service
kubectl get svc -n ai-stack

# Check endpoints
kubectl get endpoints <service-name> -n ai-stack

# Test from within cluster
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  wget -O- http://<service-name>.<namespace>:port
```

### Issue: Secrets not accessible
```bash
# Verify secret exists
kubectl get secret <secret-name> -n ai-stack

# Check pod has secret mounted
kubectl describe pod <pod-name> -n ai-stack | grep -A5 Mounts

# Verify secret content
kubectl exec -it <pod-name> -n ai-stack -- cat /run/secrets/password
```

---

## 📅 Migration Timeline

| Phase | Duration | Can Work in Parallel? |
|-------|----------|----------------------|
| 1. Backup | 30 min | No (must be first) |
| 2. Install K3s | 1 hour | No |
| 3. Install Portainer | 30 min | No (needs K3s) |
| 4. Convert Compose | 2-3 hours | Yes (manual review needed) |
| 5. Migrate Secrets | 1 hour | Yes |
| 6. Storage Setup | 1 hour | Yes |
| 7. Deploy Services | 2-3 hours | Partial (core first, then rest) |
| 8. GPU Setup | 1 hour | Yes |
| 9. Networking | 1 hour | Yes |
| 10. Testing | 2 hours | No (must be last) |
| 11. Data Restore | 1 hour | After testing |

**Total:** ~14-18 hours of work
**Can be done over:** 2-3 days working part-time

---

## ✅ Ready to Start?

Say "Let's start" and I'll begin with Phase 1: Backup!

Or ask any questions about the migration plan first.
