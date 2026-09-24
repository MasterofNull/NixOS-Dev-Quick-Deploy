# Independent Advisory Code Review: Portable Factory Deployment Contract

**Task ID**: `factory-deployment-contract-review-20260918`  
**Output Target**: `.agents/plans/factory-gate-templates/DEPLOYMENT-CONTRACT-REVIEW-20260918.md`  
**Reviewer Lane**: Antigravity IDE (Independent Advisory Node)  
**Candidate Worktree**: `/tmp/aq-factory-deployment-contract`  
**Candidate Base**: `d0b814cb`  
**Raw Staged Binary Diff SHA-256**: `1dab2288f449fb45bb24b0a4174696259d7eb3fe5297773ce57bf28644b338a9`  
**Full-Index Binary Diff SHA-256**: `70508413e509fe90fc7cb08d9d85b843802d484923cdfeb0da45dd9c6133096b`  
**Governing Documents**:
- `.agent/PROJECT-FACTORY-GATE-TEMPLATES-PRD.md` (2026-09-18 continuation)
- `.agents/plans/factory-gate-templates/DEPLOYMENT-CONTRACT-IMPLEMENTATION.md`
- `.agent/collaboration/DEPLOYMENT-CONTRACT-HANDOFF.md`  
**Role**: Software Architecture · Factory Governance · Systems Security · Verification  
**Mode**: Read-only independent advisory review (no staging, no commits, no HEAD changes, no consumer file mutation, no agent dispatches)

---

## 1. Executive Summary & Review Scope

This independent technical review audits the frozen deployment contract candidate staged in `/tmp/aq-factory-deployment-contract`. The candidate resolves critical defects identified during the in-situ factory test run (findings FF-001, FF-002, and FF-005), specifically:
1. Eliminating artificial `src/tests` assumptions by generating dynamic layout policies for legitimate brownfield structures.
2. Removing unrendered `{{PLACEHOLDER}}` command tokens from agent-facing contract files while keeping required checks fail-closed.
3. Seeding required collaboration paths (`PULSE.log`, `RESUME.json`, `issues-backlog.md`, `archive/`) during install/retrofit without clobbering existing files.
4. Strictly binding preview digests to planned directory states and rendered bytes.
5. Hardening destination paths against nested symlink traversal.

### Binary Diff Integrity
- `git diff --cached --binary`:
  `1dab2288f449fb45bb24b0a4174696259d7eb3fe5297773ce57bf28644b338a9` (verified exact match to task drop).
- `git diff --cached --binary --full-index --no-ext-diff`:
  `70508413e509fe90fc7cb08d9d85b843802d484923cdfeb0da45dd9c6133096b` (verified exact match to integrator record).

---

## 2. Invariants & Technical Evaluation

### A. Brownfield Layout Policy & Undeclared Root Rejection (FF-001 Resolution)
* **Code Location**: `scripts/ai/lib/factory_gate_install.py:layout_policy()` and `templates/factory-gate-bundle/repo-structure.conf.tmpl`
* **Analysis**:
  - Previously, `repo-structure.conf.tmpl` unconditionally enforced `required=src` and `required=tests`, which immediately failed any brownfield project with flat or alternative directory structures.
  - The implementation now evaluates `layout_policy(target, entries)` by inspecting the target repository's existing root entries and combining them with the bundle's planned install targets.
  - If `src/` or `tests/` directories exist, they are preserved as required. If absent, they are omitted from `required=`, allowing flat or polyglot layouts to pass.
  - All existing root paths plus installer-created directories (`.factory`, `.githooks`, `.agent`, `.agents`, etc.) are declared in `allowed_top=`.
  - **Adversarial Invariant Verified**: Introducing a new undeclared top-level directory after the snapshot is taken causes `hard-10-repo-structure` to fail closed. The policy permits existing legitimate roots without permitting arbitrary undeclared sprawl.

### B. Non-Executable Agent Contract Notices (FF-002 Resolution)
* **Code Location**: `templates/factory-gate-bundle/agent-scaffolding/AGENTS.md.tmpl` and `WORKFLOW-CANON.md.tmpl`
* **Analysis**:
  - The installer previously left unrendered command tokens (e.g. `Test: {{TEST_CMD}}`, `Lint: {{LINT_CMD}}`) in contract files, causing agents to attempt executing raw template tokens.
  - The template files now state explicitly:
    > *"Required checks are fail-closed until explicitly configured. Read the install receipt and the gate output for the configuration status; this notice is not an executable command."*
  - In `WORKFLOW-CANON.md.tmpl`, step 5 explicitly instructs agents:
    > *"If the gate reports an unconfigured required check, obtain explicit configuration; this notice is not an executable command."*
  - **Adversarial Invariant Verified**: Notice prose is completely inert documentation. Gate runners evaluate check configuration status directly, remaining fail-closed (`CONFIGURATION_BLOCKED`) until explicitly configured, while preventing agents from parsing or executing placeholder strings.

