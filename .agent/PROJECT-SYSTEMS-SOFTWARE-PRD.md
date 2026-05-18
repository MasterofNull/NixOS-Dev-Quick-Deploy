# PRD — systems-software Domain Activation

**Domain tag:** `systems-software`
**Status:** Proposed — Phase 58A capability expansion
**Authors:** Claude (orchestrator/architect)
**Date:** 2026-05-18
**Upstream template:** `docs/architecture/domain-activation-template.md`

---

## Problem Statement

NixOS module authoring, shell scripting, and deployment tooling are the primary development surfaces of this project. Yet there is no canonical domain that:

- routes Nix/NixOS development queries to an appropriate execution profile
- binds agents to existing static-analysis tools (`statix`, `deadnix`, `alejandra`, `bash -n`, `shellcheck`)
- persists Nix/systems patterns and findings to a dedicated AIDB namespace
- gives agents a shared instruction surface for systems-level work

Without a formal domain, NixOS module work falls through to ad-hoc routing and context-free delegation — producing inconsistent results and repeated rediscovery of project constraints.

---

## Goal

Establish `systems-software` as a first-class capability domain. Initial activation covers:

1. Registering the domain (proposed → implemented cycle begins)
2. Declaring the routing preference and AIDB namespace
3. Authoring the agent instruction surface (`.agent/SYSTEMS-SOFTWARE-INSTRUCTIONS.md`)
4. Wiring a baseline validation hook that confirms Nix static-analysis tooling is reachable

Provisioning of `shellcheck` as a Nix package (currently absent from profile), and AIDB seeding with NixOS patterns, are follow-on slices once the domain reaches `validated`.

---

## Kernel Objects Touched

| Kernel object | How this domain touches it |
|---|---|
| `intent` | Adds `systems-software` intent class → routes to `local-tool-calling` by default (Nix eval is local) |
| `memory-evidence` | Nix patterns, deployment findings → AIDB namespace `nix-systems-patterns` via MemoryBroker |
| `route-profile` | Prefers `local-tool-calling` for Nix/shell tooling invocation; `remote-reasoning` for architectural policy; `default` for module authoring queries |
| `workflow-session` | NixOS deployment flows use nixos-quick-deploy.sh → WorkflowExecutor DAG pattern |

---

## Routing Profile(s)

| Use case | Profile | Rationale |
|---|---|---|
| Nix eval / lint / static analysis | `local-tool-calling` | CLI-based; statix/deadnix/alejandra are local tools |
| NixOS module authoring query | `default` | Qwen can draft modules; local sufficient |
| Architecture / policy review | `remote-reasoning` | Requires deeper reasoning on NixOS module system semantics |
| Deployment coordination | `local-tool-calling` | nixos-quick-deploy.sh and aq-qa run locally |

All profiles already exist in the canonical inventory (`docs/architecture/routing-profile-inventory.md`). No new profile needed.

---

## AIDB Namespace

**Namespace:** `nix-systems-patterns`

Purpose: Store reusable NixOS module patterns, known-good option configurations, deployment anti-patterns, and hardware capability findings so future sessions inherit institutional Nix knowledge.

Initial seeding: extract patterns from `nix/modules/` directory and commit-commentary during `implemented` slice.
Indexing: add to `scripts/automation/aidb-reindex.sh` once domain reaches `implemented`.

---

## Tool Preferences

### Preferred tools (ordered)

1. `scripts/governance/nix-static-analysis.sh --non-blocking` — statix + deadnix + alejandra on Nix files
2. `statix check nix/` — Nix anti-pattern linter
3. `deadnix nix/` — dead code elimination for Nix
4. `alejandra --check nix/` — Nix formatter compliance
5. `bash -n <script>` — always available; mandatory for all shell scripts
6. `shellcheck <script>` — preferred over bash -n when available (not yet provisioned)
7. `nix-instantiate --parse <file>` — parse check for individual Nix files
8. `scripts/governance/discover-system-facts.sh` — hardware/facts baseline refresh
9. `scripts/governance/tier0-validation-gate.sh --pre-commit` — always run before commit

### Tool availability status (2026-05-18)

| Tool | Available | Notes |
|---|---|---|
| `bash -n` | Yes | Always present |
| `statix` | Yes (via nix-static-analysis.sh) | Must be in PATH or run via script |
| `deadnix` | Yes (via nix-static-analysis.sh) | Must be in PATH or run via script |
| `alejandra` | Yes (via nix-static-analysis.sh) | Must be in PATH or run via script |
| `shellcheck` | Not yet provisioned | Follow-on slice: systems-software.1 |
| `nix-instantiate` | Yes (NixOS system) | Available in NixOS environment |

