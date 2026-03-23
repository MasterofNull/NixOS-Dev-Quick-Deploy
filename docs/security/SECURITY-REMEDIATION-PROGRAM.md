# Security Remediation Program

Status: draft-working
Owner: codex orchestrator
Started: 2026-03-23
Scope: repo security backlog, AI harness security readiness, NixOS/core-system security workflow maturation

## 1. Objective

Create a repo-grounded security remediation program that:
- reduces the current security scanning backlog in this repository,
- hardens the local AI harness so it can run repeatable tests, evals, and discovery safely,
- establishes evidence-driven pathways for investigating NixOS, kernel-adjacent, driver, and core package issues,
- prepares upstream contribution loops once local triage and validation are mature.

## 2. Scope Lock

In scope:
- repository code scanning findings and false-positive reduction,
- secrets hygiene, dependency audit, Dockerfile/container scan, and service hardening,
- AI harness planning, issue intake, evidence capture, and reviewer-gated workflow use,
- NixOS module and declarative security posture for local services,
- kernel-adjacent and core-system research intake once local repo and harness loops are stable.

Out of scope for the first tranche:
- broad package ecosystem sweeps outside core system priorities,
- unaudited automated upstream submissions,
- destructive history rewrites or secret rotation execution without explicit approval,
- parallelized multi-agent execution beyond current harness limits.

## 3. Constraints And Guardrails

- Never hardcode secrets, tokens, passwords, ports, or service URLs.
- Prefer Nix/declarative fixes before shell/runtime workarounds.
- One logical change per commit.
- All remediation slices need evidence:
  - files changed
  - commands run
  - tests run
  - evidence output
  - rollback note
- Validation gate before commit:
  - `scripts/governance/tier0-validation-gate.sh --pre-commit`
- Validation gate before deploy:
  - `scripts/governance/tier0-validation-gate.sh --pre-deploy`

## 4. Evidence Baseline

### 4.1 Harness-first discovery

Authenticated harness plan and run were created on 2026-03-23 using the local hybrid coordinator.

- `POST /workflow/plan` succeeded with the standard phases: `discover`, `plan`, `execute`, `validate`, `handoff`.
- `POST /workflow/run/start` succeeded with session `3a386ea6-b1ec-4b61-b4bd-b2aad0f9570f`.
- Coordinator status shows:
  - local harness lane is ready,
  - remote coding/reasoning lanes are ready,
  - `allow_parallel_subagents=false`,
  - `max_parallel_subagents=1`,
  - tool-calling prep lane is degraded,
  - protected coordinator routes require `X-API-Key` from `/run/secrets/hybrid_coordinator_api_key`.

Implication:
- use the harness now for guarded planning, hints, and reviewer-gated execution,
- do not design the initial security program around broad parallel subagent fanout,
- improve local evidence loops and issue intake first.

Current readiness blocker from `scripts/ai/aq-qa 0` on 2026-03-23:
- `ai-import-agent-instructions.service` is in failed state, which blocks a clean Tier 0 validation pass even though the main coordinator, AIDB, switchboard, Redis, PostgreSQL, Qdrant, and local model services are active.

### 4.2 Local audit baseline

Local command run on 2026-03-23:

```bash
bash scripts/security/security-audit.sh
```

Observed baseline from `/home/hyperd/.local/share/nixos-ai-stack/security/audit-2026-03-23.json`:
- overall status: `findings`
- `pip-audit` unavailable locally
- Python lockfiles scanned: `0`
- npm audit available
- npm package roots scanned: `1`
- npm high findings: `0`
- npm critical findings: `0`
- dashboard security scan status: `error`
- secrets rotation planning status: `ready`

Implication:
- local scanner coverage is incomplete today,
- dashboard/operator security scan path needs repair,
- Python dependency auditing must be made reliably available before the repo backlog can be trusted.

### 4.3 Existing repo security machinery

Current repo security surfaces already present:
- GitHub Actions:
  - `.github/workflows/security.yml`
  - `.github/workflows/gitleaks.yml`
- Local scripts:
  - `scripts/security/security-audit.sh`
  - `scripts/security/security-scan.sh`
  - `scripts/security/dashboard-security-scan.sh`
  - `scripts/security/secrets-rotation-plan.sh`
