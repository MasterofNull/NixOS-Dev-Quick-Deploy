# Antigravity Advisory Review: FT-1 Portable Factory Gate Bundle

**Task ID**: `ft1-factory-gate-advisory-20260915`  
**Output Target**: `.agents/plans/factory-gate-templates/antigravity-ft1-advisory.md`  
**Candidate Subject**: `templates/factory-gate-bundle/` (commit `44ec2919`)  
**Reviewed Subject Hash**: `743848d961b8220a4487016b24074b95b3750f675cc4bb3170de95f378c75477`  
**Role**: Independent Architecture / Security / Software-Factory Advisory Reviewer  
**Verdict**: `PASS` (Advisory Confirmatory Review)  

---

## 1. Executive Summary & Verification

This advisory review assesses the FT-1 portable factory gate bundle (`templates/factory-gate-bundle/`), which extracts AQ-OS's core governance gates into a standalone, stack-agnostic bundle for greenfield repositories.

Self-test verification was executed directly:
```bash
bash templates/factory-gate-bundle/self-test.sh
# Result: SELF-TEST PASS (12/12 fixture checks passed cleanly)
```

The bundle successfully delivers:
1. **Portable Gate Runner (`gate-runner`)**: Discovers checks dynamically from `checks.d/` with clean exit code semantics.
2. **Deterministic Manifest (`MANIFEST.json`)**: All 35 bundle files are enumerated with SHA-256 digests and target relative paths.
3. **Truthful PM Projection (`pm-tracker/`)**: Projects roadmap status from Git commit evidence and tracker schemas, rejecting unevidenced `SHIPPED` claims.
4. **Commit Hook & Review Binding (`hooks/commit-msg`)**: Validates commit trailers, binding reviews to exact commit hashes and rejecting self-review.

---

## 2. Invariants & Security Architecture Findings

### A. Cooperative vs. Enforced Security Boundary
* **Finding**: Local Git hooks (`hooks/commit-msg`, `hooks/pre-commit`) are **cooperative enforcement mechanisms** within a shared developer environment. A same-user agent or developer can bypass them via `git commit --no-verify` or `core.hooksPath=/dev/null`.
* **Advisory Requirement**: Local hooks must not be documented or relied upon as a cryptographic security boundary. True enforcement requires server-side CI (FT-7) and protected branch rules on the remote repository. FT-1 correctly treats local hooks as developer ergonomics and friction reduction.

### B. WARN vs. HARD Policy Discipline (Rule 21)
* **Finding**: In `gate-runner`, live freshness and expiration checks correctly emit `WARN` during interactive pre-commit runs, while contract regressions and unconfigured required checks fail `HARD`. This prevents gate fatigue and avoids blocking commits on unrelated external time-decay.

### C. Greenfield vs. Brownfield Seams (FT-1 vs. FT-2/FT-4)
* **Finding**: FT-1 is clean for greenfield initialization. It does not attempt in-place retrofitting of existing non-empty repositories with custom hooks or conflicting CI definitions. That boundary is properly isolated to FT-4 (non-destructive retrofit) and FT-2 (stack adapters).

---

## 3. Final Advisory Verdict

**PASS** (Confirmatory advisory approval of the FT-1 bundle architecture and self-test verification).
