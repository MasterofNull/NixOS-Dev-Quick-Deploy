# Wave E Slice 10: static test recovery

Date: 2026-11-11
Task ID: HF-20261111-WAVE-E-S10

Scope: test-only plus CI manifest, plan classification, one payload-manifest entry, and a Qwen-only comment/log wording fix in `nix/home/base.nix`. No production behavior change.

## Objective
- Repair 26 static contract tests that read the deleted `http_server.py` (or stale Nix/hook formatting) so they assert current live owners, and remove them from `test_exempt` in `config/ci-checks.json` only where they pass. Delivered: 26 tests repaired and un-exempted (exempt 122 -> 96), 5 plan classifications added, `.github/CODEOWNERS` payload-manifest entry added.

## Workflow/Session IDs
- Workflow ID: recovery-wave-e-slice10-20261111 (branch and worktree of the same name)
- Session ID: Codex delegate (started it), completed by a Claude sub-agent; cross-checked against a second agent's per-assertion diff.

## Delegation Decision
- Delegated: bounded test-repair slice routed to Codex (Rule 4/17); Codex stopped after tier0 PASS with a required port-SSOT correction, finished by a Claude implementer. Nothing committed or pushed; tier0 not re-run by the finisher.

## Commands Executed
```bash
python3 -m venv <scratch>/venv-e10 && pip install -r config/ci-test-requirements.txt
CI=true HOME/XDG_*/TMPDIR redirected: python3 scripts/testing/<test>.py   # 28 scripts
python3 scripts/testing/run-test-group.py tests-misc-a-c ; ... tests-misc-d-h
bash scripts/governance/tier0.d/check-ci-test-coverage.sh
```

## What changed

- 15 coordinator regression tests now read explicit live owners instead of the removed `http_server.py` or a source glob. Ten of them share one `COORDINATOR_OWNERS` tuple whose `coordinator_source()` raises if `http_server_impl.py` does not reference an owner module, so a dormant file cannot satisfy an assertion. Assertions that moved were rewritten to the current code, not loosened:
  - delegated quality checker asserts `QualityThreshold.PERMISSIVE` (current production, Phase 12.1) and the `_ai_coordinator_local_fallback_profile(` helper;
  - query audit asserts the `_collect_query_audit` collector and its call site;
  - failover chains assert the full current local-first `priority_profiles` lists, and the pool test sets `SWITCHBOARD_REMOTE_ALIAS_*` env so the real pool registers slots (taken from the second agent's version);
  - Continue ingress parses `ai-stack/continue/config.json` and asserts every model uses the switchboard base; OpenAI/A2A routes are asserted through `agent_service` -> `openai_a2a_handlers.register_routes` (router.py), and `http_server_impl` init;
  - metrics symbols are asserted in `core/metrics.py` (`metrics.py` is a re-export shim);
  - strangler ownership reads `http_server_impl.py` only (a glob counted the owning services as legacy registrars);
  - workflow defaults read `runtime_manager`, `orchestration_utils`, `session_builders`, `agent_registry` explicitly; pattern adoption reads `workflow_planning`, `workflow_session_handlers`, `session_builders`; ops reads `workflow/ops_handlers.py`.
- `test-pre-commit-whitespace-check.py`: asserts all five hook calls are invoked as lines (not substrings of definitions or the early `exit 0` guard) and in order.
- `test-vscodium-extension-runtime-guards.py`: Qwen pruning retained; asserts Gemini CodeAssist handling is absent (retired by 3c14a843816e); Codex and Claude obsolete-marker prefixes preserved. `nix/home/base.nix` lines 1437 and 1440 now say Qwen only (comment and echo text, no behavior).
- `test-worktree-isolation.py`: fixtures drop ambient `AQ_DELEGATION_DIR` (root cause: `run-test-group.py` exports it, which relocated worktree roots and registries so blocked-path assertions succeeded).
- `test-advanced-features-control-plane.py` (reads `extensions/model_opt_handlers.py`), `test-agent-evaluation-bias.py` and `test-agent-pool-integration.py` (read named owner modules through `scripts/testing/_coordinator_src.py`, which concatenates only the listed files and fails if one is missing): added in the finishing pass from the second agent's diff, and un-exempted.
- `test-desktop-cosmic-greeter-config.py`, `test-vscodium-gpu-mitigation.py` (regex tolerant of alejandra line breaks), `test-nixos-writable-state-policy.py`: current Nix formatting / host-path literal split only.
- `templates/agentic-workflow/project-payload-manifest.json`: `.github/CODEOWNERS` entry sourced from existing `templates/factory-gate-bundle/CODEOWNERS.tmpl`.
- `.plan-classification.json` added for 5 plan dirs (delivery-loop-simplification, agentic-routing, sota-dashboard-cockpit-revamp, sota-intelligence-intake-mesh, system-integrity-recovery); each cites its tracker.json plan id, owner, goal, existing `prd_ref` and item count. `test-plans-index.py` requires every plan dir classified.
- `config/ci-checks.json`: 26 scripts moved from `test_exempt` (known-failing) into `tests-misc-*` groups (`tests` and `paths`); `test-nixos-writable-state-policy.py` was already in `tests-misc-n-r`.

## Validation Evidence

- Finishing pass (venv from `config/ci-test-requirements.txt`, CI=true, HOME/XDG/TMPDIR redirected): all 28 scripts run directly (26 un-exempted tests, `test-plans-index`, `test-project-payload-manifest`, `test-ci-checks-manifest`, `test-no-host-repo-paths-in-tests`) exit 0. `tests-misc-d-h` 86/86. `tests-misc-a-c` 88/90: `test-check-checkout-fresh.sh` (git HEAD absent under redirected HOME) and `test-cross-agent-contradiction-detection.py` (numpy cannot load libstdc++ in the plain venv) fail on environment only; neither file is touched by this slice. Codex's earlier run (real env) had a-c 87/87, i-m 52/52, n-r 110/110, s-z 95/95.
- `scripts/testing/test-ci-checks-manifest.py` pass; `scripts/governance/tier0.d/check-ci-test-coverage.sh` PASS (777 tests: 681 declared, 96 exempt; was 122 exempt before the slice); `test-project-payload-manifest.py` PASS (95 required targets); `test-plans-index.py` OK (31 tests).
- Not run by the finisher: tier0 (Codex ran it before the port-SSOT correction; it must be re-run before commit), i-m/n-r/s-z groups, commit, deploy.

## Rollback Plan
- `git restore --staged --worktree .` in the slice worktree before commit, or `git revert <commit>` after. Trigger: any un-exempted test failing in CI. Nothing here changes runtime behavior.

## Activation scope

Repository-only. The groups run in the existing CI runner. The `base.nix` change alters only comment and log text; no NixOS rebuild or service activation is claimed and none is required. Pending NixOS deployment remains owner-run. Plan status stays projected from trackers.

## Residual Risk

These are static source checks: they prove wiring and contract text, not runtime behavior. `test-continue-coordinator-ingress.py` derives the expected switchboard apiBase from the `options.nix` switchboard port default (the port-SSOT correction; no literal 8085 in the test). `ai-stack/continue/config.json` itself still hardcodes 8085 (pre-existing, not changed here). `nix/home/base.nix` change is comment/echo text only and is a rebuild item for the next home-manager activation.


## Hint Feedback
- No aq-hints IDs were consumed by the finishing agent; none to rate.
