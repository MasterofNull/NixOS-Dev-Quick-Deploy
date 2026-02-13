# AIDB Quick Start (K3s)

This guide covers the K3s-based AI stack deployed by NixOS-Dev-Quick-Deploy.

## Deploy

```bash
./nixos-quick-deploy.sh --with-ai-stack
# or re-run just the K3s phase:
./nixos-quick-deploy.sh --run-phase 9
```

## Health Checks

```bash
./scripts/system-health-check.sh --detailed
./scripts/test_services.sh
kubectl get pods -n ai-stack
```

## Logs

```bash
kubectl logs -n ai-stack deployment/aidb --tail=100
kubectl logs -n ai-stack deployment/hybrid-coordinator --tail=100
```

## Access Points (Port-Forward)

```bash
# AIDB (FastAPI MCP server)
kubectl port-forward -n ai-stack svc/aidb 8091:8091
# Embeddings
kubectl port-forward -n ai-stack svc/embeddings 8081:8081
# Grafana
kubectl port-forward -n ai-stack svc/grafana 3001:3001
```

## Database Access (Postgres)

```bash
kubectl exec -n ai-stack deploy/postgres -- bash -c \
  'export PGPASSWORD=$(cat /run/secrets/postgres-password) && psql -U mcp -d mcp'
```

## Restart a Service

```bash
kubectl rollout restart -n ai-stack deployment/aidb
kubectl rollout restart -n ai-stack deployment/postgres
```

## Troubleshooting

See `docs/06-TROUBLESHOOTING.md` for CrashLoopBackOff, ImagePullBackOff, and
SOPS/TLS remediation steps.
