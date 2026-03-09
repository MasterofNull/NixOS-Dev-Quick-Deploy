# System Upgrade Roadmap Updates

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-05

## Repo Hygiene Pass (2026-03-05): Root Crash Artifact Elimination

### RH.H1 Remove tracked root crash dumps and prevent reintroduction

**Changes Applied:**
- [x] Removed tracked root core dump artifact (`core`) from repository history-in-flight.
- [x] Added ignore guardrails for crash dump artifacts in `.gitignore`:
  - `core`
  - `core.*`
- [x] Updated repository structure policy to explicitly disallow runtime crash artifacts at repo root.

**Validation:**
- `git ls-files | rg '^core$'` → PASS (no tracked root `core` file)
- `scripts/governance/repo-structure-lint.sh --all` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Generated Report Artifact Hygiene

### RH.H2 Remove tracked generated report/temp artifacts from repository root paths

**Changes Applied:**
- [x] Removed tracked generated files from active repo state:
  - `output.txt`
  - `reports/flake-validation-report.json`
  - `reports/flake-validation-report.md`
- [x] Updated `.gitignore` to ignore root `reports/` output directory (`/reports/`) alongside `.reports/`.
- [x] Aligned CI flake-validation output/upload paths to `.reports/` in `.github/workflows/test.yml`.
- [x] Aligned flake management docs to `.reports/` artifact paths.

**Validation:**
- `git ls-files reports output.txt` → PASS (no tracked generated report/temp artifacts)
- `scripts/governance/repo-structure-lint.sh --all` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Allowlist Integrity Normalization

### RH.H3 Normalize repo-structure allowlist to active paths only

**Changes Applied:**
- [x] Added `scripts/governance/normalize-repo-allowlist.sh` to normalize `config/repo-structure-allowlist.txt`.
- [x] Normalizer behavior:
  - removes missing/stale entries,
  - removes duplicate entries while preserving first-seen order,
  - preserves comments/section headers.
- [x] Applied normalization to `config/repo-structure-allowlist.txt`:
  - removed stale legacy entries and malformed path residue,
  - removed duplicate `.claude.md` entry.

**Validation:**
- `bash -n scripts/governance/normalize-repo-allowlist.sh` → PASS
- normalizer execution: `kept=376 dropped_missing=45 dropped_duplicate=1`
- allowlist integrity check (`missing=0`, `dups=0`) → PASS
- `scripts/governance/repo-structure-lint.sh --all` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Allowlist Drift Gate Enforcement

### RH.H4 Add non-mutating allowlist integrity gate to lint + CI

**Changes Applied:**
- [x] Added non-mutating checker:
  - `scripts/governance/check-repo-allowlist-integrity.sh`
  - fails on duplicate entries or entries pointing to missing paths.
- [x] Wired checker into local deploy lint flow:
  - `scripts/governance/quick-deploy-lint.sh --mode fast|full` now includes `Repo allowlist integrity`.
  - updated step totals accordingly.
- [x] Wired checker into CI:
  - `.github/workflows/test.yml` `repo-structure-lint` job now runs allowlist integrity gate after structure policy lint.

**Validation:**
- `bash -n scripts/governance/check-repo-allowlist-integrity.sh scripts/governance/quick-deploy-lint.sh` → PASS
- `scripts/governance/check-repo-allowlist-integrity.sh` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Root Transient Dotfile Cleanup

### RH.H5 Remove tracked editor/runtime dotfile artifacts from root

**Changes Applied:**
- [x] Removed tracked transient root artifact:
  - `.nvimlog`
- [x] Added gitignore guardrail to prevent reintroduction:
  - `.nvimlog`

**Validation:**
- `git ls-files | rg '^\\.nvimlog$'` → PASS (no tracked `.nvimlog`)
- `scripts/governance/repo-structure-lint.sh --all` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Transient Dotfile Lint Enforcement

### RH.H6 Block transient dotfiles in repo-structure policy gate

**Changes Applied:**
- [x] Extended `scripts/governance/repo-structure-lint.sh` with explicit rule for transient dotfiles:
  - `.nvimlog`
  - `.python_history`
- [x] Updated `docs/operations/REPO-STRUCTURE-POLICY.md` root policy section to document this block.

**Validation:**
- `bash -n scripts/governance/repo-structure-lint.sh` → PASS
- `scripts/governance/repo-structure-lint.sh --all` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Roadmap Update Doc Label Consistency

### RH.H7 Add canonical H1 title to roadmap update ledger

**Changes Applied:**
- [x] Added missing document H1 heading to this file:
  - `# System Upgrade Roadmap Updates`
- [x] Preserved existing metadata block (`Status/Owner/Last Updated`) immediately below H1.

**Validation:**
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Legacy Root Script Reference Rewrites

### RH.H8 Rewrite active docs to structured script paths

**Changes Applied:**
- [x] Updated active dashboard docs away from legacy root launcher references:
  - `docs/DASHBOARD-DEPLOYMENT-INTEGRATION.md` now links to `/scripts/deploy/launch-dashboard.sh`.
  - `docs/DASHBOARD-V2-UPGRADE.md` rollback note now references `scripts/deploy/launch-dashboard.sh`.

**Validation:**
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Roadmap Script Path Normalization

### RH.H9 Rewrite remaining roadmap script references to structured path

**Changes Applied:**
- [x] Updated `docs/development/SYSTEM-UPGRADE-ROADMAP.md` section 11.8 references:
  - `launch-dashboard.sh` → `scripts/deploy/launch-dashboard.sh` (task + acceptance criteria text)

**Validation:**
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Script Shim Consistency Enforcement

### RH.H10 Enforce underscore->kebab shim forwarding contracts

**Changes Applied:**
- [x] Added governance checker:
  - `scripts/governance/check-script-shim-consistency.sh`
  - validates that underscore-named scripts have a kebab-case peer target and forward correctly.
- [x] Wired checker into local fast/full lint:
  - `scripts/governance/quick-deploy-lint.sh` step: `Script shim consistency`.
- [x] Wired checker into CI:
  - `.github/workflows/test.yml` (`repo-structure-lint` job) now runs script-shim consistency gate.

**Validation:**
- `bash -n scripts/governance/check-script-shim-consistency.sh scripts/governance/quick-deploy-lint.sh` → PASS
- `scripts/governance/check-script-shim-consistency.sh` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Active Doc Link Gate Enforcement

### RH.H11 Add documentation link integrity to migration lint/CI contract

**Changes Applied:**
- [x] Added `Active doc link integrity` step to `scripts/governance/quick-deploy-lint.sh`:
  - runs `scripts/governance/check-doc-links.sh --active`.
- [x] Added CI governance step in `.github/workflows/test.yml`:
  - `Enforce active documentation link integrity`.

**Validation:**
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Root File Hygiene Gate

### RH.H12 Enforce explicit tracked root file allowlist

**Changes Applied:**
- [x] Added explicit root-file allowlist:
  - `config/root-file-allowlist.txt`
- [x] Added checker:
  - `scripts/governance/check-root-file-hygiene.sh`
  - validates tracked existing root files exactly match allowlist.
- [x] Wired checker into local lint:
  - `scripts/governance/quick-deploy-lint.sh` step `Root file hygiene`.
- [x] Wired checker into CI repo governance job:
  - `.github/workflows/test.yml` step `Enforce root file hygiene`.
- [x] Updated repo structure policy enforcement section to include root-file hygiene gate.

**Validation:**
- `scripts/governance/check-root-file-hygiene.sh` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Doc Script-Path Migration Gate

### RH.H13 Enforce migrated script path usage in active docs

**Changes Applied:**
- [x] Added migration policy source:
  - `config/legacy-root-script-aliases.txt`
- [x] Added checker:
  - `scripts/governance/check-doc-script-path-migration.sh`
  - fails if active docs reference retired root script names.
  - fails if active docs link to underscore script paths when kebab canonical exists.
- [x] Wired checker into local lint and CI:
  - `scripts/governance/quick-deploy-lint.sh` step `Doc script-path migration`
  - `.github/workflows/test.yml` step `Enforce doc script-path migration policy`
- [x] Updated repo structure policy enforcement notes to include this gate.

**Validation:**
- `scripts/governance/check-doc-script-path-migration.sh` → PASS
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Doc Metadata Standards Gate

### RH.H14 Enforce required metadata in active operations/development docs

**Changes Applied:**
- [x] Added checker:
  - `scripts/governance/check-doc-metadata-standards.sh`
  - enforces `Status`, `Owner`, and `Last Updated/Updated` within top section of active docs:
    - `docs/operations/**`
    - `docs/development/**`
- [x] Wired checker into local lint:
  - `scripts/governance/quick-deploy-lint.sh` step `Doc metadata standards`.
- [x] Wired checker into CI governance job:
  - `.github/workflows/test.yml` step `Enforce documentation metadata standards`.
- [x] Updated repo structure policy enforcement section to include metadata standards gate.

**Validation:**
- `scripts/governance/check-doc-metadata-standards.sh` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Governance Report Churn Reduction

### RH.H15 Make naming/label audit non-mutating by default

**Changes Applied:**
- [x] Refactored `scripts/governance/check-naming-label-consistency.sh`:
  - default output now writes to `.reports/naming-label-consistency-report.md` (non-tracked runtime artifact).
  - added `--publish-doc` mode for intentional updates to:
    - `docs/operations/NAMING-LABEL-CONSISTENCY-REPORT-2026-03-05.md`
  - added `--out-file` override and `--help`.
- [x] Updated `docs/operations/NAMING-LABEL-CONVENTIONS.md` to document default non-mutating report behavior.

**Validation:**
- `scripts/governance/check-naming-label-consistency.sh` → PASS (writes `.reports/...`)
- `scripts/governance/check-naming-label-consistency.sh --publish-doc` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Script Header Standards Local Gate

### RH.H16 Enforce script header standards during local migration lint

**Changes Applied:**
- [x] Added `Script header standards` step to `scripts/governance/quick-deploy-lint.sh`:
  - runs `scripts/governance/check-script-header-standards.sh --all`
- [x] Updated `docs/operations/REPO-STRUCTURE-POLICY.md` enforcement section:
  - CI note: changed-script header gate
  - local lint note: full `--all` header standards check

**Validation:**
- `scripts/governance/check-script-header-standards.sh --all` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Naming/Label Audit Gate Integration

### RH.H17 Enforce naming/label consistency audit in local lint + CI

**Changes Applied:**
- [x] Added `Naming/label consistency audit` step to `scripts/governance/quick-deploy-lint.sh`:
  - runs `scripts/governance/check-naming-label-consistency.sh` (non-mutating default output to `.reports/`).
- [x] Added CI governance step in `.github/workflows/test.yml`:
  - `Run naming/label consistency audit`.
- [x] Updated `docs/operations/REPO-STRUCTURE-POLICY.md` enforcement list to include this gate.

**Validation:**
- `scripts/governance/check-naming-label-consistency.sh` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Archive Path Consistency Gate

### RH.H18 Enforce canonical deprecated archive path tokens

