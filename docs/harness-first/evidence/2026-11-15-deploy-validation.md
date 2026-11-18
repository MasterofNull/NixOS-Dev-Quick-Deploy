# Deploy validation

The owner activated NixOS and Home Manager at cd074797 successfully. Final QA failed factory readiness check 0.10.50 because the test resolved a live GitHub owner separately for preview and confirmation. A deterministic fixture owner fixes the test without changing production integrity checks.

The deployment ledger could also reconcile a running revision after failed wrapper QA and report completion without retrying QA. Reconciled deployments now require a successful live phase 0 QA with one valid zero-failure summary. A successful wrapper does not repeat QA.

Validation: 41/41 update tests, 26 factory readiness invariants, Python compilation and staged whitespace checks passed. Regression coverage includes failed QA, malformed summary, nonzero process exit despite green summary, eventual successful retry and no duplicate rebuild. Sudo policy remains unchanged; CLI wording no longer promises one prompt.

Full live validation: phase 0 exited 0 with 208 passed, 0 failed and 9 skipped (370s), using `FACTORY_OWNER_HANDLE=factory-fixture AQ_CONFINE_REQUIRE_CONTEXT=1 scripts/ai/aq-qa 0 --machine` on the running system. The committed fixture supplies that deterministic owner itself. Tier0 passed all 70 gates. Independent staged implementation review passed.

Activation attestation: these are directly invoked CLI and test changes; no daemon or Nix configuration changed. Existing QA executes the fixture. The owner already activated the system; another rebuild is unnecessary for these changes. QA output and the deployment ledger expose status; rerunning deploy retries validation. This bounded repair follows the approved delivery-loop S4 scope.
