# Known Issues and Troubleshooting

## 2026-02-26 — Phase 10.1 nixos-unstable track

### Context
- Added optional `nixpkgs-unstable` flake input.
- Added host option `mySystem.nixpkgsTrack = "stable" | "unstable"` (default `stable`).

### Unstable VM build validation
- Build command (host override via module extension):
  - `nix build --impure --expr 'let flake = builtins.getFlake (toString /home/hyperd/Documents/NixOS-Dev-Quick-Deploy); cfg = flake.nixosConfigurations."nixos-ai-dev".extendModules { modules = [ { mySystem.nixpkgsTrack = "unstable"; } ]; }; in cfg.config.system.build.vm' --no-link --print-out-paths`
- Result:
  - Built successfully: `/nix/store/5prm2q9i7p1z32abxjxcab6rjvkha581-nixos-vm`
- Boot smoke test:
  - `QEMU_OPTS='-nographic' /nix/store/5prm2q9i7p1z32abxjxcab6rjvkha581-nixos-vm/bin/run-nixos-vm`
  - Reached serial login prompt:
    - `<<< Welcome to NixOS ... >>>`
    - `nixos login:`

### Observed warnings during boot
- Repeated kernel log line:
  - `audit: error in audit_log_subj_ctx`
- This did not block boot to login, but should be investigated before calling the unstable track production-ready.

### Package version comparison (x86_64-linux)
- `llama-cpp`: stable `6981`, unstable `8069`
- `open-webui`: stable `0.8.5`, unstable `0.8.3`
- `rocmPackages.rocminfo`: stable `6.4.3`, unstable `7.1.1`

### Notes
- Unstable is not strictly newer for every package (`open-webui` is lower in this snapshot).
- Graphical desktop boot + full AI stack health inside VM is still pending.
