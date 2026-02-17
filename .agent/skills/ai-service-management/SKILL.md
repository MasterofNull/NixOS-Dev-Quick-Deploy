# Skill Name: ai-service-management

## Description
Operate the AI stack in a **K3s-first** way using Kubernetes resources in the `ai-stack` namespace.

## K3s-First Policy
- Use `kubectl` + K3s system services as the primary control plane.
- Do **not** use legacy `podman-local-ai-*` workflows for normal operations.
- Treat podman-based flows as legacy/debug-only unless explicitly requested.

## When to Use
- Check AI stack readiness in K3s
- Roll out config/image changes safely
- Restart or scale AI services
- Troubleshoot failing pods, probes, and image pulls
- Verify service endpoints after deployment

## Prerequisites
- K3s installed and running (`systemctl is-active k3s`)
- `kubectl` available and pointed at K3s (`/etc/rancher/k3s/k3s.yaml`)
- AI manifests available under `ai-stack/kubernetes/` or `ai-stack/kustomize/`

## Core Workflow

### 1) Validate Cluster + Namespace
```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get nodes -o wide
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get ns ai-stack
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -n ai-stack -o wide
```

### 2) Deploy / Reconcile AI Stack
```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl apply -k ai-stack/kubernetes
```

### 3) Observe Health
```bash
./scripts/ai-stack-health.sh
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get deploy -n ai-stack
```

### 4) Troubleshoot
```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl describe pod -n ai-stack <pod>
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl logs -n ai-stack deploy/aidb --tail=200
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get events -n ai-stack --sort-by=.metadata.creationTimestamp
```

### 5) Restart / Rollout
```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl rollout restart -n ai-stack deployment/aidb
KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl rollout status -n ai-stack deployment/aidb --timeout=180s
```

## Service Endpoints (Typical)
- AIDB: `http://localhost:8091` (via service/port-forward)
- Qdrant: `http://localhost:6333` (cluster service)
- Llama.cpp/vLLM endpoints: per active deployment/service

## Common Recovery Actions
- Re-apply manifests: `kubectl apply -k ai-stack/kubernetes`
- Check image pull failures: `kubectl describe pod ...` + events
- Restart only failed deployment(s): `kubectl rollout restart ...`
- Validate quotas/policies when pods are Pending

## Related Skills
- `nixos-deployment`
- `health-monitoring`
- `ai-model-management`
- `aidb-knowledge`

## Notes
- If local workstation services are needed outside K3s, document that as a separate explicit workflow.
- Keep this skill aligned with `docs/UNIFIED-AI-STACK.md` and K3s manifests.
