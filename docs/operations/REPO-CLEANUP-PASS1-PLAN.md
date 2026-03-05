# Repo Cleanup Pass 1 Plan

## Objective

Hard-stop future disorganization and establish an enforceable structure baseline before moving legacy files.

## Completed in Pass 1

- Added structure enforcement lint:
  - `scripts/governance/repo-structure-lint.sh`
- Added inventory generator:
  - `scripts/governance/generate-repo-cleanup-inventory.sh`
- Added legacy grandfather list:
  - `config/repo-structure-allowlist.txt`
- Wired pre-commit enforcement:
  - `.githooks/pre-commit`
- Wired CI enforcement:
  - `.github/workflows/test.yml`
  - `.github/workflows/tests.yml`
- Wired quick deploy lint enforcement:
  - `scripts/quick-deploy-lint.sh`
- Published policy:
  - `docs/operations/REPO-STRUCTURE-POLICY.md`
- Published initial inventory:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`

## Completed in Pass 2

- Moved new reliability/procedure docs from `docs/` root into subject directories:
  - `docs/operations/reliability/`
  - `docs/operations/procedures/`
  - `docs/operations/standards/`
- Moved new reliability/performance/security/observability scripts from `scripts/` root into subject directories:
  - `scripts/reliability/`
  - `scripts/performance/`
  - `scripts/security/`
  - `scripts/observability/`
- Archived all legacy numbered docs (`docs/00-*` through `docs/35-*`) into:
  - `docs/archive/legacy-sequence/`
- Rewrote references for moved files in active docs/roadmaps.
- Fixed policy lint behavior to evaluate the working tree (`git ls-files --cached --others`) and ignore deleted index paths.

## Pass 3

- Migrate active scripts from `scripts/` root to `scripts/<subject>/...` in batches (`aq`, `deploy`, `health`, `security`).
- Update all callsites in each batch:
  - Nix modules
  - deploy scripts
  - CI workflows
  - documentation links

## Pass 4

- Migrate non-numbered docs from `docs/` root into subject folders (`operations`, `development`, `prsi`, `archive/legacy-docs`).
- Fix internal doc links and index pages.

## Safety Gates (every pass)

- `scripts/governance/repo-structure-lint.sh --all`
- `scripts/quick-deploy-lint.sh --mode fast`
- `scripts/testing/validate-runtime-declarative.sh`
- `scripts/testing/check-mcp-health.sh`
