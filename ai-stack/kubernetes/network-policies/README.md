# Network Policy Baseline (K3s)

These policies are safe defaults **only when a NetworkPolicy-capable CNI is installed** (Calico/Cilium/etc.).
K3s default (flannel) does not enforce policies, so applying them is currently a no-op.

## Files
- `ai-stack-allow-internal.yaml`: allows ingress/egress only within the `ai-stack` namespace.

## Recommended sequence
1. Install a NetworkPolicy-capable CNI (Calico/Cilium).
2. Apply baseline policies:
   ```bash
   kubectl apply -f ai-stack/kubernetes/network-policies/ai-stack-allow-internal.yaml
   ```
3. Add explicit ingress exceptions for NodePort/ingress controllers as needed.

## Notes
- Do **not** apply a default-deny policy until CNI enforcement is verified.
- Review NodePort access paths before locking down ingress.
