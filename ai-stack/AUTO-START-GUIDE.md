# AI Stack Auto-Start Configuration Guide

**Date:** February 2, 2026
**Version:** 2.0.0 (K3s)

---

## Overview

This guide explains how to configure the NixOS AI Stack (running on K3s) to automatically start:
1. After NixOS Quick Deploy completes
2. After system reboots
3. After system shutdowns and restarts

Since the AI Stack runs on K3s, workloads are managed as Kubernetes deployments with built-in restart policies. K3s itself is a systemd service that starts on boot.

---

## What's Already Configured

### 1. K3s Systemd Service

K3s is installed as a systemd service (`k3s.service`) that starts automatically on boot:

```bash
# Check K3s status
systemctl status k3s.service

# View K3s logs
journalctl -u k3s.service -f
```

### 2. Kubernetes Restart Policies

All AI stack deployments use `restartPolicy: Always` (the Kubernetes default for Deployments). Combined with K3s auto-start, this means:

- Pods automatically restart if they crash
- Pods are recreated after node reboot (K3s reconciles desired state)
- No manual intervention needed after reboot
- CrashLoopBackOff provides automatic backoff for persistently failing pods

### 3. Resource Governance

The `ai-stack` namespace has:
- **LimitRange**: Per-container CPU/memory defaults and maximums
- **ResourceQuota**: Namespace-wide resource caps
- **NetworkPolicies**: Default-deny with explicit allow rules

---

## Auto-Start Flow

```
System Boot
  -> systemd starts k3s.service
    -> K3s API server comes online
      -> K3s reconciles all Deployments/StatefulSets
        -> AI stack pods are scheduled and started
          -> Liveness/readiness probes verify health
```

No additional configuration is needed. K3s handles everything.

---

## Verification

### Check K3s Service

```bash
systemctl status k3s.service
```

### Check AI Stack Pods

```bash
kubectl get pods -n ai-stack
```

**Expected output:**
```
NAME                                  READY   STATUS    RESTARTS   AGE
llama-cpp-xxx                         1/1     Running   0          2h
qdrant-xxx                            1/1     Running   0          2h
redis-xxx                             1/1     Running   0          2h
postgres-xxx                          1/1     Running   0          2h
aidb-xxx                              1/1     Running   0          2h
hybrid-coordinator-xxx                1/1     Running   0          2h
nixos-docs-xxx                        1/1     Running   0          2h
ralph-wiggum-xxx                      1/1     Running   0          2h
grafana-xxx                           1/1     Running   0          2h
prometheus-xxx                        1/1     Running   0          2h
```

### Run Health Check

```bash
./scripts/ai-stack-health.sh
```

### Check Specific Service Logs

```bash
kubectl logs -n ai-stack deploy/aidb -f
kubectl logs -n ai-stack deploy/llama-cpp -f
```

---

## Troubleshooting

### Pods Not Starting After Reboot

**Symptom:** `kubectl get pods -n ai-stack` shows no pods or pods in Pending state.

**Solutions:**
1. Check K3s is running: `systemctl status k3s.service`
2. Check for resource pressure: `kubectl describe nodes`
3. Check events: `kubectl get events -n ai-stack --sort-by=.metadata.creationTimestamp`
4. If K3s failed to start: `journalctl -u k3s.service -b`

### Pods in CrashLoopBackOff

**Symptom:** Pods repeatedly restart with increasing backoff delays.

**Solutions:**
```bash
# Check pod logs for the crash reason
kubectl logs -n ai-stack deploy/<service-name> --previous

# Describe the pod for events
kubectl describe pod -n ai-stack -l app=<service-name>

# Check if it's a resource issue
kubectl top pods -n ai-stack
```

### ImagePullBackOff

**Symptom:** Pods stuck in `ImagePullBackOff` state.

**Solutions:**
```bash
# Check the local registry is running
curl -s http://localhost:5000/v2/_catalog | jq .

# Verify K3s registry config
cat /etc/rancher/k3s/registries.yaml

# Restart K3s if registry config was updated
sudo systemctl restart k3s.service
```

### Services Not Reachable

**Symptom:** Services respond on the cluster but not from localhost.

**Solutions:**
```bash
# Use kubectl port-forward for local access
kubectl port-forward -n ai-stack svc/aidb 8091:8091 &
kubectl port-forward -n ai-stack svc/llama-cpp 8080:8080 &

# Or check NodePort/Ingress configuration
kubectl get svc -n ai-stack
```

---

## Optional: Scaling Services

### Scale Down (save resources)

```bash
kubectl scale deploy -n ai-stack llama-cpp --replicas=0
```

### Scale Up

```bash
kubectl scale deploy -n ai-stack llama-cpp --replicas=1
```

### Enable Optional Agents (e.g., Aider)

```bash
kubectl apply -k ai-stack/kustomize/overlays/dev-agents
```

---

## Configuration Files Summary

| File | Purpose |
|------|---------|
| K3s service (`k3s.service`) | Auto-starts K3s on boot |
| `ai-stack/kubernetes/` | Kustomize manifests for all services |
| `ai-stack/kubernetes/kustomization.yaml` | Main kustomize entry point |
| `ai-stack/kubernetes/security/` | LimitRange, ResourceQuota |
| `ai-stack/kubernetes/network-policies/` | Default-deny + allow rules |
| `/etc/rancher/k3s/registries.yaml` | Local registry configuration |

---

## Quick Commands

```bash
# Check everything
kubectl get all -n ai-stack

# Restart a specific service
kubectl rollout restart deploy/<service-name> -n ai-stack

# View resource usage
kubectl top pods -n ai-stack

# Check cluster health
kubectl cluster-info
kubectl get nodes

# Run health check
./scripts/ai-stack-health.sh

# Run feature scenario test
./scripts/ai-stack-feature-scenario.sh
```

---

**Status:** Production Ready (K3s)
**Last Updated:** February 2, 2026
**Maintainer:** NixOS Quick Deploy Team
