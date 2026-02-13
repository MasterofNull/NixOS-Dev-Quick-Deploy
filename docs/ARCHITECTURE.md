# Architecture (K3s-only)

- Runtime: K3s + containerd
- Manifests: `ai-stack/kubernetes/` (kustomize + kompose)
- Secrets: `ai-stack/kubernetes/secrets/` (source-of-truth)
- Monitoring: Prometheus + Grafana + Portainer
