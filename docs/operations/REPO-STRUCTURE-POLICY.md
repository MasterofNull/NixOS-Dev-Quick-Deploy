# Repository Structure Policy
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-05


## Goal

Prevent repo sprawl by enforcing deterministic placement for all new files.
Legacy files are grandfathered through `config/repo-structure-allowlist.txt` and will be migrated in controlled passes.

## Required Placement

### Scripts
- New scripts must live under subject folders:
  - `scripts/deploy/`
  - `scripts/health/`
  - `scripts/security/`
  - `scripts/reliability/`
  - `scripts/performance/`
  - `scripts/observability/`
  - `scripts/testing/`
  - `scripts/data/`
  - `scripts/ai/`
  - `scripts/automation/`
  - `scripts/utils/`
  - `scripts/governance/`
  - `scripts/lib/`
- New files in `scripts/` root are blocked by policy.

### Documentation
- New docs must live under subject folders (for example):
  - `docs/operations/`
  - `docs/architecture/`
  - `docs/security/`
  - `docs/testing/`
  - `docs/roadmap/`
  - existing structured folders (`docs/development`, `docs/agent-guides`, etc.)
- New files in `docs/` root are blocked by policy.

### Root Directory
- New root-level markdown/code/script files are blocked unless explicitly approved and allowlisted.
- Runtime crash artifacts (for example `core`, `core.*`) are disallowed and must be gitignored.
- Transient runtime/editor dotfiles (for example `.nvimlog`, `.python_history`) are disallowed and must be gitignored.

## Enforcement

- Local pre-commit hook runs:
  - `scripts/governance/repo-structure-lint.sh --staged`
- CI runs:
  - `scripts/governance/repo-structure-lint.sh --all`
  - `scripts/governance/check-root-file-hygiene.sh`
  - `scripts/governance/check-root-script-shim-only.sh`
  - `scripts/governance/check-doc-metadata-standards.sh`
  - `scripts/governance/check-doc-script-path-migration.sh`
  - `scripts/governance/check-script-header-standards.sh` (changed scripts in CI)
  - `scripts/governance/check-naming-label-consistency.sh` (non-mutating default report)
  - `scripts/governance/check-archive-path-consistency.sh`
  - `scripts/governance/check-legacy-deprecated-root.sh`
  - `scripts/governance/check-generated-artifact-hygiene.sh`
  - `scripts/governance/check-deprecated-docs-location.sh`
- Quick deploy lint includes repo structure check:
  - `scripts/governance/quick-deploy-lint.sh --mode fast`
  - includes `scripts/governance/check-root-file-hygiene.sh`
  - includes `scripts/governance/check-root-script-shim-only.sh`
  - includes `scripts/governance/check-doc-metadata-standards.sh`
  - includes `scripts/governance/check-doc-script-path-migration.sh`
  - includes `scripts/governance/check-script-header-standards.sh --all`
  - includes `scripts/governance/check-naming-label-consistency.sh`
  - includes `scripts/governance/check-archive-path-consistency.sh`
  - includes `scripts/governance/check-legacy-deprecated-root.sh`
  - includes `scripts/governance/check-generated-artifact-hygiene.sh`
  - includes `scripts/governance/check-deprecated-docs-location.sh`

## Legacy Exception Handling

- Existing out-of-policy paths are listed in:
  - `config/repo-structure-allowlist.txt`
- This file is **not** for routine additions.
- New entries require explicit migration justification and follow-up move task.
