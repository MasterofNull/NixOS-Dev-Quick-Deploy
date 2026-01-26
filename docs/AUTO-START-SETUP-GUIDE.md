# Auto-Start Setup (K3s-only)

The AI stack auto-starts via the K3s systemd service. Compose-based user units are retired.

Key commands:

```bash
sudo systemctl status k3s
kubectl get pods -n ai-stack
kubectl rollout restart -n ai-stack deployment/aidb
```

For full deployment steps, see `DEPLOYMENT.md`.

