# Security-check coverage review — 2026-10-02

## Status and scope

**Status:** Diagnosis and recommendations only. No workflow, scanner, or policy changes were made or authorized in this note.

**Scope:** Explain the Trivy removal and record the current CI security-check gaps and their likely next steps.

The removal was recorded in commit `7a5bb5fc29f71405efff06463c3bdf62ab6d48a7`. The prior container scans did not represent the deployed Nix closure; the replacement scans the deployed closure with `sbomnix` and Grype. This removes a mismatched artifact scan rather than eliminating the deployed-closure vulnerability scan. Current high/critical findings are nonblocking, so those findings are reported but do not currently prevent merging.

## Findings

- **Gitleaks behavior is inconsistent and does not establish history coverage.** `.github/workflows/security.yml` runs Gitleaks with `--no-git` and exits 1 on the current files. The standalone `.github/workflows/gitleaks.yml` also uses `--no-git`, exits 0, and is nonblocking. `fetch-depth: 0` does not change the meaning of `--no-git`; these runs scan current content rather than repository history.
- **SARIF upload is not source analysis.** `upload-sarif` uploads a SARIF artifact for display; by itself it does not run CodeQL analysis.
- **Source SAST is absent.** No CodeQL source-analysis workflow or equivalent source SAST is configured.
- **GitHub Actions workflow security analysis is absent.** No GHA-specific analyzer such as zizmor is configured.
- **Dependency/artifact coverage is specifically the deployed Nix closure.** The `sbomnix` + Grype path is the relevant vulnerability scan for that artifact. Adding Trivy for the same inputs would duplicate coverage without addressing the source or workflow-analysis gaps.

## Issue record

- **Status:** Open — policy and coverage gaps remain.
- **Scope:** CI security checks in `.github/workflows/security.yml` and `.github/workflows/gitleaks.yml`, plus deployed Nix closure scanning.
- **Root cause:** Scanner coverage is split across workflows with different Gitleaks outcomes; `--no-git` limits those runs to current files, and SARIF upload has been conflated with running a source analyzer. The deployed closure scan reports high/critical findings without making them merge-blocking.
- **Severity:** Medium. Secret/history, source-code, and workflow risks can escape these checks; existing closure findings are visible but not enforced as a merge gate.
- **Action:** Prioritize a reviewed policy that blocks on *new* findings at an agreed severity while handling existing baseline findings deliberately; establish Gitleaks PR/current-tree and repository-history coverage; then add one source SAST (CodeQL is the recommended first choice) and a GHA workflow analyzer such as zizmor. Do not add a duplicate Trivy vulnerability scan for the same deployed Nix closure unless the artifact/input scope changes.
- **File references:** `.github/workflows/security.yml`; `.github/workflows/gitleaks.yml`; Trivy-removal commit `7a5bb5fc29f71405efff06463c3bdf62ab6d48a7`.

These are recommendations for a separately authorized implementation slice; this note does not authorize changing the workflows or merge policy.
