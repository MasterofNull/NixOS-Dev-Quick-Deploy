# Service Conflict Resolution (K3s-only)

Port conflicts are handled at the Kubernetes Service/Ingress layer. If a service is not reachable:

```bash
kubectl get svc -n ai-stack
kubectl describe svc -n ai-stack <service>
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/<service> --tail=100
```

Use port-forward for local testing:

```bash
kubectl port-forward -n ai-stack svc/<service> <local-port>:<service-port>
```

