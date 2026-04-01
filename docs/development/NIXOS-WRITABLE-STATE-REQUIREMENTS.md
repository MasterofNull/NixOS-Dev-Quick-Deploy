# NixOS Writable State Requirements

Status: Active  
Owner: AI Stack Maintainers  
Last Updated: 2026-04-01

## Purpose

Prevent repeat regressions where declarative NixOS services try to write into:
- the repo checkout
- `/home/...` paths protected by `ProtectHome=read-only`
- other non-declarative locations that are writable in ad hoc shells but not under systemd hardening

## Rule

Treat `repoPath` as read-only for system services.

Allowed uses of `repoPath`:
- source code
- static config
- scripts
- test fixtures
- repo-grounded artifacts produced by manual developer workflows

Disallowed uses of `repoPath` for hardened services:
- runtime databases
- lockfiles
- telemetry streams
- mutable caches
- generated coordination state
- service-owned JSON registries

## Required Pattern

For any service-facing component:
1. Read static inputs from `repoPath` or injected config env vars.
2. Write mutable state under `/var/lib/ai-stack/...` or another declaratively owned state root.
3. Prefer `StateDirectory`, `RuntimeDirectory`, tmpfiles, or explicit Nix options over ad hoc path creation.
4. If a path must vary, inject it through env vars and give it a writable state-dir default.

## Classification

Use this split consistently:

- `repo-grounded artifact`
  - may live under `.agents/` or docs-oriented repo paths
  - intended for developer review, audits, or committed/generated artifacts
  - should not be assumed writable by systemd services

- `runtime mutable state`
  - must live under `/var/lib/ai-stack/...`, `/run/...`, or another declared writable root
  - includes caches, queues, registries, checkpoints, lockfiles, and live telemetry

## Review Checklist

Before activating a new service integration:
- verify `ReadOnlyPaths` still includes the repo path where appropriate
- verify all `.mkdir`, `write_text`, JSON writes, and lockfiles target writable state roots
- verify no hardcoded `/home/.../Documents/...` repo path remains in service code
- verify defaults are env-injectable for tests and deployments
- verify `aq-qa 0` and `tier0-validation-gate.sh --pre-commit` still pass

## Recent Failures This Prevents

- Hybrid coordinator crash from progressive-disclosure runtime state trying to create `.agents/context-tiers` under a read-only repo checkout
- Repeated repo/home path drift bugs when hardened services run with `ProtectHome=read-only`
- Misleading local-shell success where code can write into the checkout but deployed services cannot

## Current Canonical Defaults

Examples of correct writable defaults:
- `/var/lib/ai-stack/hybrid/context-tiers`
- `/var/lib/ai-stack/hybrid/playbooks`
- `/var/lib/ai-stack/hybrid/telemetry/...`
- `/var/lib/ai-stack/security/...`

## Notes

This does not ban `.agents/` completely.

`.agents/` remains acceptable for:
- roadmap and planning artifacts
- developer-facing generated reports
- manual review exports

It is not acceptable as the default writable target for live system services.
