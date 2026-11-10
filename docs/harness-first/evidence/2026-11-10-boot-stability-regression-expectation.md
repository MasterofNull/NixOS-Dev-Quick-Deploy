# Boot-stability regression expectation recovery evidence

Date: 2026-11-10

`scripts/testing/test-boot-stability-regressions.py` was exempt as known-failing
and had two stale static assertions:

1. It expected a flattened `mutableUserServicePaths = lib.unique [mutableOptimizerDir mutableLogDir];`.
   `nix/modules/core/base.nix` intentionally includes the log dir only when the
   AI-stack role is disabled (the enabled role owns its log tmpfiles rule). The
   assertion now matches that exact conditional expression, whitespace-tolerant.
2. It expected `apparmor-fix-agent.py` to filter an ignored `HANDOFF.md` before
   committing. Since #638 ("no auto-commit") the agent performs no Git operations
   at all. The assertion now requires `applied_uncommitted` and the absence of any
   `"git"` constant, which is a stronger form of the original guard.

No producer changed. The test is registered in `tests-misc-a-c` `paths` and `tests`
and its exemption is removed.

Validation:

- `python3 scripts/testing/test-boot-stability-regressions.py` — PASS.
- `python3 -m py_compile scripts/testing/test-boot-stability-regressions.py` — pass.
- `python3 scripts/testing/test-ci-checks-manifest.py` — pass (eight checks).
- Implementer: Codex (`codex-20261110-091804-vek4nl`); orchestrator re-ran all
  three on origin/main `1dfe6cc46` after applying the patch.

Activation deferral (2026-11-10): repository-only test maintenance; no service,
runtime configuration, or deployment to activate.
