# Evidence: Post-Merge Hygiene (#493/#498/#499/#500)

## Context
Date: 2026-10-14
Slice: `fix/post-merge-hygiene-488-500`
Component: `scripts/ai/lib/functional_eval.py`, `scripts/ai/aq-functional-eval`, `scripts/ai/aq-prompt-eval`, `scripts/ai/lib/rsi_sweep.py`, `nix/overlays/security-fixes.nix`, `.agent/ACTIVATION-AUDIT.md`, `.agent/WORKAROUND-REGISTER.md`, `scripts/testing/test-functional-prompt-eval.py`
Author lane: claude; independent reviewer: claude-sonnet (independent reviewer, 4 rounds) + orchestrator verification of final delta

## Problem
Root cause: Functional eval executed model-generated code in-process (#493), activation audit overstated state (#498), Nix security overlay lacked version floors (#499), and URLs were hardcoded (#500).

## Solution
Functional-eval model code runs in a two-process bwrap sandbox; activation audit made truthful; Nix version floors added; URLs sourced from env. Results are labelled trust=untrusted-model-output in all 3 consumers.

## Validation Evidence
- `test-functional-prompt-eval.py`: `ALL 6 FIXTURES PASS`.
- `test-eval-sandbox.py`: `Test EvalSandboxExecutor: PASSED`.
- `test-prompt-eval-transport-guard.py`: `PASS: aq-prompt-eval preserves registry entries on transport/runtime failures`.
- Reviewer probes passed: forgery, env, network, rlimit, stdout.
- tier0 `--pre-commit`: see commit/PR.

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| claude | claude-sonnet (independent reviewer, 4 rounds) + orchestrator verification of final delta | PASS_WITH_FOLLOWUPS |

## Follow-ups
- Documented residual: in-process model code can fake the child outcome; mitigated by trust label; registered as WR-XDP-DOCHECK-20261014 in the workaround register.

## Rule 15 Activation Attestation
- Integrated: YES - eval entrypoints and Nix overlay are the live path.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild / service restart).
- Functionally validated: tests above; full real-world end-to-end run DEFERRED (2026-10-14) pending activation unless stated in Validation Evidence.
- Observable: DEFERRED (dated 2026-10-14): no new dashboard/alert in this slice; existing logs/health unchanged.
- Intervenable: DEFERRED (dated 2026-10-14): no new operator control in this slice; existing controls unchanged.
- PM-tracked: commit subject references #493/#498/#499/#500; no tracker status hand-set.

## CI confinement preflight (2026-10-15)
Reason: GitHub-hosted runners deny unprivileged user namespaces, so the bwrap sandbox used by `scripts/ai/lib/functional_eval.py` cannot start there and QA row 0.10.64 failed in CI while passing locally.
- `functional_eval.sandbox_unavailable_reason()` runs a real bwrap preflight and caches only definitive results (success, bwrap not found, bwrap refusal); a timeout or OSError is reported but not cached.
- The runtime stays fail-closed: untrusted model code is never executed without a working sandbox.
- In `scripts/testing/test-functional-prompt-eval.py`, sandbox-dependent fixtures print `SKIP-WARN: ... confinement unavailable (<reason>)` when the preflight fails; pure fixtures always run. With `AQ_CONFINE_REQUIRE=1` the skip is a hard failure.
- Phase 0 row 0.10.64 sets `AQ_CONFINE_REQUIRE=1` unless `CI` is set, so a broken local bwrap fails loudly; in CI it reports SKIP with the warning.
- When groups were skipped the test prints `PASS WITH SKIPS` instead of the `ALL 6 FIXTURES PASS` banner.
