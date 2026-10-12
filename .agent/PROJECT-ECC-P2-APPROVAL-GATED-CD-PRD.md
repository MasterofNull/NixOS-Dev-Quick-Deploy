# PRD: ECC P2 Separately Approval-Gated CD Pack

## 1. Objective & Scope
Complete the final phase (Phase 8, P2) of the `ecc-parity-integration` plan.
Build a portable, approval-gated CD template and policy engine (`cd_policy.py` and `factory-cd.yml.tmpl`) within the factory gate bundle (`templates/factory-gate-bundle/ci/`), ensuring that deployments:
- Enforce environment protection approval gates (no deployment without environment configuration).
- Enforce non-destructive concurrency serialization (`cancel-in-progress: false`).
- Enforce least privilege (`contents: read`).
- Require immutable SHA action pins.
- Refuse unauthenticated triggers (e.g. pull requests).
- Verify artifact digest and provenance before execution.
- Maintain an explicit rollback handler on failure.
- Report a two-axis status: `LOCAL_READY` / `LOCAL_BLOCKED` / `NOT_INSTALLED` for local templates, and `UNVERIFIED_REMOTE` for remote GitHub environments (no external network/account mutation).
- Surface live health via QA check `0.10.63` and the dashboard backend and UI.
- Advance `ecc-parity-integration` plan to 100% completion (8/8 shipped).

---

## 2. Technical Specification

### A. Template: `templates/factory-gate-bundle/ci/factory-cd.yml.tmpl`
- Header marker: `# factory-gate-cd-pack v1`
- Triggers: `workflow_dispatch` with input `deployment_target` (choices: `staging`, `production`) and optional `rollback_target`.
- Permissions: `contents: read` at workflow level.
- Concurrency: `factory-cd-${{ github.workflow }}-${{ inputs.deployment_target || 'staging' }}` with `cancel-in-progress: false`.
- Job: `environment: name: ${{ inputs.deployment_target || 'staging' }}`.
- Steps:
  - Checkout pinned with full 40-hex SHA (`actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09`).
  - Pre-deploy CD policy audit (`python3 .factory/gate-bundle/ci/cd_policy.py check . --json`).
  - Artifact digest verification step (`sha256sum -c`).
  - Pre-flight gate check (`{{GATE_RUNNER_PATH}} --pre-commit`).
  - Deployment execution.
  - Post-deploy health probe.
  - Failure rollback handler (`if: failure()`).

### B. Policy Engine: `templates/factory-gate-bundle/ci/cd_policy.py`
- Parses CD workflows for compliance:
  - Detects `environment` configuration.
  - Detects `concurrency` with `cancel-in-progress: false`.
  - Audits action SHA pinning and least privilege.
  - Rejects `pull_request` and `pull_request_target` triggers.
  - Rejects `permissions: write-all` or top-level write.
  - Rejects missing rollback handling.
  - Rejects missing artifact verification.
- Two-axis verdict: `verdict: LOCAL_READY | LOCAL_BLOCKED | NOT_INSTALLED`, `remote: UNVERIFIED_REMOTE`.
- Functions: `audit_text()`, `audit_repo()`, `check(repo: Path)`, `health_summary(repo: Path, bundle: Path | None = None)`.

### C. Bundle Integration
- Update `templates/factory-gate-bundle/MANIFEST.json` to include `ci/factory-cd.yml.tmpl` and `ci/cd_policy.py`.

### D. QA & Dashboard Verification
- QA check `0.10.63` in `scripts/testing/harness_qa/phases/phase0.py` and `scripts/ai/_aq-qa-bash`: asserts `test-factory-cd-pack.py` PASS, `cd_policy.health_summary()`, and dashboard visibility.
- Dashboard route in `dashboard/backend/api/routes/aistack.py`: add `_cd_pack_health_summary()` and attach `cd_pack` in capability gap payload.
- Dashboard UI in `assets/dashboard.js`: add `· CD pack` row in capability gap card.

### E. Test Suite
- `scripts/testing/test-factory-cd-pack.py`: hermetic tests covering greenfield installation, action pinning, environment approval requirement, concurrency serialization, rollback step validation, untrusted trigger rejection, and CLI exit semantics.

### F. Plan Tracker Alignment
- `.agents/plans/ecc-parity-integration/tracker.json`: update `p2` to 100% accepted with commit and validation evidence, bringing ECC to 100%.

---

## 3. Activation Gate Attestation (6 Dimensions)
1. **Integrated**: Live QA check 0.10.63, dashboard backend route, dashboard UI, and bundle manifest.
2. **Turned ON**: Local policy evaluation active; remote state safely reported as UNVERIFIED_REMOTE.
3. **Functionally Validated Real-World**: Hermetic tests verify template rendering, security checks, and rollback logic.
4. **Observable**: Surfaced via `aq-qa 0`, `/stats/capability-enforcement` and dashboard UI card.
5. **Intervenable**: Operator inputs for target environment and rollback target; approval gates halt execution.
6. **PM-tracked**: Plan tracker `ecc-parity-integration` reaches 100%.
