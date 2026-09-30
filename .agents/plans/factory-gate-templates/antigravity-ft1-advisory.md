# Antigravity Advisory Review — FT-1 Portable Factory Gate Bundle

**Round / Item**: `ft1-factory-gate-advisory-20260915`  
**Role**: Independent Architecture / Security / Software-Factory Advisory Reviewer  
**Subject Commit**: `44ec2919db07eac51cae2db73e59af6e27ed08c6`  
**Reviewed Subject Diff SHA-256**: `743848d961b8220a4487016b24074b95b3750f675cc4bb3170de95f378c75477`  
**Target Output**: `.agents/plans/factory-gate-templates/antigravity-ft1-advisory.md`  
**Advisory Disposition**: **PASS (Confirmatory Acceptance)**

---

## 1. Executive Assessment

The FT-1 bundle (`templates/factory-gate-bundle/`) successfully decouples the universal quality, verification, and governance apparatus of this harness from host-specific NixOS/stack implementations. It codifies a portable, self-testing, and stack-adaptable factory gate system that can be stamped into greenfield and brownfield repositories.

The design faithfully implements the requirements of [`.agent/PROJECT-FACTORY-GATE-TEMPLATES-PRD.md`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agent/PROJECT-FACTORY-GATE-TEMPLATES-PRD.md), including manifest-backed file tracking, hook-driven trunk protection with staged commit-hash binding, and anti-gaming PM projection.

---

## 2. Invariant & Architecture Review

### A. Universal Framework vs. Stack Adaptation
* The portable framework components (`gate-runner`, `hooks/commit-msg`, `hooks/pre-commit`, `repo-structure-lint`, `pm-tracker/`, `agent-scaffolding/`, and `self-test.sh`) are properly genericized.
* Hardcoded harness assumptions (such as `/run/secrets/`, specific service UDS paths, and Nix daemon bindings) are kept out of the core gate-runner.
* Stack-adaptive checks are cleanly isolated into `checks.d/`, allowing FT-2/FT-3 to configure Python, Node, Rust, or Go checks without mutating the runner core.

### B. Manifest Derivation & Refreshability
* `MANIFEST.json` explicitly catalogs all 36 bundle files with exact permissions, relative paths, and SHA-256 digests.
* The self-test proves clean extraction, installation into an empty directory, and verification without dangling file references or unmanifested residue.

### C. Truthful PM Projection & Anti-Gaming
* The `pm-tracker` standard enforces progress projection directly from Git history rather than hand-typed status markers.
* The projector fails closed: `SHIPPED` status strictly requires git commit evidence; malformed schema inputs and negative percentages trigger immediate validation failure.

### D. Review & Hash Binding (Trunk Protection)
* `.githooks/commit-msg` enforces terminal review headers:
  * `Review-Disposition: ACCEPTED`
  * `Reviewed-subject-sha256: <digest>` matching the staged index patch (`git diff --cached`)
  * `Reviewed-by: <identity>` distinct from the author (anti-self-review).
* Unbound reviews, missing trailers, and author self-approval are unconditionally blocked.

### E. WARN-vs-HARD Policy (Rule 21 Alignment)
* The gate-runner strictly distinguishes between code regressions (which block commits) and external freshness/temporal drift (which emit warnings in pre-commit mode and only block during scheduled maintenance audits). This prevents gate gaming while maintaining delivery flow.

### F. Enforcement Boundary Realism (Crucial Grounding)
* **Cooperative Local Enforcement**: Local Git hooks execute within the developer's / agent's current OS user context. They are a guard against drift, accidents, and workflow omissions—not a tamper-resistant security boundary against an agent deliberately bypassing hooks (`git commit --no-verify` or altering `.git/config`).
* **Requirement for FT-7**: True non-bypassable enforcement requires remote CI / protected branch rules or an external authority gate. FT-1 does not make false security claims on this front.

---

## 3. Validation & Empirical Results

* `bash templates/factory-gate-bundle/self-test.sh`: **PASS**
  * Discovers checks and runs pre-commit verification.
  * Verifies stack adapter fixtures.
  * Validates typed `UNCONFIGURED` fail-closed semantics for missing required checks.
  * Tests live vs. freshness severity corollary.
  * Confirms `commit-msg` trunk protection rejects missing, unbound, and self-authored reviews while accepting valid bound reviews.
  * Proves manifest resolves and installs all 36 files into an isolated temporary repo.
  * Confirms PM checker rejects invalid schema inputs and requires git commit evidence.

---

## 4. Final Verdict

**PASS** — FT-1 is confirmed sound as an additive template foundation. Greenfield injection (FT-3) and non-destructive retrofit (FT-4) build upon a robust, verified substrate.
