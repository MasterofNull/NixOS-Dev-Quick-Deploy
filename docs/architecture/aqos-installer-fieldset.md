# AQ-OS installer-owned `mySystem` field set

Status: P0 contract, inert until execution verification exists.

The machine-readable authority is
[`config/aqos-mysystem-fieldset-v1.json`](../../config/aqos-mysystem-fieldset-v1.json).
It classifies every field currently projected by the module catalog exactly once:

- `user-intent`: a closed profile or role choice accepted by the trusted resolver;
- `detector`: hardware evidence, never a user or model preference;
- `expert-only`: catalog activation coverage that the installer must not write.

All unlisted `mySystem.*` fields are expert-only. In particular, the installer
cannot project secrets, disk/LUKS choices, arbitrary model/backend arguments,
ports/listen addresses, remote URLs, trust roots, SSH identity, or boot/security
bypasses. `roles.mobile.enable` is an expert override; normal installation uses
detector-owned `hardware.isMobile`. `deployment.rootFsckMode` remains expert-only
until the recovery product and authorization flow exist.

This contract does not activate projection. P0 resolver output remains
`executable=false` until a later gateway independently re-verifies the resolved
lock/source identity and applies only fields whose authority permits projection.
Multi-GPU primary/iGPU assignment and missing storage/mobile evidence must fail
closed rather than guess.