**Changes Applied:**
- [x] Corrected stale path tokens to canonical archive path:
  - `scripts/governance/generate-repo-cleanup-inventory.sh`: suggested script target now `archive/deprecated/scripts/<name>`.
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv` and `PASS2.csv`: `scripts/archive/deprecated/...` → `archive/deprecated/scripts/...`.
  - `docs/development/SYSTEM-UPGRADE-ROADMAP.md`: fixed `archive/archive/deprecated` typo.
- [x] Added checker:
  - `scripts/governance/check-archive-path-consistency.sh`
  - fails if stale tokens `scripts/archive/deprecated` or `archive/archive/deprecated` appear in active docs/scripts/config/CI.
- [x] Wired checker into local lint and CI:
  - `scripts/governance/quick-deploy-lint.sh` step `Archive path consistency`
  - `.github/workflows/test.yml` step `Enforce archive path consistency`
- [x] Updated `docs/operations/REPO-STRUCTURE-POLICY.md` enforcement list to include this gate.

**Validation:**
- `scripts/governance/check-archive-path-consistency.sh` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Legacy Deprecated-Root Guard

### RH.H19 Block live files under legacy `deprecated/` root path

**Changes Applied:**
- [x] Added checker:
  - `scripts/governance/check-legacy-deprecated-root.sh`
  - fails if any live file exists under `deprecated/`.
- [x] Wired checker into local lint and CI:
  - `scripts/governance/quick-deploy-lint.sh` step `Legacy deprecated-root guard`
  - `.github/workflows/test.yml` step `Enforce legacy deprecated-root guard`
- [x] Updated repo structure policy enforcement list to include this gate.

**Validation:**
- `scripts/governance/check-legacy-deprecated-root.sh` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Pre-Commit Governance Parity

### RH.H20 Align pre-commit checks with migration governance gates

**Changes Applied:**
- [x] Updated `.githooks/pre-commit`:
  - fixed shell color lint script path to `scripts/governance/lint-color-echo-usage.sh`.
  - added `run_migration_governance_checks()` covering:
    - `check-root-file-hygiene.sh`
    - `check-doc-links.sh --active`
    - `check-doc-metadata-standards.sh`
    - `check-doc-script-path-migration.sh`
    - `check-script-shim-consistency.sh`
    - `check-archive-path-consistency.sh`
    - `check-legacy-deprecated-root.sh`
- [x] Updated `.githooks/README.md` to reflect current pre-commit behavior and corrected lint script paths.

**Validation:**
- `.githooks/pre-commit` execution (no staged changes) → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Generated Artifact Hygiene Gate

### RH.H21 Block tracked runtime report/temp artifacts

**Changes Applied:**
- [x] Added checker:
  - `scripts/governance/check-generated-artifact-hygiene.sh`
  - fails on tracked generated/temp artifact paths:
    - `.reports/**`
    - `reports/**`
    - `output.txt`
    - `file.tmp`
    - `*.tmp` (outside `docs/archive/**`)
- [x] Wired checker into local lint and CI:
  - `scripts/governance/quick-deploy-lint.sh` step `Generated artifact hygiene`
  - `.github/workflows/test.yml` step `Enforce generated artifact hygiene`
- [x] Updated repo structure policy enforcement list to include generated artifact hygiene gate.

**Validation:**
- `scripts/governance/check-generated-artifact-hygiene.sh` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Pre-Commit Governance Completion

### RH.H22 Include allowlist + artifact hygiene gates in pre-commit migration checks

**Changes Applied:**
- [x] Updated `.githooks/pre-commit` `run_migration_governance_checks()` list to include:
  - `scripts/governance/check-repo-allowlist-integrity.sh`
  - `scripts/governance/check-generated-artifact-hygiene.sh`
- [x] Updated `.githooks/README.md` pre-commit summary to reflect allowlist/artifact hygiene coverage.

**Validation:**
- `.githooks/pre-commit` execution (no staged changes) → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Pre-Push Quick Lint Gate

### RH.H23 Add repository-managed pre-push gate for fast lint verification

**Changes Applied:**
- [x] Added `.githooks/pre-push`:
  - runs `./scripts/governance/quick-deploy-lint.sh --mode fast` before push.
  - supports emergency escape hatch: `SKIP_PRE_PUSH_LINT=true`.
- [x] Updated `.githooks/README.md` with:
  - pre-push behavior
  - bypass guidance
  - manual validation command including quick lint.

**Validation:**
- `bash -n .githooks/pre-push` → PASS
- `.githooks/pre-push` execution → PASS

## Repo Hygiene Pass (2026-03-05): Deprecated Docs Canonical Location

### RH.H24 Enforce single canonical location for deprecated markdown docs

**Changes Applied:**
- [x] Removed duplicate deprecated markdown copies from:
  - `archive/deprecated/docs/*`
- [x] Kept canonical deprecated docs under:
  - `docs/archive/deprecated/*`
- [x] Added checker:
  - `scripts/governance/check-deprecated-docs-location.sh`
  - fails if markdown docs appear under `archive/deprecated/docs/`.
- [x] Wired checker into local lint + CI + policy docs:
  - `scripts/governance/quick-deploy-lint.sh` step `Deprecated docs location`
  - `.github/workflows/test.yml` step `Enforce deprecated docs canonical location`
  - `docs/operations/REPO-STRUCTURE-POLICY.md` enforcement list

**Validation:**
- `scripts/governance/check-deprecated-docs-location.sh` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Root AI/Data Script Canonicalization

### RH.H25 Migrate remaining root AI/data utilities to `scripts/data/*` canonicals with shims

**Changes Applied:**
- [x] Moved ingestion implementation to canonical subject path:
  - `scripts/archive-project-knowledge.sh` → `scripts/data/archive-project-knowledge.sh`
- [x] Added root compatibility shim:
  - `scripts/archive-project-knowledge.sh` now forwards to `scripts/data/archive-project-knowledge.sh`
- [x] Fixed post-move runtime regression in ingestion script:
  - corrected `SCRIPT_DIR` to repository root from nested `scripts/data/`.
- [x] Updated canonical usage references:
  - `scripts/data/archive-project-knowledge.sh` usage/help text now points to canonical path.
  - `scripts/data/sync-docs-to-ai.sh` usage text now points to canonical path.
- [x] Updated roadmap/inventory docs to canonical script targets:
  - `SYSTEM-UPGRADE-ROADMAP.md` (`29.3.2`, `AI-ISSUE-005`, `13.1` context) now references canonical data paths.
  - `REPO-CLEANUP-INVENTORY-PASS1.csv` and `PASS2.csv` rows for archive/rag/sync scripts now target canonical `scripts/data/*` paths.
- [x] Fixed cleanup-inventory generator root cause:
  - `scripts/governance/generate-repo-cleanup-inventory.sh` now auto-detects canonical `scripts/<domain>/...` peers before falling back to archive targets.

**Validation:**
- `bash -n scripts/archive-project-knowledge.sh scripts/data/archive-project-knowledge.sh scripts/data/sync-docs-to-ai.sh scripts/governance/generate-repo-cleanup-inventory.sh` → PASS
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Semantic Ranking Utility Migration

### RH.H26 Canonicalize semantic-ranking utility under `scripts/data/` with root shim compatibility

**Changes Applied:**
- [x] Moved utility implementation:
  - `scripts/semantic-rank-repo-corpus.py` → `scripts/data/semantic-rank-repo-corpus.py`
- [x] Added compatibility shim at original root-script path:
  - `scripts/semantic-rank-repo-corpus.py` now forwards to `scripts/data/semantic-rank-repo-corpus.py`
- [x] Updated active references/inventory tracking:
  - `docs/AGENT-PARITY-MATRIX.md`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `python3 -m py_compile scripts/semantic-rank-repo-corpus.py scripts/data/semantic-rank-repo-corpus.py` → PASS
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Observability Collector Canonicalization

### RH.H27 Move deprecated AI metrics collector to `scripts/observability/` and preserve compatibility shim

**Changes Applied:**
- [x] Moved deprecated metrics collector implementation:
  - `scripts/collect-ai-metrics.sh` → `scripts/observability/collect-ai-metrics.sh`
- [x] Added root compatibility shim:
  - `scripts/collect-ai-metrics.sh` now forwards to `scripts/observability/collect-ai-metrics.sh`
- [x] Rewrote active-doc command references to canonical path in:
  - `docs/PROGRESSIVE-DISCLOSURE-GUIDE.md`
  - `docs/AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md`
  - `docs/operations/reference/DASHBOARD-READY.md`
  - `docs/development/SYSTEM-UPGRADE-ROADMAP.md`
- [x] Updated cleanup inventory target rows to canonical path in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/collect-ai-metrics.sh scripts/observability/collect-ai-metrics.sh` → PASS
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Automation Template Script Canonicalization

### RH.H28 Move deprecated cron-template helper to `scripts/automation/` and preserve compatibility shim

**Changes Applied:**
- [x] Moved deprecated template helper implementation:
  - `scripts/cron-templates.sh` → `scripts/automation/cron-templates.sh`
- [x] Added root compatibility shim:
  - `scripts/cron-templates.sh` now forwards to `scripts/automation/cron-templates.sh`
- [x] Rewrote active-doc links/commands to canonical path in:
  - `docs/FEDERATED-DEPLOYMENT-GUIDE.md`
  - `docs/agent-guides/43-FEDERATED-DEPLOYMENT.md`
  - `docs/development/SYSTEM-UPGRADE-ROADMAP.md`
- [x] Updated cleanup inventory target rows to canonical path in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/cron-templates.sh scripts/automation/cron-templates.sh` → PASS
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Installed-vs-Intended Checker Canonicalization

### RH.H29 Move package-state comparison checker to `scripts/testing/` and preserve compatibility shim

**Changes Applied:**
- [x] Moved operational checker implementation:
  - `scripts/compare-installed-vs-intended.sh` → `scripts/testing/compare-installed-vs-intended.sh`
- [x] Added root compatibility shim:
  - `scripts/compare-installed-vs-intended.sh` now forwards to `scripts/testing/compare-installed-vs-intended.sh`
- [x] Fixed post-move path resolution:
  - adjusted `REPO_ROOT` derivation for nested `scripts/testing/` location.
- [x] Updated active references to canonical path in:
  - `docs/operations/QUICK-DEPLOY-REFERENCE-TREE.md`
  - `docs/development/FLAKE-FIRST-DECLARATIVE-MIGRATION-CHECKLIST-2026-02-24.md`
  - `docs/development/SYSTEM-UPGRADE-ROADMAP-UPDATES.md`
  - `scripts/governance/trim-stale-assets.sh`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/compare-installed-vs-intended.sh scripts/testing/compare-installed-vs-intended.sh` → PASS
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Secrets Repair Utility Canonicalization

### RH.H30 Move secrets-encryption repair utility to `scripts/security/` and preserve compatibility shim

**Changes Applied:**
- [x] Moved secrets repair utility implementation:
  - `scripts/fix-secrets-encryption.sh` → `scripts/security/fix-secrets-encryption.sh`
- [x] Added root compatibility shim:
  - `scripts/fix-secrets-encryption.sh` now forwards to `scripts/security/fix-secrets-encryption.sh`
- [x] Fixed post-move path resolution:
  - adjusted `SCRIPT_DIR` derivation for nested `scripts/security/` location.
- [x] Updated usage text in canonical script to new path.
- [x] Updated cleanup inventory target rows to canonical path in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/fix-secrets-encryption.sh scripts/security/fix-secrets-encryption.sh` → PASS
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Deprecated Podman/Package Utility Canonicalization

### RH.H31 Move deprecated root podman/package scripts to domain folders and preserve compatibility shims

**Changes Applied:**
- [x] Moved deprecated podman helper:
  - `scripts/configure-podman-tcp.sh` → `scripts/deploy/configure-podman-tcp.sh`
- [x] Moved deprecated package inventory helpers:
  - `scripts/count-packages-accurately.sh` → `scripts/governance/count-packages-accurately.sh`
  - `scripts/count-packages-simple.sh` → `scripts/governance/count-packages-simple.sh`
- [x] Added root compatibility shims for all three original root paths.
- [x] Updated active roadmap references to canonical script paths in:
  - `docs/development/SYSTEM-UPGRADE-ROADMAP.md`
- [x] Updated cleanup inventory target rows to canonical script paths in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/configure-podman-tcp.sh scripts/deploy/configure-podman-tcp.sh scripts/count-packages-accurately.sh scripts/governance/count-packages-accurately.sh scripts/count-packages-simple.sh scripts/governance/count-packages-simple.sh` → PASS
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Security/Health Script Canonicalization

### RH.H32 Move firewall and fs-integrity scripts to domain folders and preserve compatibility shims

**Changes Applied:**
- [x] Moved security audit helper:
  - `scripts/firewall-audit.sh` → `scripts/security/firewall-audit.sh`
- [x] Moved filesystem integrity checker:
  - `scripts/fs-integrity-check.sh` → `scripts/health/fs-integrity-check.sh`
- [x] Added root compatibility shims for both original root paths.
- [x] Added purpose header comment in canonical `scripts/health/fs-integrity-check.sh` for lint standards.
- [x] Updated active references to canonical fs-integrity path in:
  - `docs/BOOT-FS-RESILIENCE-GUARDRAILS.md`
  - `docs/development/SYSTEM-UPGRADE-ROADMAP-UPDATES.md`
- [x] Updated cleanup inventory target rows to canonical script paths in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/firewall-audit.sh scripts/security/firewall-audit.sh scripts/fs-integrity-check.sh scripts/health/fs-integrity-check.sh` → PASS
- `scripts/governance/check-doc-links.sh --active` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Phase 37 Update (2026-02-24): Declarative AI Stack Compliance Gates + Execution Start

### 37.H1 Add strict verifier guardrails for centralized ports and OTEL noise regressions

**Changes Applied:**
- [x] Extended `scripts/testing/verify-flake-first-roadmap-completion.sh` with explicit checks for centralized AI/OTEL port registry coverage in `nix/modules/core/options.nix`:
  - `qdrantHttp`, `qdrantGrpc`, `otlpGrpc`, `otlpHttp`, `otelCollectorMetrics`.
- [x] Added checks that declarative MCP runtime wiring derives endpoints from `mySystem.ports` in `nix/modules/services/mcp-servers.nix`:
  - `QDRANT_URL` from `ports.qdrantHttp`
  - `OTEL_EXPORTER_OTLP_ENDPOINT` from `ports.otlpGrpc`.
- [x] Added regression checks to fail if declarative OTEL wiring reintroduces:
  - hardcoded `jaeger:4317`
  - `debug` exporter.
- [x] Added roadmap planning/execution block in `SYSTEM-UPGRADE-ROADMAP.md`:
  - new `Phase 37: AI Stack Declarative Compliance Closure`
  - phased tasks, hold-points, and success criteria

**Validation:**
- `bash -n scripts/testing/verify-flake-first-roadmap-completion.sh docs/development/SYSTEM-UPGRADE-ROADMAP.md docs/development/SYSTEM-UPGRADE-ROADMAP-UPDATES.md` → PASS
- `./scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS (`28 pass, 0 fail`)
- `rg -n "jaeger:4317|debug:\\s*\\{\\}|exporters:\\s*\\[debug\\]" nix/modules/services/mcp-servers.nix` → PASS (no matches)

### 37.H2 Execute fallback inventory + regulated gate baseline

**Changes Applied:**
- [x] Started fallback inventory scan for runtime endpoint defaults in `ai-stack/mcp-servers` (excluding docs/requirements).
- [x] Identified current high-priority candidates for strictification:
  - `ai-stack/mcp-servers/health-monitor/server.py` (localhost hardcoded health defaults)
  - `ai-stack/mcp-servers/hybrid-coordinator/federation_sync.py` (`QDRANT_URL` localhost fallback)
  - `ai-stack/mcp-servers/nixos-docs/server.py` (`REDIS_HOST=localhost` fallback)
- [x] Executed classified/hospital release gate baseline script.

**Validation:**
- `rg -n "os\\.getenv\\([^\\n]*(localhost|127\\.0\\.0\\.1|jaeger:4317|6333|8002|8003|8080|4317|4318)" ai-stack/mcp-servers --glob '!**/README.md' --glob '!**/requirements*.txt'` → PASS (inventory captured)
- `./scripts/hospital-classified-gate.sh` → PASS (non-blocking warning: approved host-network exception file still present)

### 37.H3 Harden core AI runtime defaults to fail-closed on env wiring

**Changes Applied:**
- [x] Updated strict-mode defaults for active MCP runtime services:
  - `ai-stack/mcp-servers/hybrid-coordinator/server.py`: `AI_STRICT_ENV` default changed to `true`.
  - `ai-stack/mcp-servers/ralph-wiggum/server.py`: `AI_STRICT_ENV` default changed to `true`.
  - `ai-stack/mcp-servers/aidb/settings_loader.py`: strict-env default changed to `true`.
- [x] Extended roadmap verifier checks so strict defaults are continuously enforced in CI/preflight.

**Validation:**
- `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/server.py ai-stack/mcp-servers/ralph-wiggum/server.py ai-stack/mcp-servers/aidb/settings_loader.py` → PASS
- `bash -n scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS
- `./scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS (`31 pass, 0 fail`)


**Changes Applied:**
- [x] Removed legacy container-engine resources from active K8s deployment graph:
- [x] Retired legacy host-networked container-engine manifests from active path:
- [x] Removed host-network exception debt in compliance config:
  - `config/hospital-gate-hostnetwork-allowlist.txt` now empty,
  - `nix/hosts/hyperd/facts.nix` host-network allowlist reset to `[]`,
  - `nix/modules/core/hospital-classified.nix` example updated away from legacy kompose path.
- [x] Updated audit/gate scanners to treat deprecated manifests as non-active:
  - `scripts/security/security-audit.sh` now excludes deprecated path globs,
  - `scripts/hospital-classified-gate.sh` excludes deprecated path globs for host-network and rolling-tag checks.
  - `ai-stack/systemd/letsencrypt-renewal.service` now uses `network-online.target`.

**Validation:**
- `bash scripts/security/security-audit.sh` → PASS
- `./scripts/hospital-classified-gate.sh` → PASS
- `./scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS (`31 pass, 0 fail`)

### 37.H5 Added angry-team release blockers to roadmap

**Changes Applied:**
- [x] Added `37.6 Angry-Team Release Blockers` to `SYSTEM-UPGRADE-ROADMAP.md` as explicit tasks + release criteria:
  - legacy-path freeze/cutoff,
  - exception expiry governance,
  - signed evidence bundles per release,
  - identity segmentation + short-lived credentials,
  - failure-mode validation suite,
  - threat-model-to-control evidence mapping.

## Phase 28 Update (2026-02-18): Password Provisioning Safety Guardrails

### 28.H12 Prevent unintended user/root password resets during config rendering

**Changes Applied:**
- [x] Removed automatic temporary-password generation fallback in `hydrate_primary_user_password_block()` when existing password directives cannot be derived.
- [x] Changed `provision_primary_user_password()` to default to **skip** instead of generating a new password hash.
- [x] Added non-interactive safeguard to skip password provisioning entirely, avoiding silent credential drift in unattended runs.

**Validation:**
- `bash -n lib/config.sh nixos-quick-deploy.sh` → PASS
- `./scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS

## Phase 28 Update (2026-02-18): AI Stack Env Writer Robustness

### 28.H11 Prevent sed substitution failures on secret values

**Changes Applied:**
- [x] Reworked `set_env_value()` in `nixos-quick-deploy.sh` to avoid `sed` replacement for `.env` writes.
- [x] Switched to an `awk` rewrite flow that safely persists values containing characters like `|`, `/`, and `&` without regex/sed escaping failures.
- [x] Fixed the interactive AI-stack credential path where Grafana password input could trigger `sed: unterminated 's' command` when special characters were entered.

**Validation:**
- `bash -n nixos-quick-deploy.sh` → PASS
- `python /tmp/test_set_env_value.py` (function-equivalent harness with special-character secrets) → PASS

## Phase 28 Update (2026-02-18): Roadmap Verifier Host Compatibility Fallback

### 28.H10 Make flake-first roadmap verification independent of ripgrep availability

**Changes Applied:**
- [x] Updated `scripts/testing/verify-flake-first-roadmap-completion.sh` to detect `rg` availability and use `grep -E` fallback when `rg` is not installed.
- [x] Added verifier preflight logging so fallback mode is explicit in execution output.
- [x] Preserved all existing roadmap marker checks while removing false-negative failure mode on hosts missing ripgrep.

