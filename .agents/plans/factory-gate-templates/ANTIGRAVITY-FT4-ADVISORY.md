# Antigravity Advisory Review — FT-4 Non-Destructive Factory Retrofit

**Round / Item**: `ft4-factory-retrofit-advisory-20260915`  
**Role**: Independent Architecture / Security / Software-Factory Advisory Reviewer  
**Subject Commit**: `3e7221e4e537c4644261d4422d4a8c60ca0d0ec1`  
**Reviewed Subject Diff SHA-256**: `097e9ad4e9a11a0abc61d819e3d781a66303c6270c1eea7b16458673d73668b3`  
**Target Output**: `.agents/plans/factory-gate-templates/ANTIGRAVITY-FT4-ADVISORY.md`  
**Advisory Disposition**: **PASS (Confirmatory Acceptance)**

---

## 1. Executive Assessment

The FT-4 implementation establishes a provably non-destructive, preview-gated retrofit mechanism (`aqd workflows retrofit` / `factory_gate_install.py`) for existing repositories (brownfield adoption). 

It resolves critical safety requirements identified in [`.agents/plans/factory-gate-templates/FT4-NEXT-SLICE-BRIEF.md`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/plans/factory-gate-templates/FT4-NEXT-SLICE-BRIEF.md) and [`.agents/plans/factory-gate-templates/FT4-REVIEW-R0.md`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/plans/factory-gate-templates/FT4-REVIEW-R0.md):
1. Mandatory preview-first workflow requiring explicit `--confirm-retrofit <digest>`.
2. Stale-preview refusal: changing scanner availability, target files, or partition layout immediately stales confirmation before any write occurs.
3. Strict preservation of existing project instructions, CI pipelines, and local Git hooks.
4. Faithful hook delegation: original hooks execute with preserved `stdin`, arguments, working directory, and exit codes prior to factory checks.

---

## 2. Invariant & Security Review

### A. Preview-First & Stale Confirmation Refusal
* `aqd workflows retrofit` defaults to a read-only preview. It cannot perform writes without `--confirm-retrofit <digest>`.
* The confirmation digest is constructed from canonical, length-framed JSON records encompassing file path, type, mode, and content digest.
* Empirical regression tests prove that altering tool availability (e.g. scanner going from absent to present) or re-partitioning bytes between files invalidates the digest, refusing execution fail-closed.

### B. Backup Integrity & Path Traversal Guards (R1 Correction)
* R0 correctly identified that symlinked `.factory/gate-backups` could allow config escapes.
* In FT-4 R1, backup paths and all ancestor directories are strictly validated before any write. Symlinked archive destinations are unconditionally refused.
* The original `.git/config` is copied byte-for-byte and mode-preserving to `.factory/gate-backups/<digest>/.git-config`.

### C. Non-Destructive Hook Routing & Composition
* Existing executable hooks are moved to a protected factory namespace and wrapped.
* The wrapper routes Git invocations:
  * Executes the original hook first, faithfully preserving Git-supplied command-line arguments, `stdin`, working directory, and non-zero exit codes.
  * If the original hook exits non-zero (e.g., exit code 7), execution halts immediately without running factory checks.
  * Only when the original hook succeeds does the factory gate check proceed.
* Router scripts resolve installed paths independently of `git rev-parse --show-toplevel`, preventing context breakage when invoked directly from `.git`.

### D. Enforcement Collision Refusal
* Rather than silently overwriting or coexisting with conflicting enforcement files (such as an existing `scripts/governance/gate-runner`), the installer detects collisions and refuses the retrofit with a typed failure. This prevents rogue or dummy runners from bypassing new gate obligations.

### E. Observability & Telemetry Parity
* FT-4 adds dashboard card integration for retrofit fixture proofs in [`assets/dashboard.js`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/assets/dashboard.js) and [`dashboard.html`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard.html).
* Telemetry accurately labels the signal as an "isolated existing-project fixture proof" rather than asserting false production target check results.

---

## 3. Validation & Empirical Results

* `python3 scripts/testing/test-factory-gate-retrofit.py`: **PASS**
  * `preview_read_only`: True
  * `confirmation_enforced`: True
  * `originals_preserved`: True
  * `hooks_composed`: True (preserves cwd, args, stdin, and non-zero exit codes)
  * `layout_preserved`: True
  * `collaboration_preserved`: True
  * `unsafe_state_refused`: True (symlinks and external hook paths refused)
  * `layout_confirmation_bound`: True (stale preview rejected)
  * `unsafe_receipt_refused`: True
  * `existing_receipt_preserved`: True
  * `upgrade_idempotent_preserves_user_files`: True
  * `upgrade_preserves_local_gate_configuration`: True
  * `legacy_receipt_migrates_losslessly`: True

---

## 4. Final Verdict

**PASS** — Confirmatory advisory acceptance of FT-4 non-destructive gate retrofit. The implementation satisfies all safety, preservation, and non-destructive criteria required for brownfield repository adoption.
