# AI Stack Vulkan Debug Loop
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-07

Purpose: reduce token burn and rebuild churn when `llama.cpp`, Vulkan, AppArmor, or service wiring regress.

## Primary Commands

Use these in order:

```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
aq-qa 2
aq-llama-debug
aq-llama-debug --json
```

`aq-qa 2` is the fast gate.

`aq-llama-debug` is the deep loop for `llama.cpp` runtime classification.

## What `aq-llama-debug` Checks

- current `llama-cpp.service` state
- active `ExecStart` path and running binary path
- whether the running binary links `libggml-vulkan`
- whether the configured RADV ICD file exists
- direct `--list-devices` on the active binary
- `--list-devices` on a copied alias binary
- focused `journalctl` extraction for CPU fallback vs Vulkan activation
- optional bounded smoke inference timing

## Classification Meanings

`vulkan_active`
- Live service is using Vulkan.
- Stop debugging and move to cleanup or benchmarking.

`path_scoped_confinement_likely`
- Copied binary enumerates Vulkan but original binary does not.
- Prioritize AppArmor or other path-scoped confinement before changing `llama.cpp`.

`package_not_vulkan`
- Active binary does not link `libggml-vulkan`.
- Fix the build or overlay before runtime debugging.

`runtime_cpu_fallback`
- Service is up, but logs still show CPU fallback.
- Inspect `--list-devices`, service env, and confinement.

`service_inactive`
- Fix unit startup first.

## Lessons Captured From The 2026-03-07 Incident

1. Do not assume a CPU fallback is a `llama.cpp` source bug first.
2. Compare the original binary path with a copied alias path early.
3. If the copied alias works, treat the problem as path-scoped confinement until disproven.
4. Distinguish three layers before rebuilding:
   - host Vulkan stack
   - package linkage
   - service/runtime confinement
5. Prefer package-local probes and service-local probes before full `nixos-rebuild switch`.

## Recommended Debug Order

1. `aq-qa 2`
2. `aq-llama-debug --json`
3. If classified as confinement:
   - inspect [ai-stack.nix](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/nix/modules/roles/ai-stack.nix)
   - inspect `/etc/apparmor.d/ai-llama-cpp`
   - compare original vs copied binary behavior
4. If classified as package/runtime:
   - inspect [llama-cpp-latest.nix](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/nix/lib/overlays/llama-cpp-latest.nix)
   - inspect [allow-vulkan-igpu-offload.patch](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/nix/patches/llama-cpp/allow-vulkan-igpu-offload.patch)
5. Only then start rebuild loops.

## Rebuild Gate

Do a full system activation only after:

- `aq-llama-debug` yields a concrete classification
- the planned fix is clearly in one layer:
  - Nix wiring
  - AppArmor/runtime confinement
  - `llama.cpp` package/runtime code

## Validation After Any Fix

```bash
aq-qa 2
systemctl status llama-cpp.service --no-pager
journalctl -u llama-cpp.service -n 80 --no-pager
```

For a live check:

```bash
aq-llama-debug --smoke
```