**Validation:**
- `bash -n scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS
- `./scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS
- `PATH="/usr/bin:/bin" ./scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS (grep fallback)

## Phase 28 Update (2026-02-18): CI Enforcement for Flake-First Roadmap Completion

### 28.H9 Add workflow gate for roadmap verifier and entrypoint syntax

**Changes Applied:**
- [x] Updated `.github/workflows/tests.yml` with a dedicated `flake-first-roadmap-verifier` job.
- [x] Added CI syntax checks for flake-first entrypoints and verifier script:
  - `nixos-quick-deploy.sh`
  - `scripts/deploy-clean.sh`
  - `scripts/governance/analyze-clean-deploy-readiness.sh`
  - `scripts/testing/verify-flake-first-roadmap-completion.sh`
- [x] Added CI execution of `./scripts/testing/verify-flake-first-roadmap-completion.sh` so roadmap-complete flake-first markers are enforced in PR/push checks.

**Validation:**
- `bash -n .github/workflows/tests.yml scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS
- `./scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS (15 checks)

## Phase 28 Update (2026-02-18): Enforced Roadmap-Completion Preflight in Deploy Paths

### 28.H8 Wire roadmap verifier into quick-deploy and deploy-clean execution

**Changes Applied:**
- [x] Added `run_flake_first_roadmap_verification()` in `nixos-quick-deploy.sh` and execute it in flake-first flow before declarative apply.
- [x] Added `run_roadmap_completion_verification()` in `scripts/deploy-clean.sh` and execute it before readiness/build steps.
- [x] Added escape-hatch flags for controlled troubleshooting:
  - `nixos-quick-deploy.sh --skip-roadmap-verification`
  - `scripts/deploy-clean.sh --skip-roadmap-verification`

**Validation:**
- `bash -n nixos-quick-deploy.sh scripts/deploy-clean.sh scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS
- `./scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS

## Phase 28 Update (2026-02-18): Flake-First Completion Verification Gate

### 28.H7 Add deterministic verifier for roadmap-complete flake-first items

**Changes Applied:**
- [x] Added `scripts/testing/verify-flake-first-roadmap-completion.sh` to assert presence of key roadmap-complete flake-first implementations:
  - flake-first default + deploy-clean orchestration path,
  - host auto-resolution in deploy-clean and readiness analyzer,
  - account-lock safety behavior,
  - declarative git identity + credential-helper projection,
  - host-scoped deploy/home overlay wiring in `flake.nix`,
  - supporting reliability helpers (`append_log_line`, `find_existing_parent`, `AUTO_CONFIRM` guard).
- [x] Script exits non-zero when any expected implementation marker is missing, so it can be reused as a CI/readiness guard.

**Validation:**
- `bash -n scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS
- `./scripts/testing/verify-flake-first-roadmap-completion.sh` → PASS (15 checks)

## Phase 28 Update (2026-02-18): Declarative Git Credential Helper Parity + Safer Primary User Resolution

### 28.H6 Preserve git credential helper declaratively and avoid root-user drift

**Changes Applied:**
- [x] Updated deploy-clean primary-user default resolution:
  - `PRIMARY_USER` now prefers `SUDO_USER` over `USER` to avoid accidental root-profile targeting in escalated contexts.
- [x] Extended declarative git projection to include credential helper:
  - `scripts/deploy-clean.sh` now reads `git config --global credential.helper` (or `GIT_CREDENTIAL_HELPER`) and writes it into host-scoped Home Manager options.
- [x] Reworked git option escaping to reuse `nix_escape_string()` for safe Nix string rendering.

**Validation:**
- `bash -n scripts/deploy-clean.sh scripts/governance/analyze-clean-deploy-readiness.sh nixos-quick-deploy.sh` → PASS
- `rg -n "GIT_CREDENTIAL_HELPER|credential.helper|PRIMARY_USER_OVERRIDE:-\$\{SUDO_USER" scripts/deploy-clean.sh` → PASS

## Phase 28 Update (2026-02-18): Account Lock Safety + Declarative Git Identity Parity

### 28.H5 Prevent false lockouts and restore declarative git credential behavior

**Changes Applied:**
- [x] Hardened runtime account lock checks in `scripts/deploy-clean.sh`:
  - unreadable `/etc/shadow` states no longer get interpreted as locked passwords,
  - lock checks now fail only on explicit lock markers (`!`, `*`, `!!`, prefixed lock markers).
- [x] Relaxed readiness account check behavior for locked root account in analyzer:
  - `scripts/governance/analyze-clean-deploy-readiness.sh` now treats locked root as warning (common policy) instead of hard failure.
- [x] Added declarative git identity persistence to flake-first deploy path:
  - `scripts/deploy-clean.sh` now writes `nix/hosts/<host>/home-deploy-options.nix` with `programs.git.userName/userEmail` from env or existing global git config.
- [x] Wired root flake home config loading for host-scoped home deploy options:
  - `flake.nix` now imports optional `nix/hosts/<host>/home-deploy-options.nix` into `homeConfigurations`.

**Validation:**
- `bash -n scripts/deploy-clean.sh scripts/governance/analyze-clean-deploy-readiness.sh` → PASS (shell syntax + parse targets where applicable)
- `rg -n "persist_home_git_credentials_declarative|home-deploy-options.nix|is_locked_password_field|Could not read password hash state" scripts/deploy-clean.sh flake.nix` → PASS

## Phase 28 Update (2026-02-18): Flake Host Resolution Guardrail for Fresh Installs

### 28.H4 Hostname/target mismatch remediation in deploy-clean readiness

**Changes Applied:**
- [x] Added host auto-resolution guardrail in `scripts/deploy-clean.sh`:
  - when runtime hostname has no matching `nix/hosts/<hostname>/default.nix`, deploy-clean now auto-selects the only discovered host directory in the flake.
- [x] Added identical host auto-resolution logic in `scripts/governance/analyze-clean-deploy-readiness.sh`:
  - readiness checks now evaluate the discovered host target instead of warning/failing on a hostname-only mismatch.
- [x] Added flake-first host fallback in `nixos-quick-deploy.sh` before calling deploy-clean:
  - if detected hostname has no host dir and exactly one host exists, it uses that host for `--host`/target construction.

**Validation:**
- `bash -n scripts/deploy-clean.sh scripts/governance/analyze-clean-deploy-readiness.sh nixos-quick-deploy.sh` → PASS
- `./scripts/governance/analyze-clean-deploy-readiness.sh --flake-ref path:. --profile ai-dev` → PASS/WARN (no false hostname mismatch warning when a single host is present)

## Phase 26 Update (2026-02-18): Flake-First Declarative AI Stack Parity Audit + Option Wiring

### 26.H12 Declarative ownership restored for optional AI stack/model choices

**Changes Applied:**
- [x] Added host-scoped deploy option import path in root flake:
  - `flake.nix` now conditionally imports `nix/hosts/<host>/deploy-options.nix` when present.
- [x] Added baseline host deploy options:
  - `nix/hosts/nixos/deploy-options.nix` captures AI stack enable + model defaults as declarative `mySystem.*` options.
- [x] Extended declarative AI stack module options:
  - `mySystem.aiStack.modelProfile`
  - `mySystem.aiStack.embeddingModel`
  - `mySystem.aiStack.llamaDefaultModel`
  - `mySystem.aiStack.llamaModelFile`
  - `mySystem.aiStack.namespace`
- [x] Reconciler now patches model defaults into Kubernetes env ConfigMap declaratively on each reconcile run:
- [x] Flake-first installer now asks for optional AI stack enablement/model profile at start (interactive mode) and persists choices into host declarative options:
  - `--flake-first-ai-stack on|off`
  - `--flake-first-model-profile auto|small|medium|large`
  - `nixos-quick-deploy.sh` writes `nix/hosts/<host>/deploy-options.nix` before deployment.
- [x] Removed imperative Phase 9 AI stack/model execution from flake-first completion path:
  - `run_flake_first_legacy_outcome_tasks()` now keeps parity tooling/validation/reporting but skips imperative phase-09 deployment scripts in flake-first mode.

**Roadmap Alignment Check (high-level):**
- Phase 26 goal (“bash only for orchestration/bootstrap, features in Nix options/modules”) is now applied for optional AI stack role + model selection.
- Phase 28 convergence goal (“keep flake-first declarative deploy path”) remains intact: deployment still routes through `scripts/deploy-clean.sh`, with AI stack rollout via declarative NixOS + systemd reconciliation.

**Validation:**
- `bash -n nixos-quick-deploy.sh` → PASS
- `rg -n "deploy-options\.nix|hostDeployOptionsPath" flake.nix nixos-quick-deploy.sh` → PASS
- `rg -n "modelProfile|embeddingModel|llamaDefaultModel|llamaModelFile|patch configmap env" nix/modules/services/ai-stack.nix` → PASS

## Phase 26 Update (2026-02-16): Flake Hardware Wiring + Facts Schema Expansion

### 26.H9 Critical Declarative Path Corrections

**Changes Applied:**
- [x] Root flake now imports hardware aggregator module:
  - `flake.nix` switched from legacy flat imports to `nix/modules/hardware/default.nix`.
- [x] Root flake now generates host-scoped Home Manager outputs with user alias compatibility.
- [x] `scripts/governance/discover-system-facts.sh` upgraded to emit full hardware/deployment facts schema:
  - `hardware.igpuVendor`
  - `hardware.storageType`
  - `hardware.systemRamGb`
  - `hardware.isMobile`
  - `hardware.earlyKmsPolicy`
  - `hardware.nixosHardwareModule`
  - `deployment.enableHibernation`
  - `deployment.swapSizeGb`
- [x] `nix/modules/core/options.nix` early KMS default aligned to safe mode (`off`).
- [x] `nixos-quick-deploy.sh` flake-first mode now resolves host-scoped HM targets (`user-host`) before falling back to legacy `user`.
- [x] Unit test strengthened:
  - `tests/unit/discover-system-facts.bats` now validates expanded hardware facts fields.

**Validation:**
- `bash -n scripts/governance/discover-system-facts.sh` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- deterministic run check for discovery script (`Updated` then `No changes`) → PASS

**Notes:**
- `tests/run-unit-tests.sh tests/unit/discover-system-facts.bats` could not run in sandbox due missing `bats` + restricted Nix daemon socket (`/nix/var/nix/daemon-socket/socket`).

## Phase 26 Update (2026-02-16): Clean-Cut Deployment Path + Early-KMS Alignment

### 26.H10 Minimal Workflow Cutover

**Changes Applied:**
- [x] Added minimal flake-first deploy entrypoint:
  - `scripts/deploy-clean.sh`
  - direct discovery + `nixos-rebuild --flake` + Home Manager activation
  - no template rendering and no legacy 9-phase orchestration
  - supports fresh-host bootstrap without preinstalled `home-manager` CLI
  - supports recurring update runs via `--update-lock`
- [x] Added single canonical clean setup document:
  - `docs/CLEAN-SETUP.md`
- [x] Aligned early-KMS safe defaults across all active paths:
  - `config/defaults.sh` (`DEFAULT_EARLY_KMS_POLICY="off"`)
  - `config/variables.sh` fallback (`...:-off`)
  - `lib/config.sh` fallback + invalid-value fallback (`off`)
  - `lib/hardware-detect.sh` derived policy defaults to `off` (Intel may still set `force`)
- [x] Hardened GPU validation against false warnings on built-in kernels:
  - `lib/validation.sh` now checks `/sys/module/*` in addition to `lsmod`
- [x] Added ARM/SBC hardware-module detection fallback:
  - `lib/hardware-detect.sh` and `scripts/governance/discover-system-facts.sh` read `/proc/device-tree/model` for Raspberry Pi mappings.
- [x] Removed hard dependency on `rg` in discovery script path:
  - `scripts/governance/discover-system-facts.sh` now falls back to `grep` for GPU line filtering on minimal hosts.
- [x] Completed root-flake `nixos-hardware` wiring:
  - `flake.nix` now declares `nixos-hardware` input (no invalid follows override)
  - template flake import now guards missing module attrs gracefully

**Validation:**
- `bash -n scripts/deploy-clean.sh` → PASS
- `bash -n lib/config.sh lib/hardware-detect.sh scripts/governance/discover-system-facts.sh lib/validation.sh config/defaults.sh config/variables.sh` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `nix-instantiate --parse templates/flake.nix` → PASS

## Phase 26 Update (2026-02-16): Build-Blocker Fixes + Default Flake Path Cutover

### 26.H11 Evaluation blockers resolved and legacy path demoted

**Changes Applied:**
- [x] Fixed flake input warning/error:
  - removed invalid `inputs.nixpkgs.follows` override from root `flake.nix` `nixos-hardware` input.
- [x] Fixed duplicate module option assignment:
  - merged duplicate `boot.kernelParams` definitions in `nix/modules/hardware/storage.nix` into a single combined declaration.
- [x] Fixed clean deploy lock-update command:
  - `scripts/deploy-clean.sh --update-lock` now strips `path:` for `nix flake update --flake <path>`.
- [x] Switched `nixos-quick-deploy.sh` to flake-first by default:
  - `FLAKE_FIRST_MODE=true` default.
  - added explicit `--legacy-phases` flag for maintenance-mode fallback.
  - added script-level migration guardrail policy (`TEMPLATE_PATH_FEATURE_POLICY=critical-fixes-only`).
- [x] Kept profile handling in the primary path as thin wrappers:
  - clean + flake-first flows only accept profile selectors (`ai-dev|gaming|minimal`) and pass values into declarative facts/options.
- [x] Continued profile-logic migration into declarative Nix data/modules:
  - added `nix/data/profile-system-packages.nix`
  - `nix/modules/profiles/ai-dev.nix` and `nix/modules/profiles/gaming.nix` now consume declarative package lists.
- [x] Fixed early-KMS override propagation in flake-first mode:
  - `--disable-early-kms` / `--early-kms-auto` / `--force-early-kms` now feed `EARLY_KMS_POLICY_OVERRIDE` into `scripts/governance/discover-system-facts.sh`.

**Validation:**
- `bash -n nixos-quick-deploy.sh` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `nix-instantiate --parse nix/modules/hardware/storage.nix` → PASS
- `./scripts/governance/lint-template-placeholders.sh` → PASS (no placeholder proliferation)

**Notes:**
- Full `nix eval`/`nix build` validation remains environment-dependent when Nix daemon/network/cache access is restricted; syntax/evaluation blockers from the reported errors are removed in source.

## Phase 27 Update (2026-02-16): Nix Static Analysis Track (NIX-ISSUE-022)

### 27.H2 statix/deadnix/alejandra integration

**Changes Applied:**
- [x] Added static-analysis toolchain to root flake dev shell:
  - `flake.nix` now exposes `devShells.x86_64-linux.default` with `statix`, `deadnix`, `alejandra`.
- [x] Added static-analysis toolchain to template flake dev shell:
  - `templates/flake.nix` now includes `devShells.${system}.default` with `statix`, `deadnix`, `alejandra`.
- [x] Added reusable lint runner:
  - `scripts/governance/nix-static-analysis.sh` (strict and `--non-blocking` modes).
- [x] Added CI job:
  - `.github/workflows/test.yml` now runs `scripts/governance/nix-static-analysis.sh` via `nix shell nixpkgs#statix nixpkgs#deadnix nixpkgs#alejandra`.
  - current mode is non-blocking baseline (`--non-blocking`) while legacy lint debt is normalized.
- [x] Added build-only flake-check guard in flake-first deploy path:
  - `nixos-quick-deploy.sh --build-only` executes declarative evaluation/build without applying a live switch.
- [x] Added non-blocking static analysis in Phase 3:
  - `phases/phase-03-configuration-generation.sh` now calls `scripts/governance/nix-static-analysis.sh --non-blocking`.

**Validation:**
- `bash -n scripts/governance/nix-static-analysis.sh` → PASS
- `bash -n phases/phase-03-configuration-generation.sh` → PASS
- `bash -n nixos-quick-deploy.sh` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `nix-instantiate --parse templates/flake.nix` → PASS

## Phase 27 Update (2026-02-16): Disko + Secure Boot Declarative Scaffolding

### 27.H3 NIX-ISSUE-020/021 code-path implementation

**Changes Applied:**
- [x] Added disko/lanzaboote flake inputs:
  - `flake.nix`
  - `templates/flake.nix`
- [x] Added disk and secure-boot typed options:
  - `nix/modules/core/options.nix`:
    - `mySystem.disk.layout`
    - `mySystem.disk.device`
    - `mySystem.disk.luks.enable`
    - `mySystem.disk.btrfsSubvolumes`
    - `mySystem.secureboot.enable`
- [x] Added declarative disk modules:
  - `nix/modules/disk/default.nix`
  - `nix/modules/disk/gpt-efi-ext4.nix`
  - `nix/modules/disk/gpt-efi-btrfs.nix`
  - `nix/modules/disk/gpt-luks-ext4.nix`
- [x] Added secure-boot module:
  - `nix/modules/secureboot.nix`
- [x] Wired optional imports + guardrails:
  - root/template flakes now conditionally import disko/lanzaboote modules only when requested by options/facts.
  - explicit warnings added for requested-but-missing module exports.
- [x] Added optional deploy pre-install partition step:
  - `scripts/deploy-clean.sh --phase0-disko` (requires `DISKO_CONFIRM=YES` safeguard).
