# Network Policy Baseline (K3s)

These policies are safe defaults **only when NetworkPolicy enforcement is active**.
K3s can enforce policies via its embedded controller, but you must verify enforcement before applying default-deny.

## Files
- `default-deny-all.yaml`: blocks all ingress/egress by default (requires an enforcing CNI).
- `ai-stack-allow-internal.yaml`: allows ingress/egress only within the `ai-stack` namespace.
- `ai-stack-allow-external-egress.yaml`: opt-in egress to ports 80/443 for pods labeled `egress-allow=external`.

## Recommended sequence
1. Verify enforcement (example test below).
2. If enforcement is inactive, install a NetworkPolicy-capable CNI (Calico/Cilium).
3. Apply baseline policies:
   ```bash
   kubectl apply -f ai-stack/kubernetes/network-policies/default-deny-all.yaml
   kubectl apply -f ai-stack/kubernetes/network-policies/ai-stack-allow-internal.yaml
   ```
4. Opt-in egress for specific workloads that must call the public internet:
   ```bash
   kubectl label deployment/embeddings -n ai-stack egress-allow=external --overwrite
   ```
5. Add explicit ingress exceptions for NodePort/ingress controllers as needed.

## Enforcement Test (cross-namespace block)

```bash
kubectl run netpol-test --rm -i --restart=Never --image=busybox:1.36 --command -- \
  sh -c "wget -qO- --timeout=5 --tries=1 http://postgres.ai-stack:5432 >/dev/null 2>&1 && echo ALLOWED || echo BLOCKED"
```

## Notes
- Do **not** apply a default-deny policy until enforcement is verified.
- Review NodePort access paths before locking down ingress.
- The `ai-stack-allow-external-egress.yaml` policy only affects pods labeled `egress-allow=external`.

## External Egress Allowlist (Inventory)

NetworkPolicy does **not** support FQDNs by default. If you need strict egress,
convert domains to CIDRs or use a CNI that supports FQDN policies (e.g., Cilium).

Suggested domains to allow (as needed for your deployment):
- `channels.nixos.org` (nix channels)
- `cache.nixos.org` (nix binary cache)
- `github.com`, `api.github.com`, `raw.githubusercontent.com` (flake inputs, releases)
- `dl.flathub.org`, `flathub.org` (Flatpak)
- `huggingface.co`, `hf.co`, `cdn-lfs.huggingface.co` (model downloads)
- `api.openai.com` (remote LLM, if enabled)
- `api.anthropic.com` (remote LLM, if enabled)
- `openrouter.ai` (remote LLM router, if enabled)

When using Cilium, consider `CiliumNetworkPolicy` with `toFQDNs` rules to avoid
hardcoding IPs. For non‑FQDN CNIs, maintain a CIDR allowlist and update it on
endpoint changes.

### Cilium FQDN Policy (optional)

If Cilium is installed, apply the FQDN allowlist:

```bash
kubectl apply -f ai-stack/kubernetes/network-policies/ai-stack-allow-external-fqdn.yaml
```

This policy is **not** included in kustomize by default to avoid breaking
clusters without Cilium.
