---
doc_type: prd
id: systems-software-prd
title: Systems Software Domain PRD
status: active
owner: AI Stack Maintainers
last_updated: "2026-06-04"
---

# Systems Software Domain — PRD

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-06-04

## Purpose

This PRD governs the systems-software capability domain on the NixOS AI stack.
It covers shell scripting quality, NixOS service configuration, system tooling
provision, and low-level infrastructure automation.

## Capabilities

| Capability | Status | Owner |
|------------|--------|-------|
| Shell static analysis (shellcheck) | Active | ai-dev system package |
| NixOS service configuration | Active | nix/modules/services/ |
| System CLI tooling (rg, fd, fzf, delta, etc.) | Active | nix/data/profile-system-packages.nix |
| Agent CLI wrappers (agrep, als, acat) | Active | scripts/ai/ |
| Governance scripts (tier0, focused-ci) | Active | scripts/governance/ |

## Non-Goals

- Kernel module development
- Hardware driver management
- Cross-compilation toolchains

## Architecture

Systems-software tooling is declared in `nix/data/profile-system-packages.nix` under the
`ai-dev` profile and evaluated by `nix/modules/core/base.nix`. Shell scripts are linted via
`shellcheck` as part of the tier0 pre-commit gate.

## Active Constraints

- All shell scripts must pass `shellcheck` (enforced by tier0 gate)
- System package names must resolve in nixpkgs (validated by `base.nix` missing-packages filter)
- NixOS-first: no bare `pip install` or manual `systemctl enable`; all services declared in Nix