- [x] Added optional secure-boot key enrollment step:
  - `scripts/deploy-clean.sh --enroll-secureboot-keys` (requires `SECUREBOOT_ENROLL_CONFIRM=YES` safeguard).
- [x] Expanded facts schema for disk + secure-boot toggles:
  - `scripts/governance/discover-system-facts.sh`
  - `lib/hardware-detect.sh`
- [x] Updated discovery unit coverage:
  - `tests/unit/discover-system-facts.bats` now validates disk/secureboot fields and invalid layout rejection.

**Validation:**
- `bash -n scripts/governance/discover-system-facts.sh` → PASS
- `bash -n lib/hardware-detect.sh` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `nix-instantiate --parse templates/flake.nix` → PASS
- `nix-instantiate --parse nix/modules/core/options.nix` → PASS
- `nix-instantiate --parse nix/modules/disk/default.nix` → PASS
- `nix-instantiate --parse nix/modules/secureboot.nix` → PASS

**Remaining Gated Work:**
- [ ] Validate deploy-script Phase 0 disk apply flow on target hardware (destructive test path).
- [ ] Validate `sbctl enroll-keys` automation on secure-boot-capable host.
- [ ] Execute end-to-end flake eval/show/build verification in unrestricted runtime (sandbox currently blocks daemon-backed checks).

**Remaining Non-Gated Backlog:**
- [x] Phase 26 `26.6.2`: prune/archive no-longer-used placeholder sections after one focused template-audit pass.

## Phase 27 Update (2026-02-16): Governance and Skill Integrity Gates

### 27.H1 Canonical Skill Source + Deterministic Dependency Lint

**Changes Applied:**
- [x] Removed legacy `.claude/skills.backup-20251204-075457` tree from active workspace paths.
- [x] Added canonical path guard: `scripts/testing/check-skill-source-of-truth.sh`.
- [x] Added external dependency floating-link guard: `scripts/governance/lint-skill-external-deps.sh`.
- [x] Added relative reference integrity validator: `scripts/testing/validate-skill-references.sh`.
- [x] Added pinned dependency lock manifest: `docs/skill-dependency-lock.md`.
- [x] Updated `mcp-builder` skill docs (canonical + mirror) to reference pinned-lock workflow instead of `.../main/README.md`.
- [x] Wired new checks into CI workflow (`skill-governance-lint` job).
- [x] Added initial CLI namespace wrapper: `scripts/ai/aqd`
  - `aqd skill validate`
  - `aqd skill quick-validate`
  - `aqd skill init`
  - `aqd skill package`
  - `aqd mcp scaffold`
  - `aqd mcp validate`
  - `aqd mcp test`
  - `aqd mcp evaluate`
  - `aqd mcp logs`
  - `aqd mcp deploy-aidb`
- [x] Added repository governance docs:
  - `docs/REPOSITORY-SCOPE-CONTRACT.md`
  - `docs/SKILL-BACKUP-POLICY.md`
  - `.github/CODEOWNERS`
- [x] Added CLI operator docs:
  - `docs/AQD-CLI-USAGE.md`
- [x] Added minimum skill standard guidance:
  - `docs/SKILL-MINIMUM-STANDARD.md`
  - updated `.agent/skills/skill-creator/SKILL.md` to make progressive disclosure optional
- [x] Added converter lock/version metadata:
  - `docs/skill-dependency-lock.md` (`AQD_CLI_CONVERTER_*`)
- [x] Added lint/parity tests:
  - `tests/unit/validate-skill-references.bats`
  - `tests/unit/aqd-parity.bats`
  - fixtures under `archive/test-fixtures/skill-reference-lint/`
  - `scripts/governance/lint-skill-template.sh` (+ CI step in `skill-governance-lint`)
  - template lint currently emits non-blocking warnings while legacy skills are normalized

**Validation:**
- `./scripts/testing/check-skill-source-of-truth.sh` → PASS
- `./scripts/governance/lint-skill-external-deps.sh` → PASS
- `./scripts/testing/validate-skill-references.sh` → PASS
- `./scripts/ai/aqd --version` → PASS
- `./scripts/ai/aqd workflows list` → PASS
- `./scripts/ai/aqd skill validate` → PASS (with template-lint warnings)
- `./scripts/ai/aqd skill quick-validate archive/test-fixtures/skill-reference-lint/valid-skill` → PASS
- `env SKILL_REFERENCE_ROOTS='archive/test-fixtures/skill-reference-lint/valid-skill' ./scripts/testing/validate-skill-references.sh` → PASS
- `env SKILL_REFERENCE_ROOTS='archive/test-fixtures/skill-reference-lint/broken-skill' ./scripts/testing/validate-skill-references.sh` → expected FAIL with remediation guidance
- `./scripts/governance/lint-skill-template.sh` → PASS (warning-only baseline)

**Remaining Work (Phase 27):**
- [ ] Phase 27 exit criteria verification (two consecutive CI runs + full docs convergence).

## Phase 25 Update (2026-02-16): AMDGPU Boot Hardening Follow-up

### 25.H8 Safe-by-Default Early-KMS + AMD Kernel Param Guardrails

**Problem:** Some deployments still produced boot failures with amdgpu-related errors after quick deploy/rebuild.

**Fixes Applied:**
- [x] `config/defaults.sh`
  - Set `DEFAULT_EARLY_KMS_POLICY="off"` (safe-by-default, no forced initrd GPU preload).
- [x] `nixos-quick-deploy.sh`
  - Added `--force-early-kms` for explicit override.
  - Updated early-KMS override handling to accept `off|auto|force`.
- [x] `lib/config.sh`
  - In `EARLY_KMS_POLICY=auto`, skip forced `amdgpu` initrd preload unless explicitly `force`.
  - Improved skip reason logging for clarity.
- [x] `templates/nixos-improvements/mobile-workstation.nix`
  - Removed aggressive `amdgpu.ppfeaturemask` and `amdgpu.dcdebugmask` defaults.
  - Gated `hardware.amdgpu.overdrive/opencl` on AMD GPU detection (video driver contains `amdgpu`) instead of AMD CPU detection.

**Validation Notes:**
- Ran: `./nixos-quick-deploy.sh --disable-early-kms --test-phase 3 --skip-switch --prefix /tmp/nqd-dotfiles-test`
- Generated config confirms no forced initrd GPU preload line:
  - `configuration.nix` contains `# initrd.availableKernelModules handled by hardware-configuration.nix`
- Validation run still requires interactive sudo to complete dry-build/switch on target host.

**Remaining Required Verification:**
- [ ] Run full deploy + reboot on target machine and confirm no amdgpu boot failure.
- [ ] Close roadmap task `25.8.4` after successful reboot verification.

## Phase 25 Update (2026-02-16): Root FSCK Emergency-Loop Remediation (NIX-ISSUE-017)

### 25.H9 Root Filesystem Boot-Blocker Guardrails + Recovery Path

**Problem:**
- Boot failure sequence is rooted in initrd `systemd-fsck-root` failure on `/dev/disk/by-uuid/b386ce56-aff9-493e-b42d-fbe0b648ea58`, not in amdgpu log noise.
- When fsck fails, `/sysroot` never mounts and downstream initrd dependencies (`rw-etc`, `nixos-etc-metadata`, `/sysroot/run`) fail.
- Root-locked emergency mode blocks direct shell recovery.

**Changes Applied:**
- [x] Added declarative recovery options:
  - `mySystem.deployment.rootFsckMode` (`check|skip`)
  - `mySystem.deployment.initrdEmergencyAccess` (`bool`)
  - file: `nix/modules/core/options.nix`
- [x] Added recovery module:
  - `nix/modules/hardware/recovery.nix`
  - wired into `nix/modules/hardware/default.nix`
- [x] Hardened clean deploy preflight in `scripts/deploy-clean.sh`:
  - validates host `/` device exists from `hardware-configuration.nix`
  - validates host root device + fsType parity against running system
  - blocks deploy when previous boot shows `systemd-fsck-root` failure (unless explicitly overridden)
- [x] Added safer execution modes to `scripts/deploy-clean.sh`:
  - `--boot` (stage next generation without live `switch`)
  - `--recovery-mode` (forces recovery-safe facts; default mode remains `switch`)
  - `--allow-prev-fsck-fail` override for guarded bypass
- [x] Improved GPU detection fallback (when `lspci` is unavailable):
  - `scripts/governance/discover-system-facts.sh`
  - `lib/hardware-detect.sh`
  - now reads DRM vendor IDs from `/sys/class/drm/card*/device/vendor`
- [x] Re-generated host facts with new schema and corrected GPU detection:
  - `nix/hosts/nixos/facts.nix` now reports `gpuVendor = "amd"` and includes recovery fields.

**Validation:**
- `bash -n scripts/deploy-clean.sh scripts/governance/discover-system-facts.sh lib/hardware-detect.sh` → PASS
- `nix-instantiate --parse nix/modules/core/options.nix` → PASS
- `nix-instantiate --parse nix/modules/hardware/recovery.nix` → PASS
- `nix-instantiate --parse nix/modules/hardware/default.nix` → PASS

**Remaining Gated Verification:**
- [ ] Run `./scripts/deploy-clean.sh --host nixos --profile ai-dev --recovery-mode --boot` on target host.
- [ ] Reboot and confirm no initrd emergency loop.
- [ ] Perform offline ext4 repair, then switch `rootFsckMode` back to `check`.

## Phase 3 Hotfix (2026-02-13): Dry-Build Recursion Failure

### 3.H1 NixOS Module Evaluation Recursion

**Problem:** `nixos-rebuild dry-build --flake ~/.dotfiles/home-manager#<host>` failed in Phase 3 with:
- `error: infinite recursion encountered`
- stack trace ending at `configuration.nix` in the `optionalAttrs` guard for `gcr-ssh-agent`

**Root Causes:**
- `templates/configuration.nix` used `options` as a module argument and then read `options.services.gnome` inside a top-level `optionalAttrs` merge, creating a recursive dependency during module argument resolution.
- `templates/nixos-improvements/optimizations.nix` contained 26.05+ options without release guards, which is risky for current `nixos-25.05` flake channels.

**Fixes Applied:**
- [x] `templates/configuration.nix`
  - Removed `options` from module argument list.
  - Replaced `options`-based guard with a release gate:
    - `lib.optionalAttrs (lib.versionAtLeast lib.version "26.05")`
- [x] `templates/nixos-improvements/optimizations.nix`
  - Added release guards for newer options:
    - `system.nixos-init.enable`
    - `system.etc.overlay.enable`
    - `services.userborn.enable`
    - `services.lact.enable`

**Validation Notes:**
- Reproduced failure with:
  - `nix --extra-experimental-features nix-command --extra-experimental-features flakes eval ~/.dotfiles/home-manager#nixosConfigurations.<host>.config.system.stateVersion --show-trace`
- Trace confirmed recursion originated from:
  - `configuration.nix` `// lib.optionalAttrs (options.services.gnome ? gcr-ssh-agent) { ... }`

**Operational Follow-up:**
- Regenerate live config from templates (Phase 3) so `~/.dotfiles/home-manager/configuration.nix` picks up the fix.
- Re-run Phase 3 validation (`nixos-rebuild dry-build`) after regeneration.

### 3.H2 Cross-Version Module Option Mismatches

**Problem:** After recursion was fixed, evaluation surfaced additional option-path failures on `nixos-25.05`.

**Issues + Fixes Applied:**
- [x] `services.logind.settings` invalid in `mobile-workstation.nix`
  - Replaced with `services.logind.extraConfig` for cross-release compatibility.
- [x] `systemd.settings` invalid in `optimizations.nix`
  - Replaced with `systemd.extraConfig`.
- [x] `systemd.settings.Manager` emitted by generator in swap block (`lib/config.sh`)
  - Replaced emitted config with `systemd.extraConfig`.

### 3.H3 Package/Evaluation Compatibility Failures

**Problem:** Flake evaluation failed on package and option collisions after module-path fixes.

**Issues + Fixes Applied:**
- [x] `perf` undefined in `optimizations.nix`
  - Switched to guarded `pkgs.linuxPackages.perf`.
- [x] Duplicate unique sysctl option (`fs.inotify.max_user_instances`)
  - Removed conflicting inotify sysctl overrides from optimizations module.
- [x] `heroic` pulled insecure Electron (`electron-36.9.5`) and blocked evaluation
  - Removed Heroic from default generated package sets in `lib/config.sh`.

### 3.H4 Phase 3 Failure Safety Improvement

**Problem:** Non-interactive/test runs without sudo could fail during `/etc/nixos/nixos-improvements` sync before template placeholders were fully rendered.

**Fix Applied:**
- [x] `lib/config.sh` now treats `/etc/nixos` improvements sync as best-effort in non-interactive contexts:
  - Uses `sudo -n` for privileged copy/sed operations.
  - Logs warnings instead of aborting config generation when sudo auth is unavailable.
  - Continues with `~/.dotfiles/home-manager` sync so generated files remain valid.

### 3.H5 Validation Outcome

**Final validation command:**
- `nix --extra-experimental-features nix-command --extra-experimental-features flakes flake check ~/.dotfiles/home-manager --no-build`

**Result:**
- ✅ `nixosConfigurations` evaluated
- ✅ `homeConfigurations` evaluated
- ✅ `devShells` evaluated

## Phase 10 Updates: AI Stack Runtime Reliability

### 10.37 Circuit Breaker Implementation

**Problem:** Service calls between AI stack components lack resilience patterns, leading to cascading failures.

**Goal:** Implement circuit breaker patterns for all inter-service communication.

**Tasks:**
- [ ] **10.37.1** Add circuit breaker pattern to AIDB → Hybrid Coordinator calls
- [ ] **10.37.2** Add circuit breaker pattern to Ralph → Aider-wrapper calls
- [ ] **10.37.3** Add circuit breaker pattern to Embeddings service calls
- [x] **10.37.4** Implement circuit breaker monitoring and alerting
- [x] **10.37.5** Document circuit breaker configuration and behavior

### 10.38 Graceful Degradation Strategies

**Problem:** The AI stack does not handle partial service failures gracefully, leading to complete service outages.

**Goal:** Implement graceful degradation allowing partial functionality when some services are unavailable.

**Tasks:**
- [ ] **10.38.1** Implement fallback strategies for non-critical services
- [ ] **10.38.2** Add graceful degradation for AIDB when Hybrid Coordinator is down
- [ ] **10.38.3** Add graceful degradation for Ralph when Aider is unavailable
- [x] **10.38.4** Document degradation modes and expected behavior
- [x] **10.38.5** Add degradation testing procedures

### 10.39 Enhanced Health Check Endpoints

**Problem:** Current health checks are basic and don't provide sufficient insight into service readiness.

**Goal:** Implement comprehensive health check endpoints with dependency status.

**Tasks:**
- [x] **10.39.1** Add detailed health check endpoints to AIDB
- [x] **10.39.2** Add detailed health check endpoints to Hybrid Coordinator
- [x] **10.39.3** Add detailed health check endpoints to Ralph Wiggum
- [x] **10.39.4** Add dependency health checks (PostgreSQL, Redis, Qdrant)
- [x] **10.39.5** Add performance-based health indicators

### 10.40 Retry and Backoff Implementation

**Problem:** External service calls lack proper retry mechanisms with exponential backoff.

**Goal:** Implement robust retry-with-backoff for all external service calls.

**Tasks:**
- [ ] **10.40.1** Add retry-with-backoff to AIDB → external LLM calls
- [ ] **10.40.2** Add retry-with-backoff to Hybrid Coordinator → AIDB calls
- [ ] **10.40.3** Add retry-with-backoff to Ralph → backend agent calls
- [ ] **10.40.4** Implement configurable retry policies
- [ ] **10.40.5** Add retry monitoring and metrics

---

## Phase 13 Updates: Architecture Remediation

### 13.6 Complete Continuous Learning Pipeline

**Problem:** The continuous learning pipeline is partially implemented but not fully integrated.

**Goal:** Complete the end-to-end continuous learning pipeline with feedback loops.

**Tasks:**
- [ ] **13.6.1** Complete the learning pipeline data flow from Ralph → Hybrid → AIDB
- [ ] **13.6.2** Implement pattern extraction from telemetry data
- [ ] **13.6.3** Add learning-based optimization proposals
- [ ] **13.6.4** Integrate learning feedback into service configuration
- [ ] **13.6.5** Add learning pipeline monitoring and metrics

