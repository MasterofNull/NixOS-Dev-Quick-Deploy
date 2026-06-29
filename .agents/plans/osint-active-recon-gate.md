---
doc_type: plan
id: osint-active-recon-gate
title: OSINT Active Recon Runtime Gate
status: active
owner: codex
last_updated: 2026-06-29
parent_prd: osint-active-recon-gate-prd
---

# OSINT Active Recon Runtime Gate

## Slice

- [x] Add PRD and plan for active recon gate.
- [x] Add coordinator `osint_recon_status` and fail-closed `osint_recon` admission checks.
- [x] Add local-agent `osint_recon_status`.
- [x] Update tooling manifest to prefer passive OSINT and status-gate routing.
- [x] Add focused regression coverage.
- [x] Validate focused checks.
- [x] Validate aq-qa phase 0.
- [x] Validate tier0.
- [x] Commit scoped changes.

## Activation

Repo-local behavior is active for direct code paths. Running NixOS services may require the normal rebuild cadence to pick up coordinator and local-agent registry changes from the Nix store.