### C. Preview-to-Install State & Byte Binding
* **Code Location**: `scripts/ai/lib/factory_gate_install.py:retrofit_preview()` and `retrofit_install()`
* **Analysis**:
  - The preview digest calculation (`fingerprint`) now includes:
    - `directories`: The canonical list of all planned directory creations (`planned_directories(write_paths)`).
    - `rendered_plan`: Complete mapping of relative paths to rendered SHA-256 byte digests (`rendered_plan_digests()`).
    - `target_content_sha256`: Target filesystem content digest.
  - Both `retrofit_preview` and `retrofit_install` invoke `rendered_outputs()` with identical `values` derived from `layout_policy()`.
  - **Adversarial Invariant Verified**: The exact bytes and directories previewed are identical to those written upon confirmation. Any target file drift, new root path, or altered check command stales the confirmation digest, raising `CONFIRMATION_REQUIRED` / `PREVIEW_DIGEST_MISMATCH`.

### D. Collaboration Artifact Seeding & Safety (FF-005 Resolution)
* **Code Location**: `scripts/ai/lib/factory_gate_install.py:COLLABORATION_SEEDS`
* **Analysis**:
  - Seed templates are defined for:
    - `.agent/collaboration/PULSE.log`
    - `.agent/collaboration/RESUME.json`
    - `.agent/memory/issues-backlog.md`
    - `.agent/archive/.gitkeep`
  - When installed or retrofitted, existing files are preserved byte-for-byte; seed files are written only when destination does not exist.
  - `safe_write_path` verifies all ancestor paths, rejecting any destination containing symlink components, parent directory traversal (`..`), or pointing outside `target_root`.
  - **Adversarial Invariant Verified**: Required collaboration paths exist upon installation, preventing compliant agents from failing on missing audit directories, while symlink attacks against collaboration files are refused fail-closed (`TRAVERSAL_REFUSED`).

### E. Handoff Integrity & Non-Author Role Separation
* **Location**: `.agent/collaboration/DEPLOYMENT-CONTRACT-HANDOFF.md`
* **Verification**:
  - The staged handoff file accurately reflects candidate status: authored by `factory_deployment_contract`, explicitly declaring that independent review and canonical validation remain pending.
  - Authority is properly rooted in the owner's 2026-09-18 continuation sequence.
  - Next steps truthfully state that canonical Tier0 and FT-5 execution evidence are required before any deployment claims can be made.

---

## 3. Hermetic Verification Results

The candidate was evaluated using focused disposable test suites executed directly in `/tmp/aq-factory-deployment-contract`:

1. **`python3 scripts/testing/test-factory-gate-install.py`**:
   ```json
   {
     "hooks_block_bad_commit": true,
     "tracker_discovered": true,
     "collision_preserved": true,
     "unconfigured_blocked": true,
     "collaboration_seeded": true,
     "layout_enforced": true,
     "agent_notice_safe": true
   }
   ```
   *Result*: **7/7 PASS** (All installation and greenfield safety properties verified).

2. **`python3 scripts/testing/test-factory-gate-retrofit.py`**:
   ```json
   {
     "preview_read_only": true,
     "confirmation_enforced": true,
     "originals_preserved": true,
     "hooks_composed": true,
     "layout_preserved": true,
     "collaboration_preserved": true,
     "unsafe_state_refused": true,
     "layout_confirmation_bound": true,
     "unsafe_receipt_refused": true
   }
   ```
   *Result*: **9/9 PASS** (All brownfield retrofit, layout preservation, and symlink refusal properties verified).

### Disclosure of Unexecuted Validation
- Full repository-wide `scripts/governance/tier0-validation-gate.sh --pre-commit` was not run inside the isolated candidate worktree to avoid host resource contention during advisory review. Full Tier0 gate execution remains an integration gate for the integrator on `main`.

---

## 4. Minor Advisory Observations (Non-Blocking)

1. **Top-Level Unsafe Path Error Representation**:
   When an unsafe path traversal is detected in `safe_write_path()`, it raises `RuntimeError` or returns a blocker string. In interactive CLI flows this is clean, but when invoked via JSON APIs it is beneficial to guarantee consistent JSON error formatting (`{"state": "REFUSED", "reason": ...}`).
2. **Pre-Existing Hook Chmod Existence Guard**:
   In `retrofit_install()`, the chmod loops for routed hooks assume files exist in destination. Because `safe_write_path` and `conflict` checks ensure preceding write success, this is safe in practice, but a defensive `.exists()` check is recommended for future hardening.

---

## 5. Conclusion & Advisory Verdict

The candidate staged in `/tmp/aq-factory-deployment-contract` (diff SHA-256 `1dab2288f449fb45bb24b0a4174696259d7eb3fe5297773ce57bf28644b338a9`) resolves the core brownfield layout and token rendering issues thoroughly, safely, and without regressions. All focused verification fixtures pass cleanly.

**ADVISORY VERDICT: PASS**  
*(Non-binding independent advisory review. Integration into `main` remains governed by canonical Tier-0 validation and independent integrator verification.)*