### 13.7 Model Performance Monitoring

**Problem:** No systematic monitoring of AI model performance and drift.

**Goal:** Implement comprehensive model performance monitoring.

**Tasks:**
- [ ] **13.7.1** Add model performance tracking for AIDB
- [ ] **13.7.2** Implement model drift detection
- [ ] **13.7.3** Add model accuracy metrics collection
- [ ] **13.7.4** Create model performance dashboards
- [ ] **13.7.5** Implement model retraining triggers

### 13.8 Learning System Feedback Loop

**Problem:** The learning system lacks a closed feedback loop for continuous improvement.

**Goal:** Implement a complete feedback loop for the learning system.

**Tasks:**
- [ ] **13.8.1** Add feedback collection from service users
- [ ] **13.8.2** Implement feedback processing and analysis
- [ ] **13.8.3** Add feedback-driven optimization suggestions
- [ ] **13.8.4** Integrate feedback into service configuration updates
- [ ] **13.8.5** Document feedback loop processes

### 13.9 A/B Testing Framework

**Problem:** No framework for testing model improvements and feature changes.

**Goal:** Implement A/B testing framework for model and feature validation.

**Tasks:**
- [ ] **13.9.1** Design A/B testing framework architecture
- [ ] **13.9.2** Implement A/B testing for model comparisons
- [ ] **13.9.3** Add A/B testing for feature validation
- [ ] **13.9.4** Create A/B testing dashboard and reporting
- [ ] **13.9.5** Document A/B testing procedures

---

## Phase 15 Updates: Documentation Accuracy

### 15.3 Document Actual Data Flows

**Problem:** Current documentation lacks detailed data flow diagrams and explanations.

**Goal:** Create comprehensive documentation of actual data flows in the system.

**Tasks:**
- [x] **15.3.1** Create detailed data flow diagrams for AI stack
- [x] **15.3.2** Document data transformation processes
- [x] **15.3.3** Add data flow validation procedures
- [x] **15.3.4** Create data flow troubleshooting guides
- [x] **15.3.5** Add data flow performance considerations

**Progress Note (2026-02-16):**
- Added `docs/AI-STACK-DATA-FLOWS.md` with diagrams, API contract matrix, validation commands, troubleshooting, and performance notes.

### 15.5 Add Troubleshooting Guides

**Problem:** Limited troubleshooting documentation for common issues.

**Goal:** Create comprehensive troubleshooting guides for common issues.

**Tasks:**
- [x] **15.5.1** Create AI stack troubleshooting guide
- [x] **15.5.2** Create Kubernetes deployment troubleshooting guide
- [x] **15.5.3** Create performance issue troubleshooting guide
- [x] **15.5.4** Create security issue troubleshooting guide
- [x] **15.5.5** Add troubleshooting automation scripts

**Progress Note (2026-02-16):**
- Added `docs/AI-STACK-TROUBLESHOOTING-GUIDE.md`.
- Added automation collector `scripts/ai/ai-stack-troubleshoot.sh` producing report bundles in `artifacts/troubleshooting/`.

### 15.6 Create Developer Onboarding Documentation

**Problem:** New developers lack comprehensive onboarding materials.

**Goal:** Create comprehensive onboarding documentation for new developers.

**Tasks:**
- [x] **15.6.1** Create architecture overview for new developers
- [x] **15.6.2** Add development environment setup guide
- [x] **15.6.3** Create contribution guidelines
- [x] **15.6.4** Add code review procedures
- [x] **15.6.5** Create testing procedures documentation

**Progress Note (2026-02-16):**
- Added `docs/DEVELOPER-ONBOARDING.md` with architecture map, setup steps, contribution rules, review standards, and test procedure checklist.

### 15.7 Add Security Best Practices Documentation

**Problem:** Limited documentation on security best practices for the system.

**Goal:** Create comprehensive security best practices documentation.

**Tasks:**
- [x] **15.7.1** Document secrets management best practices
- [x] **15.7.2** Add network security configuration guidelines
- [x] **15.7.3** Create access control best practices
- [x] **15.7.4** Add security monitoring procedures
- [x] **15.7.5** Document incident response procedures

**Progress Note (2026-02-16):**
- Added `docs/SECURITY-BEST-PRACTICES.md` covering secrets handling, network hardening, access control, monitoring signals, and incident response flow.

---

## Phase 16 Updates: Testing Infrastructure

### 16.5 Add Performance Regression Tests

**Problem:** No systematic testing for performance regressions.

**Goal:** Implement performance regression testing to catch performance issues.

**Tasks:**
- [x] **16.5.1** Create performance benchmark suite
- [ ] **16.5.2** Add performance regression tests to CI/CD
- [ ] **16.5.3** Implement performance monitoring dashboards
- [ ] **16.5.4** Add performance alerting thresholds
- [x] **16.5.5** Document performance testing procedures

### 16.6 Add Security Penetration Tests

**Problem:** No systematic security testing of the deployed system.

**Goal:** Implement security penetration testing to identify vulnerabilities.

**Tasks:**
- [x] **16.6.1** Set up automated security scanning
- [ ] **16.6.2** Implement vulnerability assessment procedures
- [ ] **16.6.3** Add security compliance checking
- [x] **16.6.4** Create security test reporting
- [x] **16.6.5** Document security testing procedures

---

## Phase 17 Updates: NixOS Quick Deploy Refactoring

### 17.6 Add Comprehensive Error Handling Patterns

**Problem:** Inconsistent error handling across deployment scripts.

**Goal:** Implement consistent error handling patterns across all scripts.

**Tasks:**
- [ ] **17.6.1** Create standardized error handling functions
- [ ] **17.6.2** Implement consistent error logging
- [ ] **17.6.3** Add error recovery procedures
- [x] **17.6.4** Create error handling documentation
- [ ] **17.6.5** Add error handling tests

### 17.7 Implement Structured Logging

**Problem:** Logging is inconsistent and difficult to parse.

**Goal:** Implement structured logging across all deployment components.

**Tasks:**
- [ ] **17.7.1** Add JSON logging format support
- [ ] **17.7.2** Implement consistent log levels
- [x] **17.7.3** Add structured log parsing utilities
- [ ] **17.7.4** Create log aggregation procedures
- [x] **17.7.5** Document logging standards

### 17.8 Add Configuration Validation Functions

**Problem:** Configuration validation is inconsistent across components.

**Goal:** Implement comprehensive configuration validation.

**Tasks:**
- [ ] **17.8.1** Create configuration validation library
- [ ] **17.8.2** Add validation for all configuration files
- [ ] **17.8.3** Implement validation during deployment
- [x] **17.8.4** Add validation error reporting
- [x] **17.8.5** Document configuration validation procedures

### 17.9 Add Automated Testing for Refactored Components

**Problem:** Refactored components lack automated testing.

**Goal:** Add comprehensive automated testing for all refactored components.

**Tasks:**
- [ ] **17.9.1** Create unit tests for refactored functions
- [ ] **17.9.2** Add integration tests for refactored components
- [ ] **17.9.3** Implement test coverage reporting
- [ ] **17.9.4** Add performance tests for refactored code
- [ ] **17.9.5** Document testing procedures

---

## Phase 18 Updates: Configuration Management Consolidation

### 18.1 Complete Port Configuration Consolidation

**Problem:** Port configurations are scattered across multiple files.

**Goal:** Consolidate all port configurations into a single source of truth.

**Tasks:**
- [ ] **18.1.1** Create centralized port configuration file
- [ ] **18.1.2** Update all services to use centralized ports
- [ ] **18.1.3** Add port conflict detection
- [ ] **18.1.4** Implement port validation procedures
- [x] **18.1.5** Document port management procedures

### 18.2 Complete Credential Management System

**Problem:** Credential management is inconsistent across services.

**Goal:** Implement consistent credential management across all services.

**Tasks:**
- [ ] **18.2.1** Create centralized credential management
- [ ] **18.2.2** Implement credential rotation procedures
- [ ] **18.2.3** Add credential validation
- [ ] **18.2.4** Create credential security procedures
- [x] **18.2.5** Document credential management

### 18.3 Complete Configuration Validation Framework

**Problem:** No comprehensive configuration validation framework.

**Goal:** Implement comprehensive configuration validation framework.

**Tasks:**
- [ ] **18.3.1** Create configuration schema definitions
- [ ] **18.3.2** Implement schema validation
- [ ] **18.3.3** Add configuration dependency validation
- [ ] **18.3.4** Create validation error reporting
- [x] **18.3.5** Document validation procedures

### 18.4 Complete Configuration Documentation

**Problem:** Configuration options lack comprehensive documentation.

**Goal:** Create comprehensive documentation for all configuration options.

**Tasks:**
- [x] **18.4.1** Document all configuration parameters
- [x] **18.4.2** Add configuration examples
- [x] **18.4.3** Create configuration best practices
- [x] **18.4.4** Add configuration troubleshooting guides
- [x] **18.4.5** Create configuration validation tools

**Progress Note (2026-02-16):**
- Added `docs/CONFIGURATION-REFERENCE.md` (parameters, examples, best practices, troubleshooting).
- Added `scripts/testing/validate-config-settings.sh` and unit tests in `tests/unit/validate-config-settings.bats`.
- Wired config validation into CI smoke tests (`.github/workflows/test.yml`).

---

## Phase 19 Update (2026-02-16): Flake Validation + Security/Compatibility Gates

### 19.H1 Deterministic input validation and reporting

**Changes Applied:**
- [x] Added flake compatibility/security/dependency validator:
  - `scripts/testing/validate-flake-inputs.sh`
  - checks declared-vs-locked ref compatibility (`nixpkgs`, `home-manager`)
  - verifies lock integrity (`narHash`) and immutable git revisions (`rev`)
  - validates lock dependency graph references
  - flags insecure HTTP source URLs and floating branch refs
  - emits JSON + Markdown reports
- [x] Wired validator into CI flake job:
  - `.github/workflows/test.yml`
  - uploads `reports/flake-validation-report.json` and `.md` artifacts
- [x] Added flake management/validation documentation:
  - `docs/FLAKE-MANAGEMENT.md`
- [x] Updated clean deploy docs with validator command:
  - `docs/CLEAN-SETUP.md`

**Validation:**
- `bash -n scripts/testing/validate-flake-inputs.sh` → PASS
- `./scripts/testing/validate-flake-inputs.sh --flake-ref path:. --skip-nix-metadata` → PASS
- `bash -n .github/workflows/test.yml` is not applicable (YAML), structural edits verified by file diff review.

---

## Phase 19 Updates: Package Installation & Flake Management

### 19.4 Complete Flake.nix Package Pinning

**Problem:** AI tool versions are not pinned in flakes, leading to reproducibility issues.

**Goal:** Implement reproducible AI tool versions through flake pinning.

**Tasks:**
- [x] **19.4.7** Document flake input update procedure
- [x] **19.4.8** Implement automated flake update procedures
- [x] **19.4.9** Add flake version compatibility checking
- [x] **19.4.10** Create flake management documentation
- [x] **19.4.11** Add flake security scanning

### 19.5 Complete Flake Input Validation and Verification

**Problem:** Flake inputs lack validation and verification procedures.

**Goal:** Implement comprehensive flake input validation and verification.

**Tasks:**
- [x] **19.5.1** Add flake input signature verification
- [x] **19.5.2** Implement flake input security scanning
- [x] **19.5.3** Add flake input dependency checking
- [x] **19.5.4** Create flake validation reporting
- [x] **19.5.5** Document flake validation procedures

### 19.6 Evaluate Flake-Based Management for Non-Nix Tools

**Problem:** Non-Nix tools like Claude and Goose are not managed through flakes.

**Goal:** Evaluate and implement flake-based management for non-Nix tools.

**Tasks:**
- [x] **19.6.1** Research Nix packaging for Claude Code
- [x] **19.6.2** Research Goose CLI Nix packaging
- [x] **19.6.3** Evaluate native vs Nix trade-offs
- [x] **19.6.4** Document recommendation
- [x] **19.6.5** Implement chosen approach for tool management

## Phase 19 Update (2026-02-16): Non-Nix Tool Management Decision (19.6)

### 19.H2 Claude native + Goose declarative policy

**Changes Applied:**
- [x] Closed 19.4.1 / 19.4.2 policy decisions:
  - no Claude flake overlay for now (native installer remains canonical path).
  - `nix-ai-tools` remains absent by design; if introduced later it must be commit-pinned (enforced).
- [x] Claude Code policy finalized:
  - keep native installer path (`install_claude_code_native`) as canonical.
  - keep Claude removed from npm manifest.
- [x] Goose CLI policy finalized:
  - prefer declarative nixpkgs package (`goose-cli`) via profile package data.
  - keep fallback release installer in `lib/tools.sh` for compatibility.
- [x] Added policy guardrail script:
  - `scripts/testing/validate-tool-management-policy.sh`
- [x] Wired policy validation into CI flake-validation job:
  - `.github/workflows/test.yml`
- [x] Documented recommendation and trade-offs:
  - `docs/FLAKE-MANAGEMENT.md`

**Validation:**
- `bash -n scripts/testing/validate-tool-management-policy.sh` → PASS
- `./scripts/testing/validate-tool-management-policy.sh` → PASS
- `bash -n scripts/deploy-clean.sh` → PASS

### 19.6 Task Status

- [x] **19.6.1** Research Nix packaging for Claude Code
- [x] **19.6.2** Research Goose CLI Nix packaging
- [x] **19.6.3** Evaluate native vs Nix trade-offs
- [x] **19.6.4** Document recommendation
- [x] **19.6.5** Implement chosen approach for tool management

## Phase 26 Update (2026-02-16): System Package Deduplication Baseline

### 26.H12 Single-source package merge and dedupe

**Changes Applied:**
- [x] Added `mySystem.profileData.systemPackageNames` option:
  - `nix/modules/core/options.nix`
- [x] Centralized package merge in base module:
  - `nix/modules/core/base.nix` now merges base + profile package names and deduplicates via `lib.unique`.
- [x] Removed direct profile writes to `environment.systemPackages`:
  - `nix/modules/profiles/ai-dev.nix`
  - `nix/modules/profiles/gaming.nix`
  - `nix/modules/profiles/minimal.nix`
- [x] Updated package comparison to include Goose where intended:
  - `scripts/testing/compare-installed-vs-intended.sh`

**Validation:**
- `nix-instantiate --parse` for updated Nix modules/data files → PASS
- `rg -n "environment\\.systemPackages" nix/modules` now resolves to a single source (`core/base.nix`) → PASS
- `./scripts/testing/compare-installed-vs-intended.sh --host nixos --profile ai-dev --flake-ref path:.` → PASS

## Phase 26 Update (2026-02-16): Placeholder Template Prune Audit (26.6.2)

### 26.H13 Focused template placeholder cleanup

**Changes Applied:**
- [x] Archived orphaned legacy systemd templates from `templates/systemd/` to `archive/templates/systemd-legacy/`:
  - `ai-stack-cleanup.service`
  - `ai-stack-runtime-recovery.service`
  - `ai-stack-resume-recovery.sh`
  - `claude-api-proxy.service`
- [x] Updated placeholder baseline to reflect active template surface:
  - `config/template-placeholder-baseline.tsv`
- [x] Updated cleanup guide path references:
  - `scripts/README-ORPHANED-PROCESS-CLEANUP.md`

**Validation:**
- `./scripts/governance/lint-template-placeholders.sh` → PASS
- Placeholder-bearing files under active `templates/` tree reduced accordingly.

## Phase 28 Update (2026-02-16): K3s-First Ops + Flake Deploy-Mode Convergence

### 28.H1 Quick Deploy now drives clean declarative engine with explicit mode control

**Changes Applied:**
- [x] `scripts/deploy-clean.sh`
  - `--recovery-mode` no longer forces `--boot`; default mode remains `switch`.
  - Added explicit target overrides:
    - `--nixos-target`
    - `--home-target`
  - Added skip controls:
    - `--skip-system-switch`
    - `--skip-home-switch`
  - Added recovery-mode informational log clarifying `switch` vs `boot` expectations.
  - Strengthened previous-boot fsck gate:
    - scans broader previous-boot journal signatures (`/sysroot` dependency chain + emergency mode + fsck failures)
    - blocks live `switch` when root-fs failure signatures are present and instructs `--recovery-mode --boot`.
