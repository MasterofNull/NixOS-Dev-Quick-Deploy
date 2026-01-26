# AI Stack E2E Testing (K3s-only)

```bash
python3 ai-stack/tests/test_hospital_e2e.py
```

If a service is down:

```bash
kubectl get pods -n ai-stack
kubectl logs -n ai-stack deployment/<service> --tail=100
kubectl rollout restart -n ai-stack deployment/<service>
```

