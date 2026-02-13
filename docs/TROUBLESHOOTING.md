# Troubleshooting (K3s-only)

This guide focuses on the K3s-based AI stack and the deployment scripts in this repo.

## Quick Health Snapshot

```bash
kubectl get nodes -o wide
kubectl get pods -n ai-stack
./scripts/system-health-check.sh --detailed
```

## CrashLoopBackOff

**Symptoms:** Pod restarts continuously, `STATUS=CrashLoopBackOff`.

```bash
kubectl get pods -n ai-stack
kubectl describe pod -n ai-stack <pod>
kubectl logs -n ai-stack <pod> --previous --tail=120
```

Common causes:
- Liveness probe hitting a 404/invalid path.
- Missing env/secret entries.
- OOMKills (check `Last State` in `kubectl describe`).

**Fix:** Update the probe to a valid endpoint or switch to `tcpSocket`.

## ImagePullBackOff / ErrImagePull

**Symptoms:** Pods stuck in `ImagePullBackOff`.

```bash
kubectl describe pod -n ai-stack <pod>
curl -s http://localhost:5000/v2/_catalog | jq .
sudo ss -tulnp | grep 5000
```

**Fix:**
- Ensure `/etc/rancher/k3s/registries.yaml` trusts `localhost:5000` (HTTP).
- Re-run the registry helper:
  ```bash
  sudo ./scripts/configure-k3s-registry.sh
  ```
- Restart k3s:
  ```bash
  sudo systemctl restart k3s
  ```

## Secrets / SOPS Errors

**Symptoms:** Services fail due to missing passwords or API keys.

```bash
ls -la ai-stack/kubernetes/secrets/secrets.sops.yaml
sops -d ai-stack/kubernetes/secrets/secrets.sops.yaml >/dev/null
./nixos-quick-deploy.sh --run-phase 9
```

## TLS / Cert-Manager Issues

```bash
kubectl get certificate -A
kubectl describe certificate -n ai-stack <cert>
kubectl get pods -n cert-manager
./scripts/check-tls-log-warnings.sh
```

If certs are not ready, check ClusterIssuer and cert-manager logs.

## NetworkPolicy / CNI Enforcement

**Symptoms:** Pods cannot reach internal services after policy changes.

```bash
kubectl get networkpolicy -n ai-stack
kubectl exec -n ai-stack deploy/grafana -- curl -s http://prometheus:9090/-/healthy
```

If policies are not enforced, ensure NetworkPolicy enforcement is enabled or install
a policy-capable CNI (Calico or Cilium).

Quick enforcement test (should return BLOCKED):
```bash
kubectl run netpol-test --rm -i --restart=Never --image=busybox:1.36 --command -- \
  sh -c "wget -qO- --timeout=5 --tries=1 http://postgres.ai-stack:5432 >/dev/null 2>&1 && echo ALLOWED || echo BLOCKED"
```

## PersistentVolumeClaims Pending

```bash
kubectl get pvc -n ai-stack
kubectl describe pvc -n ai-stack <pvc>
```

If PVCs are pending, verify the default storage class and available disk space.

## Logs and Restarts

```bash
kubectl logs -n ai-stack deployment/<service> --tail=200
kubectl get pods -n ai-stack -o wide
```

## Restart a Service

```bash
kubectl rollout restart -n ai-stack deployment/<service>
```