- Integration tests:
  - `scripts/testing/test-security-workflow-integration.py`
  - `scripts/testing/smoke-security-audit-compliance.sh`

Current posture issue:
- several CI scans are report-oriented and non-blocking,
- local audit coverage depends on tool availability,
- the issue intake path is not yet dependable enough for backlog management.

### 4.4 Issue intake blockers

Observed local blockers on 2026-03-23:
- `gh auth status` failed because GitHub CLI is not logged in on this machine.
- user-reported GitHub backlog count (`595` open issues/warnings) is therefore unverified from this shell.
- `python3 scripts/governance/list-issues.py --limit 5` failed with `ModuleNotFoundError: No module named 'asyncpg'`.
- `scripts/governance/list-issues.py` also contains insecure/non-production defaults that should not become the long-term path:
  - default DB password literal,
  - missing resilience around local dependency availability.

Implication:
- we need a reliable local issue ingestion and normalization lane before trying to burn down the full hosted backlog.

## 5. Priority Model

Use this ordering for the first maturity cycle:

1. Secret exposure and credential handling.
2. Security tooling correctness and coverage gaps.
3. Externally exposed service/auth hardening.
4. NixOS module and declarative hardening drift.
5. Dependency and container vulnerability backlog.
6. Kernel-adjacent and upstream research intake.

## 6. Phase Plan

### Phase 0: Intake And Measurement

Goal:
- make the backlog measurable and reproducible from this machine.

Tasks:
- authenticate GitHub CLI or provide a repo token through approved secret management.
- build a normalized export path for:
  - GitHub code scanning alerts,
  - gitleaks findings,
  - local audit findings,
  - dashboard/operator security findings,
  - issue tracker records.
- fix or replace the local issue listing path so backlog review does not depend on broken optional dependencies.

Acceptance:
- one command produces a dated backlog snapshot with severity, component, rule id, location, and fix owner.

Validation:
- authenticated `gh` or API export works,
- local issue intake works without hardcoded credentials,
- exported snapshot is stored in a repo-approved path or referenced from the local database.

Rollback:
- disable only the new intake layer and continue using existing raw reports.

### Phase 1: Scanner Reliability

Goal:
- make local and CI security signals trustworthy enough to drive engineering decisions.

Tasks:
- ensure `pip-audit` is provisioned declaratively or through a bounded repo-supported path.
- repair `scripts/security/dashboard-security-scan.sh` or the dashboard route assumptions causing local `error` status.
- review `security.yml` and convert the highest-value scans from report-only to policy-gated where false positives are understood.
- document scan categories as:
  - blocking,
  - warning,
  - informational,
  - suppressed with justification.

Acceptance:
- local audit no longer reports missing scanner availability for supported ecosystems,
- dashboard security scan returns healthy output,
- at least one high-signal security class becomes gating.

Validation:
- `bash scripts/security/security-audit.sh`
- `scripts/testing/smoke-security-audit-compliance.sh`
- `scripts/testing/test-security-workflow-integration.py`

Rollback:
- revert gating thresholds to report-only while preserving collected evidence.

### Phase 2: Secrets And Auth Hardening

Goal:
- eliminate real secret exposure paths and tighten service auth defaults.

Tasks:
- review gitleaks history findings and separate:
  - active secrets,
  - already-rotated artifacts,
  - test fixtures,
  - suppressible false positives.
- remove literal default credentials from scripts and CLIs.
- standardize API key discovery on secret files or injected env vars only.
- confirm protected services bind to loopback unless explicitly required.

Acceptance:
- no new plaintext secret findings in current tree,
- security-sensitive scripts no longer ship production-like default passwords,
- authenticated routes consistently document the required secret source.

Validation:
- gitleaks local run or CI SARIF export,
- targeted `rg` scans for hardcoded secrets and credentials,
- relevant smoke tests for auth-protected endpoints.

Rollback:
- restore previous script behavior only if equivalent secret-safe injection exists.

### Phase 3: NixOS And Service Hardening

Goal:
- move security posture into typed options and declarative modules.

