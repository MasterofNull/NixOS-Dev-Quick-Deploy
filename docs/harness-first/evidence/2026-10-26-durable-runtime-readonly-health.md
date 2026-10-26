# Evidence: Durable Runtime Read-Only Health Summary for Confined Daemons

## Objective
Enable read-only callers (such as `command-center-dashboard-api`, confined under AppArmor with `deny /home/** wx`) to query `durable_runtime.health_summary()` without attempting store initialization or file lock creation, eliminating `durable_runtime_unavailable:OSError` and making durable mesh status operational on the live dashboard.

## Workflow/Session IDs
- Session ID: `57a807e7-c3e6-4e8e-833b-ce38fb8d47cd`
- PRD: `.agent/PROJECT-DURABLE-AGENTS-SOTA-UI-PRD.md`
- Branch: `fix/durable-runtime-readonly-health-wave7`

## Delegation Decision
- Implementer: Antigravity orchestrator.
- Reviewer: Codex independent parity check.

## Commands Executed
- `python3 scripts/testing/test-aq-durable.py`
- `python3 -c "import urllib.request, json; print(json.loads(urllib.request.urlopen('http://127.0.0.1:8889/api/aistack/advanced/runtime-summary').read())['summary']['capability_gap']['durable_runtime'])"`
- `bash scripts/governance/tier0-validation-gate.sh --pre-commit`
- `bash scripts/testing/check-harness-first-pr-evidence-gate.sh`

## Changes Made
- Refactored `health_summary()` in `scripts/ai/lib/durable_runtime.py` to open and parse `ledger.json` in read-only mode (`open(..., "r")`) instead of instantiating `DurableEffectStore()`, which calls `_ensure_store()` and attempts mkdir/lock operations forbidden in confined reader environments.
- Maintained exact return schema contract (`available`, `status`, `total_intents`, `unresolved_intents`, `committed_intents`, `ledger_path`).

## Validation Evidence
- Unit test suite `test-aq-durable.py` passed: 10/10 fixtures PASS.
- Live API query: `GET http://127.0.0.1:8889/api/aistack/advanced/runtime-summary` transitioned from:
  `{'available': False, 'status': 'unverified', 'reason': 'durable_runtime_unavailable:OSError'}`
  to:
  `{'available': True, 'status': 'operational', 'total_intents': 0, 'unresolved_intents': 0, 'committed_intents': 0, 'ledger_path': '/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/durable/ledger.json'}`.
- Pre-commit Tier-0 gate passed (71/71 checks pass).

## Rollback Plan
- Revert commit on `fix/durable-runtime-readonly-health-wave7`.

## Residual Risk
- None: pure read-only path that safely defaults to `status: "unconfigured"` if `ledger.json` does not exist.

## Hint Feedback
- `aq-hints` surfaced the live runtime summary endpoint (`/api/aistack/advanced/runtime-summary`) which enabled rapid detection and verification of the AppArmor confinement mismatch.
