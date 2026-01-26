# Troubleshooting (K3s-only)

## Check Pods

```bash
kubectl get pods -n ai-stack
kubectl describe pod -n ai-stack <pod>
```

## Logs

```bash
kubectl logs -n ai-stack deployment/<service> --tail=100
```

## Restart

```bash
kubectl rollout restart -n ai-stack deployment/<service>
```

