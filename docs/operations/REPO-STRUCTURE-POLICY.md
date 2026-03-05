# Repository Structure Policy

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

## Enforcement

- Local pre-commit hook runs:
  - `scripts/governance/repo-structure-lint.sh --staged`
- CI runs:
  - `scripts/governance/repo-structure-lint.sh --all`
- Quick deploy lint includes repo structure check:
  - `scripts/quick-deploy-lint.sh --mode fast`

## Legacy Exception Handling

- Existing out-of-policy paths are listed in:
  - `config/repo-structure-allowlist.txt`
- This file is **not** for routine additions.
- New entries require explicit migration justification and follow-up move task.