Tasks:
- audit systemd hardening for security-sensitive services.
- remove literal ports/URLs from modules and scripts where option/env wiring should exist.
- verify firewall exposure, rate limiting, and loopback-only defaults for internal services.
- map each security-sensitive service to its secret input and hardening controls.

Acceptance:
- service hardening matrix exists for core AI stack services,
- port and URL policy violations are reduced or blocked,
- declarative configuration is the source of truth for core security settings.

Validation:
- `scripts/governance/tier0-validation-gate.sh --pre-commit`
- targeted Nix syntax checks
- service-specific smoke tests

Rollback:
- revert module changes and redeploy prior generation.

### Phase 4: Core System Research And Upstream Readiness

Goal:
- create a disciplined path from local discovery to upstream-quality reports and patches.

Tasks:
- define templates for kernel/NixOS/core-package research notes:
  - repro conditions,
  - affected versions,
  - local evidence,
  - upstream reference,
  - proposed patch or mitigation.
- require local reproduction or authoritative external evidence before opening upstream issues.
- track upstream-targeted findings separately from repo-local fixes.

Acceptance:
- at least one upstream-ready issue template and one patch template exist,
- upstream work is blocked until local reproduction or source-backed evidence is attached.

Validation:
- dry-run the template on one repo-local or NixOS-core finding.

Rollback:
- keep findings local-only until evidence quality is sufficient.

## 7. Working Tracker

Use this table as the initial tracker seed.

| Track | Current state | First owner | Next evidence |
| --- | --- | --- | --- |
| GitHub code scanning export | blocked by `gh` auth | codex/human | authenticated export command |
| Local issue intake | broken | codex | working issue snapshot command |
| Python dependency audit | missing locally | codex | `pip-audit` available in local audit |
| Dashboard security scan | failing | codex | healthy dashboard scan report |
| Secrets backlog normalization | not started | codex/human | categorized gitleaks baseline |
| NixOS hardening matrix | not started | codex | tracked service hardening inventory |
| Upstream research template | not started | codex | first template draft with evidence contract |

## 8. First Execution Batch

Execute these in order:

1. Fix issue intake and backlog export.
2. Restore Python audit coverage and dashboard scan health.
3. Normalize gitleaks and credential-handling findings.
4. Harden core service auth/binding/systemd posture.
5. Only then start kernel/NixOS/core-package upstream research slices.

## 9. Commands Used For This Baseline

```bash
curl -sf http://127.0.0.1:8003/health | python3 -m json.tool
scripts/ai/aq-hints 'security code scanning backlog and upstream security research program' --format=json --agent=codex
HYBRID_KEY=$(tr -d '[:space:]' < /run/secrets/hybrid_coordinator_api_key)
curl -fsS -X POST http://127.0.0.1:8003/workflow/plan -H 'Content-Type: application/json' -H "X-API-Key: ${HYBRID_KEY}" -d '{"query":"Create a phased security remediation program for this repo and local AI harness, prioritized for repo code scanning backlog, NixOS modules, kernel-adjacent surfaces, and upstream contribution readiness."}'
curl -fsS -X POST http://127.0.0.1:8003/workflow/run/start -H 'Content-Type: application/json' -H "X-API-Key: ${HYBRID_KEY}" -d '{"query":"Investigate security scanning backlog prioritization and harness readiness","intent_contract":{"user_intent":"prepare a repo-grounded security remediation and research program","definition_of_done":"workflow run is created with explicit phases, validation expectations, and reviewer gate","depth_expectation":"standard","spirit_constraints":["declarative-first","evidence-based","no secrets in outputs"],"no_early_exit_without":["validation evidence","reviewer gate"]}}'
curl -fsS -H "X-API-Key: ${HYBRID_KEY}" 'http://127.0.0.1:8003/control/ai-coordinator/status' | python3 -m json.tool
bash scripts/security/security-audit.sh
python3 scripts/governance/list-issues.py --limit 5
gh auth status
```

## 10. Next Review Trigger

Review and update this document when any of these occur:
- authenticated GitHub backlog export is available,
- scanner coverage materially changes,
- issue intake is repaired,
- the `ai-import-agent-instructions.service` readiness failure is fixed,
- the first security remediation patch lands,
- upstream submission workflow is ready for trial use.
