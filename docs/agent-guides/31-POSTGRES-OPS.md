# Postgres Ops (K3s-only)

```bash
kubectl exec -n ai-stack deployment/postgres -- pg_isready -U mcp
kubectl exec -n ai-stack deployment/postgres -- psql -U mcp -d mcp -c '\\dt'
```

Backup:

```bash
kubectl exec -n ai-stack deployment/postgres -- pg_dump -U mcp mcp | gzip > backup-$(date +%Y%m%d).sql.gz
```

