---
title: Tiered Deterministic Auto-Update PRD
status: DRAFT (perspectives round open)
owner_directive: 2026-10-01
extends: .agents/plans/split-channel-packaging/DESIGN.md
---

# Tiered deterministic auto-update

## Owner directive (2026-10-01)
Routine updates (release watch, version compare, pin bump, lock refresh, flake update,
rebuild + switch) are deterministic scripts in the system update pipeline — never agent
work (no token burn, no context growth). The system stays at the safest frontier:
**core system services** on the safe tier; **agentic and fast-moving tools** (agent
CLIs/models, IDEs, language toolchains, database client languages, SOPS, kernel,
performance tools) on the newest versions.

## Existing machinery (reuse, do not duplicate)
- Split channels: stable `nixos-26.05` + `nixpkgs-unstable`; fast-lane overlay with a
  single-source manifest `nix/overlays/fast-lane-manifest.nix` (only `antigravity` active).
- `nix/modules/core/fast-lane-staleness-monitor.nix` (notify-only staleness checker).
- `scripts/maintenance/system-update-full.sh` (runs `nix flake update`).
- Capability-intake pins for tool-authority executables (test-enabled-external-mcp-candidates).

## Slices
- **U1 (building now)** `aq-pin-watch`: deterministic release watcher for tool-authority
  executables (MCP servers etc.): registry query → semver compare → minor/patch bump across
  all pin sites + intake registry → run intake test; major → owner sign-off record. No LLM.
- **U2** Tier policy `config/update-tiers.json` (frontier vs core categories → package
  attrs) feeding the fast-lane manifest; promotion of frontier categories (agent CLIs, IDE,
  toolchains, SOPS, kernel via `linuxPackages_latest`, perf tools) each with an automated
  build check.
- **U3** Unattended pipeline (extends system-update-full.sh, root systemd timer behind
  `mySystem.autoUpdate.enable`, default off): flake update → aq-pin-watch → lock refresh
  (hash-preserving) → `nixos-rebuild build` → health/eval gates → `switch` → post-switch
  health (aq-qa 0, failed units, service probes) → automatic `--rollback` on failure →
  report + RSI incident on failure only. Kernel changes: switch staged, reboot owner-scheduled
  (known Renoir audio/kernel-skew behaviour).
- **U4** Observability: last-run status, versions moved, rollbacks — via aq-rsi status +
  dashboard card (CLI-first).

## Acceptance
- A full unattended run with no agent tokens produces: updated lock/pins, a successful
  build, a switch with green post-switch health, or an automatic rollback with an incident.
- Core-tier services never move channel without passing their tier gate.
- Hash-pinned locks keep hashes (guard test).

## Open questions for the round
1. Which packages exactly belong to frontier vs core (initial list)?
2. Kernel on frontier: `linuxPackages_latest` vs a pinned recent LTS bumped by the pipeline?
3. Post-switch health gate thresholds and rollback trigger set.
4. Timer cadence and quiet hours; how to avoid switching during active agent work.
