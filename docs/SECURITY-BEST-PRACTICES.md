# Security Best Practices

This guide defines operational security practices for deployment and AI stack runtime.

## 1. Secrets Management

- Keep secrets encrypted at rest (`sops` + age workflow where configured).
- Do not commit plaintext credentials, keys, or kube secrets.
- Rotate credentials after any suspected leak or history exposure.

## 2. Network Security Configuration

- Prefer in-cluster service communication over host-network shortcuts.
- Restrict ingress to required services only.
- Enforce default-deny + explicit allow rules via `NetworkPolicy`.

## 3. Access Control

- Use least privilege for service accounts.
- Avoid privileged containers unless justified and documented.
- Limit kubeconfig and cluster-admin usage to operational workflows.

## 4. Security Monitoring

- Monitor health and events continuously:
  - `kubectl get events -n ai-stack --sort-by=.lastTimestamp`
  - `./scripts/ai-stack-troubleshoot.sh`
- Track auth failures, repeated restarts, and unusual egress behavior.

## 5. Incident Response

1. Identify scope and affected services.
2. Capture diagnostics (`scripts/ai-stack-troubleshoot.sh`).
3. Isolate impacted workload (scale down / cordon / policy lock).
4. Rotate credentials and re-apply secure manifests.
5. Validate recovery with health and deployment checks.
6. Record follow-up tasks in roadmap and post-incident notes.
