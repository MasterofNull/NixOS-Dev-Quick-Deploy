# Antigravity Advisory Review: FT-4 Non-Destructive Factory Retrofit

**Task ID**: `ft4-factory-retrofit-advisory-20260915`  
**Output Target**: `.agents/plans/factory-gate-templates/ANTIGRAVITY-FT4-ADVISORY.md`  
**Candidate Subject**: FT-4 Retrofit Implementation (`FT4-IMPLEMENTATION.md`)  
**Role**: Independent Architecture / Security / Software-Factory Advisory Reviewer  
**Verdict**: `PASS_WITH_ADVISORY_OBSERVATIONS` (Advisory Catch-Up Review)  

---

## 1. Executive Summary & Review Scope

This advisory review analyzes the FT-4 retrofit architecture (`aqd workflows retrofit`), which retrofits existing (brownfield) Git repositories with the factory gate bundle without destroying existing project history, Git configuration, or custom hooks.

The review specifically audits the four blocking invariants raised during the R0 review and addressed in R1 hardening:
1. **Backup Destination Ancestor Validation**: Refusal of symlinked `.factory/gate-backups/` or redirected paths.
2. **Length-Framed Content & Configuration Digest**: Preventing hash collision or tool-availability bypasses through structured JSON digest records.
3. **Robust Hook Invocation Context**: Decoupling hook wrapper routing from `git rev-parse --show-toplevel` so hooks triggered from within `.git` receive correct original arguments, stdin, and cwd.
4. **Collision Refusal for Enforcement Components**: Explicitly refusing to overwrite or wrap existing `scripts/governance/gate-runner` implementations that could act as no-op bypasses.

---

## 2. Invariants & Security Architecture Findings

### A. Confirmation Digest & Stale-Preview Refusal
* **Design**: Retrofit execution is strictly gated behind `--confirm-retrofit <digest>`, where `<digest>` is a canonical, length-framed JSON representation of:
  - Pristine bundle hashes
  - Original Git configuration
  - Executable original hooks (mode, path, hash)
  - Preserved target files
  - Planned rendered gate bytes and check configuration
* **Security Finding**: Framing each record by path, type, mode, and content digest completely prevents collision attacks from concatenating file streams. Furthermore, binding external scanner tool availability directly into the confirmation digest guarantees that discovering a new scanner (e.g. Semgrep or Trivy becoming available) stales the preview before any filesystem writes occur.

### B. Symlink Traversal & Backup Protection
* **Security Finding**: Symlink attacks targeting backup destinations (`.factory/gate-backups/<digest>/`) could lead to copying repository Git configuration or secrets outside the target boundary.
* **Hardening Verdict**: R1 properly verifies all ancestor directory paths before writing, strictly disallowing symlinked paths or parent-directory traversal (`..`).

### C. Hook Chaining & Execution Semantics
* **Architecture Finding**: Retrofitting preserves original hooks by wrapping them. The execution order:
  1. Original `pre-commit` executes first with original stdin/arguments.
  2. If original exits 0, factory gate checks execute.
  3. If original fails, execution aborts immediately with the original exit status.
* **Observation**: This preserves existing developer workflows while ensuring factory gates are additive. As noted in FT-1, local hook execution remains cooperative enforcement; true enforcement belongs in remote CI (FT-7).

---

## 3. Final Advisory Verdict

**PASS_WITH_ADVISORY_OBSERVATIONS** (Architecture and R1 hardening invariants are verified sound and safe for brownfield adoption).
