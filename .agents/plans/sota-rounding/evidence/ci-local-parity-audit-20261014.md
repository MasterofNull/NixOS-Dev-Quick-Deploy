# CI vs local parity audit (2026-10-14, branch feat/durable-mesh-dp3-oncall-daemon)

Local layers examined: `.githooks/pre-commit` (secret regex subset, npm audit on staged manifests, color-echo lint, bash/py/nix parse on STAGED files, `git diff --cached --check`, repo-structure --staged, 9 governance checks, run-focused-ci-checks --pre-commit [114 path-triggered registry checks]); `.githooks/pre-push` (upstream sync + `quick-deploy-lint.sh --mode fast`: repo-structure --all, allowlist, hygiene, doc links/metadata, script headers (changed-vs-pushed-sha), naming, validate-runtime-declarative, self-check, security-audit smokes; NO nix build/eval in fast mode); `tier0-validation-gate.sh --pre-commit` (syntax gates on CHANGED files, repo-structure --staged, script-headers --all, focused CI, roadmap verify, aq-qa phase 0 [freshness/live classes downgraded to WARN], env contract, agent regression suites, tier0.d/*: sops-sync, dep-CVE, pm-tracker, canon drift, etc.). `.pre-commit-config.yaml` only wraps tier0 + pre-archive-scan + generic hooks (not active; core.hooksPath=.githooks).

Local tool versions (this machine) vs CI pins:
| tool | CI | local |
|---|---|---|
| gitleaks | 8.24.3 (curl pin, 2 workflows) | 8.30.1 |
| shellcheck | apt (ubuntu runner) / action master | nix, version not pinned |
| nix | install-nix-action v30 default | 2.34.8 |
| python | 3.11 (tests, coverage, security), 3.12 (sdk), 3.13 (memory-bench) | 3.13.15 |
| statix/deadnix/alejandra | nixpkgs#, channel nixos-25.11 | statix (no --version), deadnix 1.3.2, alejandra 4.0.0 from ~/.nix-profile |
| grype | via aq-closure-scan, nixpkgs from flake.lock | 0.112.0 |
| bats, uv, sbomnix | installed in CI | MISSING locally |
| node | 20 (sdk) | 24.21 |
Note nix_path=channel:nixos-25.11 in CI vs flake.lock nixpkgs 26.05 (only affects `nix shell nixpkgs#statix ...` in nix-static-analysis, which resolves from the *channel*, not the lock).

## Matrix
Legend: PARITY / PARTIAL / MISSING / LOCAL-ONLY. "soft" = cannot fail the job.

### gitleaks.yml `Gitleaks Secret Scan` (push main, PR main, cron Mon)
gitleaks 8.24.3, `.gitleaks.toml`, `detect --no-git` whole working tree, `--exit-code 0` (soft/non-blocking). Local: none (known; fix in flight). Class: MISSING (known).

### security.yml (push main, PR main, weekly cron, dispatch)
| job | tool/scope | fail condition | local | class |
|---|---|---|---|---|
| security-audit (Security Configuration Audit) | `scripts/security/security-audit.sh`, whole tree, `continue-on-error`; then grep for BLOCKING/CRITICAL | exit 1 only if output contains "BLOCKING" | quick-deploy-lint runs "security audit producer/compliance smoke" (different scripts) | PARTIAL, and **dead gate**: security-audit.sh contains neither the string BLOCKING nor CRITICAL and `exit 0` at end, so this job can never fail |
| nix-closure-vuln-scan | nix build toplevel (+solo llama-cpp), sbomnix->grype SARIF, `aq-closure-scan`; fails on build/scanner crash, findings non-blocking | build or scanner error | quick-deploy-lint `--mode full` does a toplevel build (NOT in any hook); sbomnix absent locally; tier0.d/check-dependency-cve.sh only for npm manifests | MISSING in hooks/tier0 (full-mode lint is manual) |
| secrets-scan (Secret Detection) | gitleaks 8.24.3 `--no-git` whole tree, `--exit-code 1`, REQUIRED check | any finding | pre-commit 4-regex subset, staged added lines, uses grep -v for words like test/example/fake | MISSING real equivalent (known) |
| security-summary | summary only | - | - | n/a |

### test.yml "Test & Quality Assurance" (push main/develop/cursor, PR main)
| job | what | CI strictness | local equivalent | class |
|---|---|---|---|---|
| repo-structure-lint | repo-structure-lint --all, allowlist, root hygiene, shim consistency, doc links/metadata/migration, naming audit, archive path, legacy root, generated hygiene, deprecated docs, pre-archive fixture | hard | pre-commit runs 9 of these on tree + repo-structure --staged; pre-push fast lint runs --all variants incl. naming; `test-pre-archive-no-materialization.py` is a focused-CI registry check (path-triggered) | PARITY (pre-push) / PARTIAL (pre-commit staged-only for structure) |
| harness-first-owner-approval | PR-only, needs GITHUB_TOKEN + reviews API | hard | none; cannot run offline | MISSING (inherently remote) |
| skill-governance-lint | check-skill-source-of-truth, lint-skill-external-deps, lint-skill-template | hard | grep of hooks/tier0/registry finds none | MISSING |
| template-placeholder-lint | lint-template-placeholders.sh | hard | none | MISSING |
| flake-validation | `nix flake show`, `nix flake check --offline --no-build`, profile eval smoke, package-count-drift, validate-runtime-declarative | hard | package-count-drift only path-triggered registry check (flake.nix etc.); validate-runtime-declarative in pre-push; flake show/check: nowhere | PARTIAL (flake check MISSING) |
| nix-static-analysis | statix/deadnix/alejandra via `nix-static-analysis.sh --non-blocking` | soft (always exit 0) | not run by hooks; only referenced by a systems-software-health file-exists check | MISSING but CI is soft |
| shellcheck (Shellcheck & Linting) | all git-tracked *.sh, severity warning | soft (`exit 0`) | none (pre-commit has only `bash -n`) | MISSING but soft |
| script-header-standards | check-script-header-standards `--base $BASE --head $SHA` (changed scripts; on PR the head is the merge commit) | hard | pre-push: changed since remote sha; tier0: `--all` | PARITY-ish (different scopes: tier0 --all is stricter, pre-push diff vs remote tip not vs main) |
| syntax | `bash -n` ALL tracked .sh; aq-report contract; metric smoke; PRSI cycle/bootstrap/phase7 contracts; **harness-first static gates (runbook, evidence template, PR evidence gate)**; tool-security-auditor smoke | hard | `bash -n` on staged/changed only; the 6 contract scripts and static gates have NO local runner | PARTIAL / MISSING |
| validate-structure | required-file list | hard | roadmap verification/repo-structure overlap | PARTIAL |
| bats-tests | `tests/run-unit-tests.sh` (bats from apt) | hard | none; bats not installed locally | MISSING |
| smoke-tests | phase inventory, `nixos-quick-deploy.sh --help/--version/--list-phases`, `aqd --version/workflows list/skill validate` | hard | pre-push runs `--self-check` only | PARTIAL |
| harness-sdk-parity | smoke-harness-sdk-packaging (py3.12 + build) | hard | none | MISSING |
| skill-bundle-parity | smoke-skill-bundle-distribution | hard | none | MISSING |
| advanced-parity-tooling | run-advanced-parity-suite | hard | none | MISSING |
| security (Security Scanning) | 1 regex grep (always exit 0, "does not block") + world-writable find | find = hard | none for world-writable; regex subset is also in pre-commit | MISSING (world-writable) |
| build | tag only | - | - | n/a |

### tests.yml "tests"
| job | CI | local | class |
|---|---|---|---|
| repo-structure-lint (+root shim-only) | hard | pre-push fast lint | PARITY |
| flake-first-roadmap-verifier | `bash -n` entrypoints, verify-flake-first-roadmap-completion, rg guard against gitleaks-action | tier0 gate_roadmap_verification | PARTIAL (gitleaks-action guard CI-only, trivial) |
| parity-scorecard-gate | `harness-runner.sh --offline` which itself invokes **tier0 + aq-qa phase 0 in a bare CI env** | tier0 locally runs on full host | PARTIAL: same code, different environment (see failure class 3) |
| unit-tests matrix (aidb, hybrid-coordinator, nixos-docs) | py3.11, `pip install requirements.txt`, `pytest -m "not integration"` w/ cov, hard (rc5 -> skip) | tier0 gate_agent_harness_regression_suites + path-gated registry pytest only; nobody runs the full per-service pytest in a clean pip env | PARTIAL |

### Other workflows
- tests-legacy.yml `Tests`: bats unit tests with `|| exit 0` (soft), integration job loops tests/integration/*.sh (hard if any exist). Local: none. MISSING, mostly soft.
- validate-shell-scripts.yml: lint-color-echo-usage + validate-echo-colors (hard), ShellCheck severity warning (continue-on-error). Local: pre-commit `lint-color-echo --staged` = PARITY for the lint; `validate-echo-colors.sh` MISSING.
- shellcheck.yml: continue-on-error, severity error, scripts/ only. MISSING, soft.
- nix-build.yml `Build NixOS Configuration`: `nix flake check --all-systems || true` (soft; always logs "Unsupported system: aarch64-linux" error noise), solo llama-cpp build, toplevel build (hard). Local: only `quick-deploy-lint --mode full` (manual). MISSING from hooks.
- test-coverage.yml `Targeted Coverage`: py3.11 + uv, run-targeted-coverage.sh (hard). Local none. MISSING.
- memory-benchmarks.yml: path-filtered (aidb/**), py3.13, memory-regression-tests.py. Local none. MISSING.
- harness-sdk-release.yml: PR path-filtered (hybrid-coordinator/**), version parity + packaging smoke + python build/npm pack. Local none. MISSING.
- rust-tests.yml.disabled: n/a.

### LOCAL-ONLY (fine)
npm audit on staged manifests, color-echo staged lint, `git diff --cached --check`, integration_guard, main-checkout guard, shallow-merge guard, upstream sync check, tier0.d (sops-sync, canon drift, lane-hook parity, agent-instruction parity, pm-tracker, suspend-resume, color-echo, deleted-links, frontier-fold), env/cross-surface contracts, llama payload SSOT, ~100 path-triggered registry checks, aq-qa phase 0 live-service checks.

## Cross-cutting findings
1. Merge-commit semantics: every `pull_request` workflow uses the default checkout of `refs/pull/N/merge` (base+head). Local hooks only see the branch HEAD plus a *fetched* `origin/main`; pre-push does not merge or rebase-check against current main (its sync check is against the branch upstream, not main). Tests that pass on branch but break after base moved are invisible locally.
2. Scope asymmetry: local pre-commit and tier0 syntax/focused-CI gates look at STAGED or CHANGED files only; CI scans ALL tracked files (`bash -n` all, gitleaks whole tree, shellcheck all, `--all` lint). Pre-existing/interaction breakage appears only in CI.
3. Bare-env asymmetry: CI runs tier0/QA phase 0 and pytest in a minimal pip env (py3.11, only requirements.txt deps); local runs in the Nix dev env with everything installed and live services up.
4. Dead gate: CI `Check audit results` greps for BLOCKING/CRITICAL, which security-audit.sh never prints.
5. CI-skipped-on-tool-absence has the reverse form locally: `run-focused-ci-checks` SKIPs (exit 0) when `require_tool` missing, `gate_*` JS/TS/SQL/YAML SKIP when node/tsc/PyYAML missing, bats/uv/sbomnix missing => any dependent check is silently unrun.
6. Soft-in-CI/hard-locally: none material (CI is generally softer: shellcheck x3, nix-static-analysis, regex secrets, tests-legacy bats, `flake check || true`). Hard-in-CI/not-local: see MISSING rows. Several soft CI checks mean local also not needing them; but they also give no signal anywhere.

## CI failure history (600 runs, 2026-10-11..13; 13 non-success)
| # | class | runs | would local gates catch it? |
|---|---|---|---|
| 1 | Secret Detection (gitleaks) | 38462693433 (PR #506) | NO (known) |
| 2 | harness-first PR evidence gate: "high-impact paths changed but no new evidence file added" (test.yml `Syntax Validation` step) | 38344319393, 38099502322, 38099442274 | NO: `check-harness-first-static-gates.sh` not wired into pre-push/tier0 (helped by c78a174e which auto-detects branches, but nothing calls it) |
| 3 | tier0 -> aq-qa 0.10.67 (DP-4 streaming canvas) failed in CI's bare env (`test-pi-agent-streaming-ui.py` needs FastAPI etc.; fixed by 3d241071 minimal-app isolation) | 38433857151 (tests/parity-scorecard-gate) | NO: passes locally in the full Nix env; env-dependent. The same tier0 code runs in CI so a clean-venv run would catch it |
| 4 | Nix closure/build failure: nixpkgs `xdg-desktop-portal-1.20.4` check phase fails in sandbox -> dbus-1 -> system-path -> toplevel (also `Unsupported system: aarch64-linux` noise from `flake check --all-systems || true`, soft) | 38340140806/885, 38340130321/129831, 38344319319/361, 38344891198/140 | NO: local machine pulls from cache/has it built; hooks never build toplevel. Fix branch fix/cve-overlay-and-branch-reconciliation implies a CVE overlay changed the derivation hash so cache missed |
| 5 | Test & Quality Assurance `Syntax Validation` (same as #2) | see #2 | NO |
Other 570+ runs green; no CI failure was due to shellcheck, structure lint, bats, coverage, or sdk.

## Ranked gaps and minimal fixes
1. (HIGH) harness-first static gates / PR evidence gate: CI-hard, no local runner; failed 3 runs. Fix: add `scripts/testing/check-harness-first-static-gates.sh` to `quick-deploy-lint.sh` fast mode (so pre-push runs it with the same script CI runs).
2. (HIGH) Nix toplevel build / eval not in any local gate; failed 5 runs. A change to flake.lock, overlays, or nix/** can pass hooks. Fix: pre-push runs `nix flake check --no-build --offline` + `nix eval ...toplevel.drvPath` when diff touches `flake.*|nix/**` (path-triggered registry entry); keep full build in `--mode full`/CI. For cache-miss/sandbox-test failures only CI will tell; add `permittedInsecure`/`doCheck=false` overlay review to checklist.
3. (HIGH) Env asymmetry for tier0/QA phase 0 and pytest. Fix: one script `scripts/governance/ci-clean-env.sh` (python venv from the same requirements files, py3.11, PYTHONPATH as CI) used by tests.yml AND by a pre-push option / `aq-ci-local`; or run `harness-runner.sh --offline` under `env -i` + minimal venv.
4. (MED, wrong-pass-both) security-audit "Check audit results" dead grep. Fix: make security-audit.sh emit/return non-zero on blocking findings and have the workflow use its exit code (drop continue-on-error); same script already usable locally.
5. (MED) CI-only hard checks with no local runner: skill-governance (3 scripts), template-placeholder, aq-report/PRSI contracts (6 scripts), tool-security-auditor smoke, bats, SDK parity, skill-bundle, advanced-parity-suite, world-writable find, validate-echo-colors, aqd smoke, unit-test matrix, targeted coverage. Fix: single manifest `config/ci-checks.json` {id, cmd, scope}; test.yml loops over it via `scripts/governance/run-ci-checks.sh --all`, pre-push runs `--changed` (path-triggered) from the same file; tier0.d check fails if a workflow `run:` references a script not in the manifest.
6. (MED) Tool pin drift: gitleaks 8.24.3 vs 8.30.1, py 3.11 vs 3.13, nix, channel 25.11 vs lock 26.05. Fix: `config/tool-pins.json` read by workflows (gitleaks version, python) and a tier0.d check `check-ci-tool-pins.sh` that greps workflows for `GITLEAKS_VERSION=`/`python-version` and compares to `<tool> --version` on PATH (WARN on mismatch in pre-commit, HARD in maintenance).
7. (MED) Merge-commit blindness. Fix: pre-push/`aq-ci-local` runs the manifest checks on a temporary `git merge --no-commit origin/main` worktree (tier0 already has `--staged-isolated` worktree machinery to reuse).
8. (LOW) Staged-only vs whole-tree scope: add full-tree `bash -n` (CI `syntax`) and gitleaks whole-tree scan to `--maintenance`/nightly so drift outside the diff surfaces without CI.
9. (LOW) Silent SKIP when tool missing (bats, uv, sbomnix, node): record skips in tier0 summary as WARN count and make `aq-tool` auto-fetch in the shared script.
10. (LOW/noise) `nix flake check --all-systems || true` always prints the aarch64 error; replace with explicit `--system x86_64-linux` and drop `|| true` so it is a real gate.

Files: workflows /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.github/workflows/*.yml; hooks .githooks/{pre-commit,pre-push}; scripts/governance/{tier0-validation-gate.sh,quick-deploy-lint.sh,run-focused-ci-checks.sh}; config/validation-check-registry.json. Raw logs: /tmp/claude-1000/parity-audit/fail-*.log, runs.json.