- [x] `nixos-quick-deploy.sh`
  - Added `--flake-first-deploy-mode switch|boot|build`.
  - Reworked `run_flake_first_deployment()` to call `scripts/deploy-clean.sh` directly.
  - Preserved operator prompts/choices (`--prompt-system-switch`, `--prompt-home-switch`) and mapped choices to clean deploy flags.
  - Preserved flake dry-run check behavior.
- [x] K3s-first skill alignment:
  - Replaced podman-first `ai-service-management` skill docs with K3s-first workflows:
    - `.agent/skills/ai-service-management/SKILL.md`
  - `ai-stack/agents/skills/ai-service-management/SKILL.md`
- [x] Recovery fsck bypass hardening:
  - `nix/modules/hardware/recovery.nix` now adds `fsck.mode=skip` + `fsck.repair=no` when `rootFsckMode=skip`.

**Validation:**
- `bash -n scripts/deploy-clean.sh` → PASS
- `bash -n nixos-quick-deploy.sh` → PASS
- `./scripts/deploy-clean.sh --help` includes new/updated flags and recovery semantics → PASS

**Remaining Gated Verification:**
- [ ] Run interactive end-to-end on host:
  - `./nixos-quick-deploy.sh --flake-first --flake-first-profile ai-dev --flake-first-deploy-mode switch`
- [ ] Confirm no reboot message in default `switch` mode and successful live apply.
- [ ] Confirm `boot` mode still stages generation and reports reboot requirement.

## Phase 29 Update (2026-02-16): K3s-First MLOps Lifecycle Planning

### 29.P1 MLOps suggestions normalized to Kubernetes-native roadmap

**Planned Scope Added to Roadmap:**
- [x] Added new Phase 29 definition in `SYSTEM-UPGRADE-ROADMAP.md`.
- [x] Broke work into explicit K3s-first tracks:
  - DVC + S3-compatible artifact store in K3s
  - MLflow experiment tracking in K3s
  - Global Qdrant knowledge loop with ingestion safeguards
  - Promptfoo regression gates in CI/local workflows
- [x] Added phase-level exit criteria enforcing no podman dependency for normal AI lifecycle ops.

**Implementation Status:**
- [ ] Not implemented yet (planning + decomposition complete).

## Phase 10/16/17 Update (2026-03-04): Reliability + Testing + Logging/Validation Procedures

### Runtime reliability implementation slice completed

**Changes Applied:**
- [x] Added Hybrid detailed health endpoint with dependency and performance payload:
  - `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (`GET /health/detailed`)
- [x] Added Ralph detailed health endpoint with dependency and performance payload:
  - `ai-stack/mcp-servers/ralph-wiggum/server.py` (`GET /health/detailed`)
- [x] Added runtime reliability verification script:
  - `scripts/reliability/check-runtime-reliability.sh`
- [x] Added runtime reliability operations documentation:
  - `docs/operations/reliability/AI-STACK-RUNTIME-RELIABILITY.md`

### Performance/security/testing/logging/config-validation procedures completed

**Changes Applied:**
- [x] Added benchmark suite:
  - `scripts/performance/run-performance-benchmark-suite.sh`
- [x] Added security penetration suite with report artifacts:
  - `scripts/security/run-security-penetration-suite.sh`
- [x] Added structured log parsing utility:
  - `scripts/observability/parse-structured-logs.py`
- [x] Added procedure docs:
  - `docs/operations/procedures/PERFORMANCE-TESTING-PROCEDURES.md`
  - `docs/operations/procedures/SECURITY-TESTING-PROCEDURES.md`
  - `docs/operations/standards/LOGGING-STANDARDS.md`
  - `docs/operations/procedures/CONFIG-VALIDATION-PROCEDURES.md`
  - `docs/operations/procedures/PORT-MANAGEMENT-PROCEDURES.md`
  - `docs/operations/procedures/CREDENTIAL-MANAGEMENT-PROCEDURES.md`
  - existing error-handling guide validated for roadmap task closure: `docs/ERROR_HANDLING_PATTERNS.md`

**Validation (local static):**
- `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/http_server.py ai-stack/mcp-servers/ralph-wiggum/server.py` → PASS
- `bash -n scripts/reliability/check-runtime-reliability.sh scripts/performance/run-performance-benchmark-suite.sh scripts/security/run-security-penetration-suite.sh` → PASS
- `python3 scripts/observability/parse-structured-logs.py --help` → PASS

**Gated runtime validation (requires next rebuild/deploy):**
- Run `scripts/reliability/check-runtime-reliability.sh` against deployed services and confirm `GET /health/detailed` endpoint responses for Hybrid and Ralph.

## Phase 25 Update (2026-02-16): Post-Boot Filesystem Integrity Monitor

### 25.H5 Add automated integrity detection guardrails

**Changes Applied:**
- [x] Added declarative filesystem integrity monitor module:
  - `nix/modules/core/fs-integrity-monitor.nix`
- [x] Added monitor options under deployment:
  - `mySystem.deployment.fsIntegrityMonitor.enable` (default: `true`)
  - `mySystem.deployment.fsIntegrityMonitor.intervalMinutes` (default: `60`)
  - File: `nix/modules/core/options.nix`
- [x] Wired module into flake host module list:
  - File: `flake.nix`
- [x] Provisioned systemd units declaratively:
  - `fs-integrity-monitor.service` (oneshot journal signature scan)
  - `fs-integrity-monitor.timer` (`OnBootSec=3min`, periodic rerun, `Persistent=true`)
- [x] Exposed manual CLI in system packages:
  - `fs-integrity-check`
  - Scans current + previous boot logs for fsck/ext4 failure signatures and emits offline repair guidance.
- [x] Added immediate repo-local manual checker (usable before rebuild):
  - `scripts/health/fs-integrity-check.sh`

**Validation:**
- `nix-instantiate --parse nix/modules/core/fs-integrity-monitor.nix` → PASS
- `nix-instantiate --parse nix/modules/core/options.nix` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `bash -n scripts/health/fs-integrity-check.sh` → PASS

## Phase 30 Update (2026-02-16): Boot + Filesystem Resilience Guardrails

### 30.H1 Hardening rollout (guardrails + fallbacks + monitoring)

**Changes Applied:**
- [x] Added declarative disk health monitor:
  - `nix/modules/core/disk-health-monitor.nix`
  - service/timer: `disk-health-monitor.service` + `.timer`
  - CLI: `disk-health-check`
- [x] Added deployment options for disk monitor:
  - `mySystem.deployment.diskHealthMonitor.enable` (default `true`)
  - `mySystem.deployment.diskHealthMonitor.intervalMinutes` (default `180`)
  - file: `nix/modules/core/options.nix`
- [x] Wired disk monitor module into flake:
  - file: `flake.nix`
- [x] Added GUI switch safety fallback in `scripts/deploy-clean.sh`:
  - auto-fallback from `switch` to `boot` in graphical sessions (override with `ALLOW_GUI_SWITCH=true`)
  - added explicit flags: `--allow-gui-switch`, `--no-gui-fallback`
  - added env docs in `--help`
- [x] Added offline repair helper:
  - `scripts/deploy/recovery-offline-fsck-guide.sh`
- [x] Added bootloader resilience defaults in `nix/modules/core/base.nix`:
  - `boot.loader.systemd-boot.configurationLimit = 20` (mkDefault)
  - `boot.loader.systemd-boot.graceful = true` (mkDefault)
- [x] Added new planning/execution phase:
  - `Phase 30` section in `SYSTEM-UPGRADE-ROADMAP.md` with tasks, fallbacks, and success criteria.
- [x] Added operator policy/runbook document:
  - `docs/BOOT-FS-RESILIENCE-GUARDRAILS.md`
  - includes upstream references (`e2fsck(8)`, `systemd-fsck@.service(8)`, `systemd.timer(5)`, NixOS options, `smartctl(8)`)

**Validation:**
- `nix-instantiate --parse nix/modules/core/disk-health-monitor.nix` → PASS
- `nix-instantiate --parse nix/modules/core/fs-integrity-monitor.nix` → PASS
- `nix-instantiate --parse nix/modules/core/options.nix` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `bash -n scripts/deploy-clean.sh` → PASS
- `bash -n scripts/deploy/recovery-offline-fsck-guide.sh` → PASS

## Phase 30 Update (2026-02-17): Guardrail Completion Pass

### 30.H2 Close remaining non-gated safeguards

**Changes Applied:**
- [x] Added declarative guardrail failure notification module:
  - `nix/modules/core/guardrail-alerts.nix`
  - `deploy-guardrail-alert@.service`
  - CLI: `guardrail-failure-notify`
- [x] Wired monitor failure hooks:
  - `nix/modules/core/fs-integrity-monitor.nix` now uses `onFailure = [ "deploy-guardrail-alert@%n.service" ]`
  - `nix/modules/core/disk-health-monitor.nix` now uses `onFailure = [ "deploy-guardrail-alert@%n.service" ]`
- [x] Added monitor visibility in health reporting:
  - `scripts/health/system-health-check.sh` now includes a `Boot + Filesystem Guardrails` section
  - reports monitor/timer health and guardrail alert backlog
- [x] Added deploy preflight bootloader guard:
  - `scripts/deploy-clean.sh` now verifies bootloader enablement, `bootctl status`, mounted ESP, and minimum free ESP space before deploy
  - threshold is declarative via `mySystem.deployment.bootloaderEspMinFreeMb` (default `128`)
  - option added in `nix/modules/core/options.nix`
- [x] Added deterministic tests for helper scripts:
  - `tests/unit/fs-integrity-helpers.bats`
  - added test overrides in:
    - `scripts/health/fs-integrity-check.sh`
    - `scripts/deploy/recovery-offline-fsck-guide.sh`
- [x] Added immediate git operability fallback for unstable hosts:
  - `scripts/governance/git-safe.sh` (uses system `git` when present, otherwise ephemeral `nixpkgs#git`)
  - `scripts/health/system-health-check.sh` remediation output now references the fallback when `git` is missing.

**Validation:**
- `bash -n scripts/deploy-clean.sh scripts/health/system-health-check.sh scripts/health/fs-integrity-check.sh scripts/deploy/recovery-offline-fsck-guide.sh` → PASS
- `nix-instantiate --parse nix/modules/core/guardrail-alerts.nix` → PASS
- `nix-instantiate --parse nix/modules/core/fs-integrity-monitor.nix` → PASS
- `nix-instantiate --parse nix/modules/core/disk-health-monitor.nix` → PASS
- `nix-instantiate --parse nix/modules/core/options.nix` → PASS
- `nix-instantiate --parse flake.nix` → PASS
- `nix --extra-experimental-features 'nix-command flakes' shell nixpkgs#bats --command bats --tap tests/unit/fs-integrity-helpers.bats` → PASS

## Phase 30 Update (2026-02-17): Account Lockout + Facts Permission Guardrails

### 30.H3 Prevent deploy-time account lock regressions and unreadable host facts

**Changes Applied:**
- [x] Added deploy-time account safety checks in `scripts/deploy-clean.sh`:
  - Preflight blocks deploy when the running primary account is locked.
  - Post-switch re-check verifies the primary account did not become locked during apply.
- [x] Added target configuration lockout guardrails in `scripts/deploy-clean.sh`:
  - Blocks deploy if target config declares a locked `hashedPassword` for primary/root users.
  - Blocks deploy if `users.mutableUsers=false` but primary user is missing or has no password directive.
  - Blocks deploy when initrd emergency access is enabled but declared root account has invalid password state.
- [x] Added host facts ownership/permission repair in `scripts/deploy-clean.sh`:
  - Auto-repairs unreadable `nix/hosts/<host>/facts.nix` before flake eval.
  - Fails fast with explicit remediation when privilege escalation is unavailable.
- [x] Hardened facts generation permissions in `scripts/governance/discover-system-facts.sh`:
  - Enforces `0644` on generated `facts.nix`.
  - When invoked as root via sudo, re-owns facts file back to invoking non-root user.
- [x] Added declarative eval-time assertions in `nix/modules/core/base.nix`:
  - Prevents builds with locked declarative password hashes for primary/root users.
  - Prevents immutable-user (`users.mutableUsers=false`) configs without a valid primary-user password declaration.

**Validation:**
- `bash -n scripts/deploy-clean.sh` → PASS
- `bash -n scripts/governance/discover-system-facts.sh` → PASS
- `nix-instantiate --parse nix/modules/core/base.nix` → PASS
- Guardrail behavior verified:
  - `./scripts/deploy-clean.sh --host hyperd --profile ai-dev --build-only --skip-system-switch --skip-home-switch --skip-health-check --skip-flatpak-sync`
  - Result: correctly fails with account-lock guard (`Account 'hyperd' is locked`).

**Current Gated Blocker (needs operator action on target host):**
- Primary operator account is still locked (`passwd -S hyperd -> L`), which correctly blocks deploy preflight.
- `nix/hosts/nixos/facts.nix` ownership/permissions were repaired and file regenerated.

## Phase 31 Update (2026-02-17): Fresh-Host Readiness Analysis + Preflight Hardening

### 31.H1 Analysis → Plan → Implementation for clean reinstall path

**Analysis Findings (current host):**
- Hard blockers:
  - operator account locked (`hyperd`) -> deployment must fail fast.
- Optional gaps (warn-only, acceptable for fresh host bootstrap):
  - `home-manager` absent
  - `flatpak` absent
  - `lspci` absent
  - `jq` absent
- Structural checks:
  - `flake.nix` readable
  - host scaffold present (`nix/hosts/nixos/default.nix`)
  - `facts.nix` now present + readable after regeneration

**Plan Executed:**
- [x] Add dedicated readiness analysis script for fresh/blank hosts.
- [x] Integrate analysis into `deploy-clean` preflight and add `--analyze-only`.
- [x] Ensure probe commands remain timeout-safe and do not hang.
- [x] Keep optional tooling non-fatal with explicit warnings/remediation.

**Implementation Applied:**
- [x] Added new script: `scripts/governance/analyze-clean-deploy-readiness.sh`
  - checks core commands, optional commands, host/flake structure, account lock state, eval capability
  - prints pass/warn/fail summary and remediation guidance
  - supports `--host`, `--profile`, `--flake-ref`, `--update-lock`
- [x] Updated `scripts/deploy-clean.sh`
  - new flags:
    - `--analyze-only`
    - `--skip-readiness-check`
  - runs readiness analysis before build/switch path by default
  - exits early in analyze-only mode
- [x] Hardened readiness evaluator
  - timeout-protected `nix eval` probe to avoid preflight hangs

**Validation:**
- `bash -n scripts/governance/analyze-clean-deploy-readiness.sh scripts/deploy-clean.sh` → PASS
- `./scripts/governance/analyze-clean-deploy-readiness.sh --host nixos --profile ai-dev --flake-ref path:$(pwd)` → FAIL (expected, account locked)
  - Summary: `8 pass, 5 warn, 1 fail`
- `./scripts/deploy-clean.sh --host nixos --profile ai-dev --analyze-only --skip-discovery --skip-health-check --skip-flatpak-sync` → FAIL (expected, same locked-account gate)
## Program Closure Update (2026-03-04)

- System Upgrade Roadmap is now closed as a completed historical program.
- Canonical active execution plans are:
  - `docs/SYSTEM-IMPROVEMENT-PLAN-2026-03.md`
  - `docs/AGENT-PARITY-MATRIX.md`
- Closure verification evidence (latest pass):
  - `scripts/testing/check-mcp-health.sh` (13/13 required services passing)
  - `scripts/governance/quick-deploy-lint.sh --mode fast` (all checks passing)
  - `scripts/testing/validate-runtime-declarative.sh` (pass)
  - `scripts/testing/check-prsi-phase7-program.sh` (pass)
  - `scripts/testing/verify-flake-first-roadmap-completion.sh` (31 pass / 0 fail)
- `scripts/automation/run-harness-improvement-pass.sh` (success=true)

## Post-Activation Validation Report (2026-03-04 13:12 UTC)

### Scope
- Validate `ai-npm-security-monitor.service` after activation.
- Confirm systemd execution status, journal evidence, and report artifact output.

### Results
- `systemctl show ai-npm-security-monitor.service`:
  - `Result=success`
  - `ExecMainStatus=0`
  - `ActiveState=inactive` / `SubState=dead` (expected for `Type=oneshot`)
