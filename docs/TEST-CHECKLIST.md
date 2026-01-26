# Test Checklist (K3s-only)

- [ ] Run quick-deploy: `./nixos-quick-deploy.sh`
- [ ] K3s running: `sudo systemctl status k3s --no-pager`
- [ ] Pods healthy: `kubectl get pods -n ai-stack`
- [ ] AIDB health: `kubectl port-forward -n ai-stack svc/aidb 8091:8091` then `curl http://localhost:8091/health`
- [ ] Hybrid health: `kubectl port-forward -n ai-stack svc/hybrid-coordinator 8092:8092` then `curl http://localhost:8092/health`
- [ ] E2E test: `python3 ai-stack/tests/test_hospital_e2e.py`

