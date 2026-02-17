# Repository Scope Contract

Last Updated: 2026-02-16
Owner: Phase 27 governance track

## Purpose

This repository has one primary responsibility:
- deliver a clean, flake-first NixOS deployment system for personal SBC/laptop/desktop/small-server environments

Secondary responsibility:
- maintain agent skill/MCP workflow tooling that directly supports that deployment system.

Out of scope:
- unrelated experiments and ad-hoc backups in active paths
- duplicate skill trees and floating references

## Canonical Ownership Map

| Path | Owner Surface | Purpose |
| --- | --- | --- |
| `nix/` | System Declarative Config | NixOS modules, profiles, host facts |
| `scripts/` | Deployment + CLI | Deployment entrypoints and governance tooling |
| `.agent/skills/` | Canonical Skills | Source-of-truth skill definitions |
| `ai-stack/` | AI Runtime Stack | AI service manifests and integrations |
| `docs/` | Governance + Ops Docs | Stable architecture/runbook/guidance |
| `archive/` | Historical/Fixture | Non-active backups and test fixtures only |

## Architecture Map (Lightweight)

- Deploy layer: `scripts/deploy-clean.sh` + `flake.nix` + `nix/`
- Runtime layer: `ai-stack/`
- Agent tooling layer: `.agent/skills/` + `scripts/aqd`
- Governance layer: lint/test scripts in `scripts/`, CI in `.github/workflows/test.yml`

## Governance Rules

1. New deployment behavior must land in `nix/` + flake path first.
2. `.agent/skills/` is canonical; mirrored trees are optional and explicit.
3. Skill docs must avoid floating external refs (no `main`/`master` links).
4. Filesystem backup trees do not belong in active root paths.
5. CLI wrappers in `scripts/aqd` are the preferred user/agent interface for skill/MCP workflows.