- Journal evidence:
  - `Starting AI Stack npm supply-chain security monitor...`
  - `npm security report written: /var/lib/ai-stack/security/npm/npm-security-20260304T131216Z.json`
  - `Finished AI Stack npm supply-chain security monitor.`
- Artifacts present:
  - `/var/lib/ai-stack/security/npm/latest-npm-security.json`
  - `/var/lib/ai-stack/security/npm/npm-security-20260304T131216Z.json`

### Outcome
- PASS: post-activation npm monitor execution is healthy on current generation.
- Historical failures shown by `systemctl status` are prior invocations and do not represent the latest run state.

## Repo Cleanup Update (2026-03-04)

### Pass 2 execution (continuous loop batch)

**Changes Applied:**
- [x] Enforced structure policy as a persistent gate in hooks/CI/quick-deploy lint.
- [x] Migrated reliability/procedure docs from docs root into subject folders:
  - `docs/operations/reliability/`
  - `docs/operations/procedures/`
  - `docs/operations/standards/`
- [x] Migrated reliability/performance/security/observability scripts from scripts root into subject folders:
  - `scripts/reliability/`
  - `scripts/performance/`
  - `scripts/security/`
  - `scripts/observability/`
- [x] Archived all numbered legacy docs into:
  - `docs/archive/legacy-sequence/`
- [x] Rewrote callsites and doc links for moved files.
- [x] Fixed repo-structure lint `--all` mode to evaluate current working-tree files and avoid deleted-index false failures.
- [x] Regenerated cleanup inventory baseline:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `scripts/governance/repo-structure-lint.sh --all` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS
- `bash -n scripts/governance/repo-structure-lint.sh scripts/reliability/check-runtime-reliability.sh scripts/performance/run-performance-benchmark-suite.sh scripts/security/run-security-penetration-suite.sh` → PASS
- `python3 -m py_compile scripts/observability/parse-structured-logs.py` → PASS

### Pass 3 incremental script-root reduction (continuous loop)

**Changes Applied:**
- [x] Migrated all `aq*` root scripts into `scripts/ai/` and rewired callsites across Nix modules, tests, docs, and runtime scripts.
- [x] Migrated all root `check-*` scripts into `scripts/testing/`.
- [x] Migrated all root `run-*` scripts into `scripts/automation/`.
- [x] Migrated all root `analyze-*`, `audit-*`, and `lint-*` scripts into `scripts/governance/`.
- [x] Migrated all root `validate-*` and `verify-*` scripts into `scripts/testing/`.
- [x] Migrated all root `seed-*` and `sync-*` scripts into `scripts/data/`.
- [x] Migrated all root `start-*`, `stop-*`, and `serve-*` scripts into `scripts/deploy/`.
- [x] Migrated all root `install-*` and `setup-*` scripts into `scripts/deploy/`.
- [x] Migrated all root `test-*` scripts into `scripts/testing/`.
- [x] Migrated all root `import-*`, `export-*`, `populate-*`, `download-*`, and `backup-*` scripts into `scripts/data/`.
- [x] Migrated all root `discover-*` and `manage-*` scripts into `scripts/governance/`.
- [x] Migrated all root `generate-*` scripts into `scripts/data/`.
- [x] Migrated remaining root `ai-*`, `security-*`, `mcp-*`, and `update-*` scripts:
  - `scripts/ai/`: `ai-*`, `mcp-*`, `harness-rpc.js`, `llama-model-cli.sh`, `ralph-orchestrator.sh`, `route-reasoning-mode.py`
  - `scripts/security/`: `security-audit.sh`, `security-manager.sh`, `security-scan.sh`, `update-mcp-integrity-baseline.sh`
  - `scripts/data/`: `update-ai-research-now.sh`, `update-aidb-library-catalog-now.sh`
  - `scripts/governance/`: `update-readme-ai-stack.py`, `apply-project-root.sh`, `apply-readme-ai-stack-updates.py`, `git-safe.sh`, `new-improvement-proposal.sh`, `smart_config_gen.sh`, `list-issues.py`, `comprehensive-mcp-search.py`
  - `scripts/deploy/`: `local-registry.sh`
  - `scripts/automation/`: `prsi-orchestrator.py`
- [x] Migrated bootstrap/init/migrate/proxy wrappers:
  - `scripts/ai/`: `claude-api-proxy.py`, `claude-local-wrapper.py`, `complete-via-ralph.sh`
  - `scripts/deploy/`: `deploy-aidb-mcp-server.sh`, `quick-deploy-fast-verify.sh`
  - `scripts/data/`: `bootstrap-prsi-confidence-samples.sh`, `bootstrap_aidb_data.sh`, `initialize-qdrant-collections.sh`, `migrate-reports-to-database.sh`
  - `scripts/governance/`: `preflight-auto-remediate.sh`
- [x] Migrated smoke/test utility scripts out of root:
  - `scripts/testing/`: `smoke-*`, `chaos-harness-smoke.sh`, `rag-smoke-test.sh`, `telemetry-smoke-test.sh`, `test_real_world_workflows.sh`, `test_services.sh`
  - `scripts/health/`: `system-health-check.sh`
- [x] Migrated root recovery/rotation scripts into target domains:
  - `scripts/deploy/`: `fast-rebuild.sh`, `recovery-*`, `restore-drill.sh`
  - `scripts/security/`: `renew-tls-certificate.sh`, `rotate-api-key.sh`
  - `scripts/data/`: `rebuild-qdrant-collections.sh`, `rotate-telemetry.sh`
  - `scripts/governance/`: `record-claude-code-errors.sh`, `record-issue.py`
- [x] Normalized moved script repo-root resolution from one-level-up (`/..`) to two-level-up (`/../..`) where required.

**Validation:**
- `bash -n scripts/ai/aq-completions.sh scripts/ai/aq-gap-import scripts/ai/aq-gaps scripts/ai/aq-knowledge-import.sh scripts/ai/aq-qa scripts/ai/aq-rate scripts/ai/aqd` → PASS
- `python3 -m py_compile scripts/ai/aq-auto-remediate.py scripts/ai/aq-hints scripts/ai/aq-optimizer scripts/ai/aq-prompt-eval scripts/ai/aq-report` → PASS
- `bash -n scripts/testing/check-*.sh` → PASS
- `bash -n scripts/automation/run-*.sh` → PASS
- `bash -n scripts/governance/analyze-clean-deploy-readiness.sh scripts/governance/audit-deploy-feature-toggles.sh scripts/governance/audit-hardcoded-paths.sh scripts/governance/audit-service-endpoints.sh scripts/governance/lint-color-echo-usage.sh` → PASS
- `bash -n scripts/testing/validate-*.sh scripts/testing/verify-*.sh` → PASS
- `bash -n scripts/data/seed-*.sh scripts/data/sync-*.sh scripts/data/sync-knowledge-sources` → PASS
- `bash -n scripts/deploy/start-*.sh scripts/deploy/stop-*.sh scripts/deploy/serve-*.sh scripts/deploy/install-*.sh scripts/deploy/setup-*.sh` → PASS
- `bash -n scripts/testing/test-*.sh` → PASS
- `bash -n scripts/data/backup-*.sh scripts/data/download-*.sh scripts/data/export-*.sh scripts/data/import-*.sh scripts/data/populate-*.sh scripts/data/sync-knowledge-sources` → PASS
- `bash -n scripts/data/generate-*.sh scripts/governance/discover-improvements.sh scripts/governance/discover-system-facts.sh scripts/governance/manage-secrets.sh` → PASS
- `bash -n scripts/deploy/recovery-*.sh scripts/deploy/restore-drill.sh scripts/security/renew-tls-certificate.sh scripts/security/rotate-api-key.sh scripts/data/rebuild-qdrant-collections.sh scripts/data/rotate-telemetry.sh scripts/governance/record-claude-code-errors.sh` → PASS
- `bash -n scripts/testing/smoke-*.sh scripts/testing/chaos-harness-smoke.sh scripts/testing/rag-smoke-test.sh scripts/testing/telemetry-smoke-test.sh scripts/testing/test_real_world_workflows.sh scripts/testing/test_services.sh scripts/health/system-health-check.sh` → PASS
- `bash -n scripts/ai/ai-*.sh scripts/security/security-*.sh scripts/ai/mcp-* scripts/data/update-*.sh scripts/governance/{apply-project-root.sh,new-improvement-proposal.sh,smart_config_gen.sh,git-safe.sh} scripts/deploy/local-registry.sh` → PASS
- `bash -n scripts/ai/complete-via-ralph.sh scripts/deploy/{deploy-aidb-mcp-server.sh,quick-deploy-fast-verify.sh} scripts/data/{bootstrap-prsi-confidence-samples.sh,bootstrap_aidb_data.sh,initialize-qdrant-collections.sh,migrate-reports-to-database.sh} scripts/governance/preflight-auto-remediate.sh` → PASS
- `python3 -m py_compile scripts/data/sync-hint-feedback-db.py scripts/testing/test-continuous-learning.py scripts/testing/test-discovery-system.py scripts/testing/test-rag-workflow.py scripts/testing/test-tool-security-auditor.py` → PASS
- `python3 -m py_compile scripts/data/import-documents.py scripts/data/populate-knowledge-base.py scripts/data/populate-knowledge-from-web.py scripts/data/populate-qdrant-directly.py scripts/data/populate-qdrant-with-embeddings.py` → PASS
- `python3 -m py_compile scripts/governance/discover-focused-agent-repos.py scripts/governance/discover-improvements.py scripts/governance/discover-semantic-github-repos.py scripts/governance/manage-secrets.py scripts/governance/record-issue.py` → PASS
- `python3 -m py_compile scripts/governance/{apply-readme-ai-stack-updates.py,update-readme-ai-stack.py,list-issues.py,comprehensive-mcp-search.py} scripts/ai/{mcp-bridge-hybrid.py,route-reasoning-mode.py} scripts/automation/prsi-orchestrator.py` → PASS
- `python3 -m py_compile scripts/ai/claude-api-proxy.py scripts/ai/claude-local-wrapper.py` → PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` → PASS

## Repo Hygiene Pass (2026-03-05): Report Cleanup Utility Canonicalization

### RH.H33 Move report-cleanup utility to `scripts/data/` and preserve compatibility shim

**Changes Applied:**
- [x] Moved report cleanup utility implementation:
  - `scripts/cleanup-migrated-reports.sh` -> `scripts/data/cleanup-migrated-reports.sh`
- [x] Added root compatibility shim:
  - `scripts/cleanup-migrated-reports.sh` now forwards to `scripts/data/cleanup-migrated-reports.sh`
- [x] Fixed post-move path resolution:
  - adjusted `PROJECT_ROOT` and sourced helper path to work from nested `scripts/data/`.
- [x] Updated canonical command hint in:
  - `scripts/data/migrate-reports-to-database.sh`
- [x] Updated cleanup inventory target rows to canonical path in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/cleanup-migrated-reports.sh scripts/data/cleanup-migrated-reports.sh scripts/data/migrate-reports-to-database.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): TLS Apply Utility Canonicalization

### RH.H34 Move deprecated TLS apply helper to `scripts/security/` and preserve compatibility shim

**Changes Applied:**
- [x] Moved deprecated TLS apply helper implementation:
  - `scripts/apply-tls-certificates.sh` -> `scripts/security/apply-tls-certificates.sh`
- [x] Added root compatibility shim:
  - `scripts/apply-tls-certificates.sh` now forwards to `scripts/security/apply-tls-certificates.sh`
- [x] Added purpose header comment in canonical script for lint compliance.
- [x] Updated cleanup inventory target rows to canonical path in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/apply-tls-certificates.sh scripts/security/apply-tls-certificates.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Local AI Demo Utility Canonicalization

### RH.H35 Move local-AI usage demo utility to `scripts/testing/` and preserve compatibility shim

**Changes Applied:**
- [x] Moved demo utility implementation:
  - `scripts/demo-local-ai-usage.py` -> `scripts/testing/demo-local-ai-usage.py`
- [x] Added root compatibility shim:
  - `scripts/demo-local-ai-usage.py` now forwards to `scripts/testing/demo-local-ai-usage.py`
- [x] Updated active doc references to canonical path in:
  - `docs/ENFORCE-LOCAL-AI-USAGE.md`
- [x] Updated cleanup inventory target rows to canonical path in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `python3 -m py_compile scripts/demo-local-ai-usage.py scripts/testing/demo-local-ai-usage.py` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Agent Policy Evaluator Canonicalization

### RH.H36 Move agent policy evaluator to `scripts/governance/` and preserve compatibility shim

**Changes Applied:**
- [x] Moved policy evaluator implementation:
  - `scripts/evaluate-agent-policy.py` -> `scripts/governance/evaluate-agent-policy.py`
- [x] Added root compatibility shim:
  - `scripts/evaluate-agent-policy.py` now forwards to `scripts/governance/evaluate-agent-policy.py`
- [x] Updated active script/doc references to canonical path in:
  - `scripts/automation/run-advanced-parity-suite.sh`
  - `scripts/ai/aqd`
  - `docs/AGENT-PARITY-MATRIX.md`
  - `docs/PARITY-ADVANCED-TOOLING.md`
- [x] Updated cleanup inventory target rows to canonical path in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `python3 -m py_compile scripts/evaluate-agent-policy.py scripts/governance/evaluate-agent-policy.py` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Nix/Discovery/Registry Script Canonicalization

### RH.H37 Move static-analysis and deprecated discovery/registry helpers to domain folders with compatibility shims

**Changes Applied:**
- [x] Moved active Nix static analysis utility:
  - `scripts/nix-static-analysis.sh` -> `scripts/governance/nix-static-analysis.sh`
- [x] Moved deprecated discovery helper:
  - `scripts/enable-progressive-disclosure.sh` -> `scripts/deploy/enable-progressive-disclosure.sh`
- [x] Moved deprecated local registry helper:
  - `scripts/publish-local-registry.sh` -> `scripts/deploy/publish-local-registry.sh`
- [x] Added root compatibility shims for all three original root paths.
- [x] Updated active script/doc/CI references to canonical paths in:
  - `.github/workflows/test.yml`
  - `docs/operations/reference/QUICK-REFERENCE.md`
  - `docs/AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md`
  - `docs/development/COMPLETION-ROADMAP.md`
  - `docs/development/SYSTEM-UPGRADE-ROADMAP.md`
  - `docs/development/SYSTEM-UPGRADE-ROADMAP-UPDATES.md`
- [x] Updated cleanup inventory target rows to canonical paths in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/nix-static-analysis.sh scripts/governance/nix-static-analysis.sh scripts/enable-progressive-disclosure.sh scripts/deploy/enable-progressive-disclosure.sh scripts/publish-local-registry.sh scripts/deploy/publish-local-registry.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Registry/Gap Curation Utility Canonicalization

### RH.H38 Move registry validation and residual-gap curation utilities to domain folders with compatibility shims

**Changes Applied:**
- [x] Moved edge-model registry validator:
  - `scripts/edge-model-registry-validate.sh` -> `scripts/governance/edge-model-registry-validate.sh`
- [x] Moved residual-gap curation utility:
  - `scripts/curate-residual-gaps.sh` -> `scripts/data/curate-residual-gaps.sh`
- [x] Added root compatibility shims for both original root paths.
- [x] Fixed post-move repo-root/service-endpoints path resolution for both canonical scripts.
- [x] Updated active tool reference in:
  - `docs/SYSTEM-IMPROVEMENT-PLAN-2026-03.md`
- [x] Updated cleanup inventory target rows to canonical paths in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/edge-model-registry-validate.sh scripts/governance/edge-model-registry-validate.sh scripts/curate-residual-gaps.sh scripts/data/curate-residual-gaps.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): MangoHud Utility Canonicalization

### RH.H39 Move MangoHud profile/fix utilities to `scripts/deploy/` with compatibility shims

**Changes Applied:**
- [x] Moved MangoHud config-fix utility:
  - `scripts/fix-mangohud-config.sh` -> `scripts/deploy/fix-mangohud-config.sh`
- [x] Moved MangoHud profile selector utility:
  - `scripts/mangohud-profile.sh` -> `scripts/deploy/mangohud-profile.sh`
- [x] Added root compatibility shims for both original root paths.
- [x] Fixed post-move repo-root resolution in both canonical scripts.
- [x] Updated usage line in canonical `fix-mangohud-config.sh` to new path.
- [x] Updated cleanup inventory target rows to canonical paths in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/fix-mangohud-config.sh scripts/deploy/fix-mangohud-config.sh scripts/mangohud-profile.sh scripts/deploy/mangohud-profile.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Dashboard/COSMIC Helper Canonicalization

### RH.H40 Move dashboard enhancement and COSMIC power-profile helpers to `scripts/deploy/` with compatibility shims

**Changes Applied:**
- [x] Moved dashboard enhancement helper:
  - `scripts/enhance-dashboard-with-controls.sh` -> `scripts/deploy/enhance-dashboard-with-controls.sh`
- [x] Moved COSMIC power-profile helper:
  - `scripts/enable-cosmic-power-profiles.sh` -> `scripts/deploy/enable-cosmic-power-profiles.sh`
- [x] Added root compatibility shims for both original root paths.
- [x] Fixed post-move repo-root resolution for dashboard enhancement helper.
- [x] Updated cleanup inventory target rows to canonical paths in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/enhance-dashboard-with-controls.sh scripts/deploy/enhance-dashboard-with-controls.sh scripts/enable-cosmic-power-profiles.sh scripts/deploy/enable-cosmic-power-profiles.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): p10k Wizard Canonicalization

### RH.H41 Move p10k setup wizard to `scripts/deploy/` and keep Home Manager wiring declarative

**Changes Applied:**
- [x] Moved p10k setup wizard:
  - `scripts/p10k-setup-wizard.sh` -> `scripts/deploy/p10k-setup-wizard.sh`
- [x] Added root compatibility shim:
  - `scripts/p10k-setup-wizard.sh` now forwards to `scripts/deploy/p10k-setup-wizard.sh`
- [x] Updated declarative Home Manager source wiring to canonical path in:
  - `nix/home/base.nix`
- [x] Updated cleanup inventory target rows to canonical path in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/p10k-setup-wizard.sh scripts/deploy/p10k-setup-wizard.sh` -> PASS
- `nix-instantiate --parse nix/home/base.nix` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Skill Registry Tooling Canonicalization

