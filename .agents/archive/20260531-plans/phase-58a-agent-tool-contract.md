# Phase 58A.x — Agent Tool Contract Hardening

## Objective

Remove a source of repeated cross-agent friction before continuing the larger capability-expansion architecture program by making the default tool surface explicit, lean, and consistent across docs plus runtime policy.

## Scope lock

### In scope
- Tool-contract PRD and reference guide.
- Instruction updates for universal tool order and fallback discipline.
- Runtime isolation default allowlist alignment.
- Planning linkage back to Phase 58A.

### Out of scope
- Domain-specific SDK/toolchain expansion.
- Runtime deployment or host rebuild.
- Refactoring every historical instruction document in one pass.

## Workstreams

1. **Contract** — write the canonical baseline, preferred order, and fallback rules.
2. **Instruction projection** — update workflow, onboarding, Gemini guidance, and generated Gemini context.
3. **Runtime alignment** — expose the same preferred inspection tools in default isolation profiles.
4. **Program continuity** — mark this as an enabling slice and return Phase 58A to canonical-kernel work.

## Step plan

1. Record intent lock and write the PRD.
2. Add `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`.
3. Update `.agent/WORKFLOW-CANON.md`, `AGENTS.md`, `.agent/GEMINI.md`, and `scripts/data/sync-agent-instructions` so they all point at the same bounded tool order.
4. Regenerate or manually align `.gemini/context.md`.
5. Extend default runtime isolation allowlists in `nix/modules/core/options.nix` with the preferred non-network discovery tools.
6. Update Phase 58A planning notes to show this slice as an enabling dependency, not a replacement for the canonical-kernel work.
7. Validate syntax and run the repo governance gate.

## Validation

- `python3 -m py_compile scripts/data/sync-agent-instructions`
- `python3 scripts/data/sync-agent-instructions --dry-run --verbose`
- `nix-instantiate --parse nix/modules/core/options.nix`
- targeted search review of touched instruction surfaces
- `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Rollback

- Revert the additive instruction/tool-contract documents.
- Revert the allowlist expansion in `nix/modules/core/options.nix` if runtime policy review rejects it.
- Preserve the earlier Gemini search-before-read hardening independently; it should not be rolled back with this slice.

## Return path to main program

After this slice, resume:
1. `58A.0 — Canonical Kernel Declaration`
2. `58A.1 — Canonical role matrix SSOT`
3. downstream capability-expansion work from the existing master PRD and team plan.
