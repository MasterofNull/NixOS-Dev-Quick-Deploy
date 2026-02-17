# AI Stack Troubleshooting Guide

This guide is for diagnosing runtime issues in the K3s AI stack deployment.

## 1. AI Stack Service Failures

### Symptoms

- API timeouts on AIDB/Hybrid/Embeddings.
- Pods in `CrashLoopBackOff` or `ImagePullBackOff`.
- Health checks fail in `scripts/system-health-check.sh`.

### Checks

```bash
kubectl get pods -n ai-stack -o wide
kubectl get deploy -n ai-stack
kubectl logs -n ai-stack deploy/aidb --tail=100
kubectl logs -n ai-stack deploy/hybrid-coordinator --tail=100
```

## 2. Kubernetes Deployment Issues

### Symptoms

- Deploy script reports healthy cluster but workloads not ready.
- Service endpoints unavailable after rollout.

### Checks

```bash
kubectl get nodes -o wide
kubectl get svc -n ai-stack
kubectl get events -n ai-stack --sort-by=.lastTimestamp
kubectl describe deploy -n ai-stack aidb
```

## 3. Performance Troubleshooting

### Symptoms

- Slow query responses.
- CPU/memory pressure under load.
- Intermittent timeouts on `/query`.

### Checks

```bash
kubectl top nodes
kubectl top pods -n ai-stack
curl -sf http://localhost:8091/health/detailed
curl -sf http://localhost:8092/health
```

### Immediate Actions

- Reduce concurrent request volume.
- Verify embeddings backend readiness.
- Confirm Postgres/Qdrant service latency.

## 4. Security Troubleshooting

### Symptoms

- Authentication failures.
- TLS handshake failures.
- Unexpected external exposure.

### Checks

```bash
kubectl get secrets -n ai-stack
kubectl get ingress -A
kubectl get networkpolicy -n ai-stack
```

### Immediate Actions

- Validate API key configuration (`X-API-Key` paths).
- Rotate affected credentials.
- Re-apply security manifests before re-testing.

## 5. Automation Script

Collect a one-shot troubleshooting report:

```bash
./scripts/ai-stack-troubleshoot.sh
```

Output:

- `artifacts/troubleshooting/ai-stack-troubleshoot-<timestamp>.txt`

Use this report for incident triage and roadmap follow-up.