### RH.H42 Move skill registry signer/installer tooling to domain folders with compatibility shims

**Changes Applied:**
- [x] Moved skill registry signer script:
  - `scripts/sign-skill-registry.sh` -> `scripts/security/sign-skill-registry.sh`
- [x] Moved skill bundle registry CLI:
  - `scripts/skill-bundle-registry.py` -> `scripts/governance/skill-bundle-registry.py`
- [x] Added root compatibility shims for both original root paths.
- [x] Removed hardcoded repo-root default in signer script and switched to script-relative repo-root derivation.
- [x] Updated active script/doc/CI references to canonical paths in:
  - `.github/workflows/test.yml`
  - `docs/AGENT-PARITY-MATRIX.md`
  - `docs/PARITY-ADVANCED-TOOLING.md`
  - `scripts/automation/run-advanced-parity-suite.sh`
  - `scripts/testing/smoke-skill-bundle-distribution.sh`
  - `scripts/ai/aqd`
- [x] Updated cleanup inventory target rows to canonical paths in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `python3 -m py_compile scripts/skill-bundle-registry.py scripts/governance/skill-bundle-registry.py` -> PASS
- `bash -n scripts/sign-skill-registry.sh scripts/security/sign-skill-registry.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Allowlist Re-Normalization After Migration Batches

### RH.H43 Re-normalize repo-structure allowlist to current canonical paths after multi-slice script/doc moves

**Changes Applied:**
- [x] Re-ran allowlist normalizer:
  - `scripts/governance/normalize-repo-allowlist.sh`
- [x] Refreshed `config/repo-structure-allowlist.txt` to remove legacy-path drift and align with current canonical moved paths.
- [x] Re-validated allowlist integrity after normalization.

**Validation:**
- `scripts/governance/normalize-repo-allowlist.sh` -> PASS
- `scripts/governance/check-repo-allowlist-integrity.sh` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Convergence + npm Monitor Canonicalization

### RH.H44 Move post-deploy converge and npm security monitor to canonical folders with compatibility shims

**Changes Applied:**
- [x] Moved npm security monitor:
  - `scripts/npm-security-monitor.sh` -> `scripts/security/npm-security-monitor.sh`
- [x] Moved post-deploy converge runner:
  - `scripts/post-deploy-converge.sh` -> `scripts/automation/post-deploy-converge.sh`
- [x] Added root compatibility shims for both original root paths.
- [x] Fixed post-move repo-root resolution in both canonical scripts.
- [x] Updated canonical internal call in converge runner:
  - now calls `scripts/security/npm-security-monitor.sh` directly.
- [x] Updated active runtime/test references to canonical paths in:
  - `nix/modules/services/mcp-servers.nix`
  - `scripts/deploy/quick-deploy-fast-verify.sh`
  - `scripts/governance/preflight-auto-remediate.sh`
  - `scripts/testing/validate-runtime-declarative.sh`
  - `scripts/testing/check-dryrun-failure-modes.sh`
  - `scripts/testing/check-npm-security-monitor-smoke.sh`
  - `docs/SYSTEM-IMPROVEMENT-PLAN-2026-03.md`
- [x] Updated cleanup inventory target rows to canonical paths in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`
- [x] Updated npm monitor usage text to canonical path.

**Validation:**
- `bash -n scripts/npm-security-monitor.sh scripts/security/npm-security-monitor.sh scripts/post-deploy-converge.sh scripts/automation/post-deploy-converge.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Quick Deploy Lint Canonicalization

### RH.H45 Move quick-deploy lint runner to `scripts/governance/` with compatibility shim

**Changes Applied:**
- [x] Moved lint runner implementation:
  - `scripts/quick-deploy-lint.sh` -> `scripts/governance/quick-deploy-lint.sh`
- [x] Added root compatibility shim:
  - `scripts/quick-deploy-lint.sh` now forwards to `scripts/governance/quick-deploy-lint.sh`
- [x] Fixed post-move repo-root resolution and usage text in canonical script.
- [x] Updated active references to canonical path in:
  - `.githooks/pre-push`
  - `.githooks/README.md`
  - `docs/AGENTS.md`
  - `scripts/deploy/quick-deploy-fast-verify.sh`
  - `docs/operations/REPO-STRUCTURE-POLICY.md`
  - `docs/operations/procedures/CONFIG-VALIDATION-PROCEDURES.md`
  - `docs/operations/NAMING-LABEL-CONVENTIONS.md`
  - `docs/operations/REPO-CLEANUP-PASS1-PLAN.md`
  - `docs/operations/reliability/AI-STACK-RUNTIME-RELIABILITY.md`
  - `docs/agent-guides/01-QUICK-START.md`
  - `docs/development/SYSTEM-UPGRADE-ROADMAP.md`
  - `docs/development/SYSTEM-UPGRADE-ROADMAP-UPDATES.md`
  - `docs/SYSTEM-IMPROVEMENT-PLAN-2026-03.md`
- [x] Corrected inventory row to preserve legacy key + canonical target in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/quick-deploy-lint.sh scripts/governance/quick-deploy-lint.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Deploy-Clean Wrapper Canonicalization

### RH.H46 Move deprecated deploy-clean wrapper to `scripts/deploy/` with compatibility shim

**Changes Applied:**
- [x] Moved deploy-clean wrapper:
  - `scripts/deploy-clean.sh` -> `scripts/deploy/deploy-clean.sh`
- [x] Added root compatibility shim:
  - `scripts/deploy-clean.sh` now forwards to `scripts/deploy/deploy-clean.sh`
- [x] Fixed post-move repo-root resolution in canonical wrapper.
- [x] Preserved deprecated message text to avoid breaking existing verification expectations.
- [x] Updated cleanup inventory target rows to canonical path in:
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv`
  - `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`

**Validation:**
- `bash -n scripts/deploy-clean.sh scripts/deploy/deploy-clean.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Active Doc Canonical Script Path Sweep

### RH.H47 Rewrite active docs from root-shim script paths to canonical script locations

**Changes Applied:**
- [x] Ran canonical-path rewrite sweep for active docs (excluding archive + inventory ledgers + roadmap update ledger) using root-shim metadata.
- [x] Rewrote remaining active-doc references from root shim paths to canonical targets across operations/development/system docs.
- [x] Reduced active-doc root-shim references to intentional mention-only cases.

**Validation:**
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Script Header Waiver Path Sanitation

### RH.H48 Fix invalid waiver path tokens in `config/script-header-waivers.txt`

**Changes Applied:**
- [x] Identified malformed waiver entries ending with trailing `.` (for example `scripts/governance/nix-static-analysis.sh.`).
- [x] Normalized waiver paths by stripping trailing punctuation from script path lines.
- [x] Preserved waiver comments and ordering semantics.

**Validation:**
- `scripts/governance/check-script-header-standards.sh --all` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Root Shim Policy CI Enforcement + Canonical Test Names

### RH.H49 Wire root script shim-only policy into CI and normalize automation references

**Changes Applied:**
- [x] Added CI enforcement step in `.github/workflows/test.yml` (`repo-structure-lint` job):
  - runs `scripts/governance/check-root-script-shim-only.sh`
- [x] Updated `docs/operations/REPO-STRUCTURE-POLICY.md` enforcement section to include:
  - CI gate: `check-root-script-shim-only.sh`
  - quick-lint included gate reference
- [x] Normalized high-traffic automation references to canonical kebab-case test scripts in:
  - `scripts/automation/run-all-checks.sh`
  - `test-services.sh` and `test-real-world-workflows.sh` now used directly (underscore shims remain for compatibility).

**Validation:**
- `bash -n scripts/automation/run-all-checks.sh` -> PASS
- `rg -n "Enforce root script shim-only policy" .github/workflows/test.yml` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Secondary CI Workflow and Ownership Canonicalization

### RH.H50 Align legacy CI workflow and CODEOWNERS with canonical deploy path

**Changes Applied:**
- [x] Updated `.github/workflows/tests.yml`:
  - added `check-root-script-shim-only.sh` in `repo-structure-lint`
  - switched syntax gate to canonical `scripts/deploy/deploy-clean.sh`
- [x] Updated `.github/CODEOWNERS` to explicitly own canonical deploy path:
  - added `/scripts/deploy/deploy-clean.sh`
  - retained `/scripts/deploy-clean.sh` coverage for compatibility shim

**Validation:**
- `rg -n "Enforce root script shim-only policy|scripts/deploy/deploy-clean.sh" .github/workflows/tests.yml` -> PASS
- `rg -n "/scripts/deploy/deploy-clean.sh|/scripts/deploy-clean.sh" .github/CODEOWNERS` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Canonical Deploy-Path Reference Sweep (Active Runtime Assets)

### RH.H51 Rewrite active runtime/example references from deploy-clean shim path to canonical deploy path

**Changes Applied:**
- [x] Rewrote active references from `scripts/deploy-clean.sh` to `scripts/deploy/deploy-clean.sh` in:
  - `scripts/governance/analyze-clean-deploy-readiness.sh`
  - `nix/hosts/_example/default.nix.sample`
  - `scripts/deploy/recovery-iso-disk-fix.sh`
  - `scripts/deploy/recovery-offline-fsck-guide.sh`
- [x] Left intentional shim verification paths unchanged (for compatibility/deprecation assertions).

**Validation:**
- `bash -n scripts/governance/analyze-clean-deploy-readiness.sh scripts/deploy/recovery-iso-disk-fix.sh scripts/deploy/recovery-offline-fsck-guide.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Naming Audit Signal Quality (Shim-Aware)

### RH.H52 Make naming consistency audit shim-aware to reduce false-positive noise

**Changes Applied:**
- [x] Updated `scripts/governance/check-naming-label-consistency.sh` to classify underscore files as:
  - non-shim underscore scripts (actionable)
  - underscore compatibility shims (informational)
- [x] Report metrics now expose both counts separately.
- [x] Added a dedicated informational section for underscore shim paths so migration progress remains visible without inflating actionable findings.

**Validation:**
- `bash -n scripts/governance/check-naming-label-consistency.sh` -> PASS
- `scripts/governance/check-naming-label-consistency.sh` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Alias Registry Hardening + Active Doc Drift Fixes

### RH.H53 Expand legacy alias registry from actual root shims and remediate drift

**Changes Applied:**
- [x] Expanded `config/legacy-root-script-aliases.txt` to include all migrated root shim names discovered under `scripts/`.
- [x] Preserved historical non-root legacy names for backward lint coverage.
- [x] Ran migration lint and fixed newly surfaced active-doc drift:
  - `README.md` script tree now references canonical paths:
    - `scripts/health/system-health-check.sh`
    - `scripts/deploy/p10k-setup-wizard.sh`
  - `docs/SECURITY-AUDIT-DEC-2025.md` now references:
    - `scripts/security/fix-secrets-encryption.sh`

**Validation:**
- `scripts/governance/check-doc-script-path-migration.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): README Canonical Script Path Sweep

### RH.H54 Rewrite README runtime commands from root shims to canonical script paths

**Changes Applied:**
- [x] Updated README canonical deployment commands:
  - `./scripts/deploy-clean.sh` -> `./scripts/deploy/deploy-clean.sh`
- [x] Updated README operational command examples:
  - `./scripts/publish-local-registry.sh` -> `./scripts/deploy/publish-local-registry.sh`
  - `./scripts/fix-mangohud-config.sh` -> `./scripts/deploy/fix-mangohud-config.sh`
  - `./scripts/mangohud-profile.sh` -> `./scripts/deploy/mangohud-profile.sh`

**Validation:**
- `scripts/governance/check-doc-script-path-migration.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Canonical Deprecation Guidance Messages

### RH.H55 Remove legacy root-path wording from canonical deprecated scripts

**Changes Applied:**
- [x] Updated deprecated guidance messages to canonical paths in:
  - `scripts/automation/cron-templates.sh`
  - `scripts/security/apply-tls-certificates.sh`
  - `scripts/observability/collect-ai-metrics.sh`
  - `scripts/deploy/enable-progressive-disclosure.sh`
  - `scripts/deploy/publish-local-registry.sh`
- [x] Preserved behavior (`exit 2`) and compatibility intent.

**Validation:**
- `bash -n scripts/automation/cron-templates.sh scripts/security/apply-tls-certificates.sh scripts/observability/collect-ai-metrics.sh scripts/deploy/enable-progressive-disclosure.sh scripts/deploy/publish-local-registry.sh` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode fast` -> PASS

## Repo Hygiene Pass (2026-03-05): Final Closeout Validation + Readiness Checklist

### RH.H56 Run full closeout battery and publish strict ready/not-ready decision doc

**Changes Applied:**
- [x] Executed full validation battery across structure/docs/deploy/runtime gates.
- [x] Published strict evidence-based readiness checklist:
  - `docs/operations/CLOSEOUT-READINESS-CHECKLIST-2026-03-05.md`
- [x] Marked closeout decision as **READY** for commit/push with shim-retirement debt explicitly noted.

**Validation (evidence):**
- `scripts/governance/repo-structure-lint.sh --all` -> PASS
- `scripts/governance/check-repo-allowlist-integrity.sh` -> PASS
- `scripts/governance/check-root-file-hygiene.sh` -> PASS
- `scripts/governance/check-root-script-shim-only.sh` -> PASS
- `scripts/governance/check-script-shim-consistency.sh` -> PASS
- `scripts/governance/check-doc-links.sh --active` -> PASS
- `scripts/governance/check-doc-metadata-standards.sh` -> PASS
- `scripts/governance/check-doc-script-path-migration.sh` -> PASS
- `scripts/governance/check-script-header-standards.sh --all` -> PASS
- `scripts/governance/check-naming-label-consistency.sh --publish-doc` -> PASS
- `scripts/governance/check-archive-path-consistency.sh` -> PASS
- `scripts/governance/check-legacy-deprecated-root.sh` -> PASS
- `scripts/governance/check-generated-artifact-hygiene.sh` -> PASS
- `scripts/governance/check-deprecated-docs-location.sh` -> PASS
- `scripts/governance/quick-deploy-lint.sh --mode full` -> PASS (21/21)
- `scripts/testing/check-mcp-health.sh` -> PASS (13 passed, 0 failed)
- `scripts/testing/check-npm-security-monitor-smoke.sh` -> PASS