### Fallback order

`nix-static-analysis.sh --non-blocking` → `bash -n` → `nix-instantiate --parse` → manual review

### Forbidden

- `bare pip install` inside Nix modules (violates NixOS-first constraint)
- Hardcoded ports or URLs in Nix or Python source (source of truth: `nix/modules/core/options.nix`)
- `--no-verify` on any commit
- `eval()` on Nix expressions from untrusted LLM output
- `nixos-rebuild switch` from Claude shell (sudo setuid missing; requires terminal session)

---

## Architecture Constraints (project-specific)

These constraints are non-negotiable and apply to ALL agents working in this domain:

1. **NixOS-first, flake-based** — no bare pip install, no manual systemctl outside NixOS module
2. **Port SSOT** — `nix/modules/core/options.nix`; never hardcode port values
3. **`deploy-options.local.nix` is gitignored** — secrets/overrides only; policy changes must be git-tracked
4. **Feature flags profile-driven** — `nix/modules/profiles/ai-dev.nix` (`mkDefault true`); hosts override with `mkForce`
5. **Batch deploy cadence** — prefer 3–5 repo-only slices before invoking `nixos-quick-deploy.sh`; deploy only for runtime activation blockers

---

## Acceptance Criteria

1. `config/capability-lifecycle-registry.json` contains a `systems-software` entry at state ≥ `proposed`.
2. `.agent/SYSTEMS-SOFTWARE-INSTRUCTIONS.md` exists with domain tag, task classes, tool preferences, AIDB namespace binding.
3. `config/validation-check-registry.json` contains a `systems-software-health` check that exits 0 when baseline tooling is accessible.
4. `aq-qa 0` includes the `systems-software-health` check without regression.
5. When domain reaches `implemented` (follow-on slice): `shellcheck` provisioned in Nix profile; AIDB `nix-systems-patterns` namespace seeded with ≥20 patterns; `nix-static-analysis.sh` runs clean on staged Nix files.
6. When domain reaches `validated`: Gemini review-gate PASS on one NixOS module change routed through domain; aq-qa check exits 0 in CI.

---

## Security and Safety Considerations

- Nix expression evaluation is sandboxed by the Nix daemon — agents should prefer `nix-instantiate --parse` (parse-only) over `nix eval` (may trigger builds).
- `nixos-rebuild switch` is a high-impact system operation — requires user confirmation or a terminal session; never invoke from Claude shell.
- Shell scripts generated in this domain are subject to `bash -n` + `shellcheck` (once provisioned) before commit.
- Avoid `mkForce` in shared modules — use `mkDefault` and let host-level overrides win.

---

## Rollback Procedure

1. Set `systems-software` registry state to `blocked`.
2. Remove `systems-software` intent class from `config/intent-routing-map.json` if added.
3. Disable `systems-software-health` check in `config/validation-check-registry.json` (`"enabled": false`).
4. Archive (do not delete) `nix-systems-patterns` AIDB namespace content.
5. Remove `shellcheck` from Nix profile if provisioned.

---

## Open Items (follow-on slices)

| Item | Slice |
|---|---|
| Provision `shellcheck` in Nix profile (`nix/modules/profiles/ai-dev.nix`) | systems-software.1 |
| Wire `systems-software` intent class in `config/intent-routing-map.json` | systems-software.2 |
| Seed `nix-systems-patterns` AIDB namespace from `nix/modules/` | systems-software.3 |
| Update `systems-software-health` to test statix/shellcheck invocation | systems-software.4 |
| Gemini review gate on first module-authoring output | systems-software.5 (→ validated) |

---

## Related Docs

- `docs/architecture/domain-activation-template.md`
- `docs/architecture/capability-lifecycle.md`
- `docs/architecture/gemini-review-gate.md`
- `docs/architecture/routing-profile-inventory.md`
- `docs/architecture/qwen-task-eligibility.md`
- `scripts/governance/nix-static-analysis.sh`
- `scripts/governance/tier0-validation-gate.sh`
- `nix/modules/core/options.nix` (port SSOT)
- `nix/modules/profiles/ai-dev.nix` (feature flags)
- `config/hardware-capability-matrix.json` (hardware facts for Nix module choices)
