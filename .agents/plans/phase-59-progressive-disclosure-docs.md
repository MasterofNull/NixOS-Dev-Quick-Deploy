# Phase Plan — Progressive Disclosure Documentation Overhaul (Phase 59)

## Objective
Update all progressive disclosure documentation to reflect the current Phase 58 system state, retire obsolete guides, and consolidate references.

## Scope Lock
- **Files to Archive**:
  - `docs/PROGRESSIVE-DISCLOSURE-GUIDE.md`
  - `docs/operations/agent-context-progressive-disclosure.md`
- **Files to Update**:
  - `docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md` (Primary Rewrite)
  - `README.md` (Update links and tool descriptions)
  - `docs/AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md` (Update redirect targets)
- **Knowledge Sources**:
  - `config/progressive-disclosure-domains.json` (Domains/Triggers)
  - `scripts/ai/` (Tool behaviors)
  - `nix/modules/core/options.nix` (Ports)

## Workstreams

### 1. Preparation & Archiving
- [ ] Move `docs/PROGRESSIVE-DISCLOSURE-GUIDE.md` to `docs/archive/legacy-sequence/03-PROGRESSIVE-DISCLOSURE-LEGACY.md`.
- [ ] Move `docs/operations/agent-context-progressive-disclosure.md` to `docs/archive/legacy-sequence/04-AGENT-CONTEXT-PD-LEGACY.md`.

### 2. Primary Documentation Rewrite
- [ ] Rewrite `docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md` with:
  - Corrected ports (8002/8003).
  - Current 7 domains (nixos-dev, web-dev, ai-harness, data-engineering, devops, security, documentation).
  - Modern toolset (`aq-prime`, `aq-hints`, `aq-context-card`, `aq-qa --layer`).
  - Updated status: Phase 58+ / Active.

### 3. Integration & Linkage
- [ ] Update `README.md` to point to `docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md`.
- [ ] Update `docs/AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md` redirect list.
- [ ] Ensure `GEMINI.md` references are still valid (they seem to be, as they point to `aq-prime`).

## Validation
- [ ] Verify all file moves are tracked by git.
- [ ] Verify all internal markdown links are functional.
- [ ] Verify port numbers and domain names match the live config.

## Rollback
- `git checkout docs/` to restore documentation state.
