# 2026-11-07 exempt-tests-batch1

## Objective
Work the "missing module" cause group (21 tests) of the P2.1 tests sweep (docs/harness-first/evidence/2026-11-06-sweep-tests.md) and, as one root cause allowed, part of "missing file". Un-exempt a test only when it passes in the CI environment. No assertion was weakened; no test was deleted or archived.

## Workflow/Session IDs
Branch fix/exempt-tests-batch1 (worktree .agents/delegation/worktrees/exempt-batch1), date 2026-11-07. Staged, not committed, not pushed.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet 5.5 (Rule 17, bounded triage slice).

## Commands Executed
CI-like environment: venv from `config/ci-test-requirements.txt` (plus `fido2`, added by this slice), `CI=true`, HOME/XDG/TMPDIR redirected to scratch, the CI git config, and `PYTHONPATH` unset (operator shells point it at the main checkout, which masked missing `shared`/module paths; `run-test-group.py` drops it too). The NixOS host needs `LD_LIBRARY_PATH` for libstdc++ so pip numpy loads; that is a host-only shim, not a CI concern. Each test run directly, then every touched group through `scripts/testing/run-test-group.py <group>`: tests-agent 27/27, tests-aq 80/80, tests-misc-a-c 81/81, tests-misc-i-m 50/50, tests-misc-n-r 102/102, tests-misc-s-z 88/88. `check-ci-test-coverage.sh` PASS (775 tests: 650 declared, 125 exempt).

## Validation Evidence

| test | diagnosis | action | verified how |
|---|---|---|---|
| test-agent-auth-s5.py | `core/config.py` imports `shared` from ai-stack/mcp-servers; only PYTHONPATH provided it. Fixing the producer (`_SHARED_PARENT`) broke test-routing-profile-registry.py, whose fallback relies on that ImportError, so the test adds mcp-servers to its own path (mirrors the deployed PYTHONPATH). | test path fix; un-exempted, tests-agent | group run, PYTHONPATH unset |
| test-approval-recovery.py, test-approval-signer.py, test-aq-approve-headless.py | Missing dependency `fido2` (real product dep, in nix/modules/core/base.nix, used by lib/approval_signer.py). | `fido2` added to config/ci-test-requirements.txt; un-exempted, tests-aq | pass 9/20/21 checks; tests-aq 80/80 |
| test-approval-runbook-engine.py | Not in the missing-module group but in the same approval family: passes 16/16 once fido2 is installed (its exemption was the same dependency). | un-exempted, tests-aq | direct + group |
| test-task-classifier-local-continuation.py | Two layers: (1) shim `task_classifier.py` needs hybrid-coordinator on sys.path; (2) stale constant: the "oversized" case used 5000 chars, but local limits were raised in 7718162a5 (1800/2000 tokens), so it is now local-eligible. The case now derives its size from the module's limits, same intent. | test fixed; un-exempted, tests-misc-s-z | group run |
| test-route-handler-{adaptive-timeouts,backend-audit,classifier-context-cap,context-budget,discovery-gating,local-synthesis-budget}.py (6) | Stale stubs after the coordinator split (d9a602930, phase-b3): tests loaded the re-export shim route_handler.py so monkeypatching never reached the code under test (`_hybrid_search` None); stubs lacked `routing_config`, `work_classifier` (ai-stack/offloading, on PYTHONPATH in the deployed unit), `query_targets_runtime_diagnostics`, and several Config attrs. Loaded the real core/route_handler.py, added the missing stubs (shared `_mock_config.py`), local-synthesis test query no longer contains "briefly" (brief queries deliberately skip synthesis). | tests fixed; un-exempted, tests-misc-n-r | group run 102/102 |
| test-search-router-collection-timeouts.py | Loaded the shim search_router.py (needs package `knowledge`); now loads knowledge/search_router.py; stub Config gained AI_SEARCH_SCORE_THRESHOLD. | test fixed; un-exempted, tests-misc-s-z | group run |
| test-safety-layer.py | Import path (tool_registry is in ai-stack/local-agents). It was also non-hermetic and non-asserting: wrote `.agent/proposals` into the cwd and a tool-audit sqlite into HOME, and printed FAILURE while exiting 0. Now runs in a temp cwd with a temp db and exits 1 on non-interception (strengthened, not weakened). | test fixed; un-exempted, tests-misc-s-z | direct + group |
| test-security-workflow-integration.py | lib/security moved to lib/cross-cutting/security and lib/deploy to lib/l1-infra/deploy (2e65cae38); audit-logger.py is hyphenated. Paths fixed, module loaded via importlib; scripts' state redirected to a temp `REPO_ROOT` (it wrote `.agent/security` into the checkout). Two real product bugs found and fixed (below); the vacuous scanner assertion now checks the JSON findings. | test + product fix; un-exempted, tests-misc-s-z | 18/18, group run |
| test-model-optimization-advanced-runtime.py | `synthetic_data` lives in ai-stack/model-optimization (deployed PYTHONPATH); added to test path. | test path fix; un-exempted, tests-misc-i-m | pass (needs numpy; in requirements) |
| test-multi-agent-collaboration.py, test-workflow-automation.py | `lib/agents` and `lib/workflows` moved to lib/l4-coord (2e65cae38). workflow-automation also wrote fixed /tmp paths that persisted across runs; now a per-run temp dir. | test fixes; un-exempted, tests-misc-i-m / tests-misc-s-z | 32/32 and 19/19 |
| test-query-performance.py | lib/search moved to lib/l6-cog/search (2e65cae38). After that, QueryCache skips results below `partial_cache_min_size` counted on `combined_results`; the test cached a one-row `results` payload. Payload now has the minimum rows, same assertions. | test fixed; un-exempted, tests-misc-n-r | 7/7, group run |
| test-a2a-compat.py (missing file) | http_server.py was deleted (e67f4289d); the canonical file is http_server_impl.py and its assertions still hold. | path fixed; un-exempted, tests-misc-a-c | group run |
| 19 other tests reading http_server.py (missing file) | Tried the same path swap: only a2a-compat passes. The rest grep the source for symbols that moved out of or were never in http_server_impl.py (e.g. `get_advanced_features_readiness`, `DELEGATED_PROMPT_TOKENS_BEFORE`, `/health`). Each needs a per-assertion review, which is not small. Reverted, still exempt, reason unchanged. | none | failure text recorded per test |
| test-llm-router-integration.py | Path (`__file__.parent`) and AI_STRICT_ENV fixed so it now runs, but it only prints PASS/FAIL and exits 0 (cannot gate) and its Test 2 prints a visible FAIL (expects free tier, router returns local). Needs a routing-policy decision. | edits kept; stays exempt, reason rewritten | run output |
| test-local-agent-offline-resilience.py | The router half imports local-agents/task_router.py, retired by cc392da25; no replacement has offline_mode / allow_degraded_local. | none; stays exempt (decision below) | import error, git log |
| test-prompt-effectiveness.py | Drives LocalOrchestrator.process() against a live model over a prompt corpus; also imports `local_orchestrator` from a hyphenated directory. | reclassified live-service | code read |

Fixture refresh: `scripts/testing/fixtures/local-inference-l2b-payload-golden.json` `live_source_manifest["ai-stack/mcp-servers/hybrid-coordinator/core/route_handler.py"]` refreshed from d76fd29c… (HEAD, pre-NameError-fix) to a3cca7f0… (working copy with the `_build_dynamic_system_prompt` fix), the deliberate same-PR refresh per 79cb82c1b; test-local-inference-l2b.py then passes 16/16 and the parity test stays green.

## Product bugs found
- `ai-stack/mcp-servers/hybrid-coordinator/core/route_handler.py`: `_build_dynamic_system_prompt` was called at two sites since 34b3db4ca (2026-05-25) but defined nowhere, so the local synthesis route raised NameError. Fixed by defining it as the prior behaviour (`Config.build_local_system_prompt()`). Needs a coordinator restart to take effect; the query-dependent behaviour the commit message implied was never written.
- `lib/*/log_debug` (8 files in lib/cross-cutting/security and lib/l1-infra/deploy): `[[ VERBOSE == 1 ]] && echo` returns 1 when VERBOSE is unset, and the files use `set -e`, so any script sourcing them and calling `log_debug` exited silently. Changed to `[[ ... != 1 ]] || echo`.
- `lib/l1-infra/deploy/deployment-hooks.sh`: `.last_updated = now | strftime(...)` piped the whole object into strftime (jq error), so `register_hook`, unregister and enable/disable never worked. Parenthesised in 3 places.
- `lib/cross-cutting/security/scanner.sh` `scan_file_for_secrets`: `\s` and `\047` inside bracket expressions are literal characters in ERE, so values containing `s`, `0`, `4`, `7` or a backslash were not detected (e.g. `password="insecure123"` missed). Replaced with POSIX classes.
- Observation, not changed: core/config.py `_SHARED_PARENT` is off by one since d9a602930 (shared is in ai-stack/mcp-servers); it only works through PYTHONPATH, and routing_contract's fallback depends on the resulting ImportError. Backlog-ready: [OPEN] COORDINATOR-SHARED-PATH core/config.py:23 resolves `shared` one level too low; fixing it lets Config load in strict mode outside the unit and breaks routing_contract's ImportError fallback (test-routing-profile-registry.py); fix both together; Severity low.

## Exemptions
Before 145, after 125 (20 removed). Remaining of the missing-module group: test-llm-router-integration.py, test-local-agent-offline-resilience.py, test-prompt-effectiveness.py (reasons rewritten). Missing-file group: 1 of 28 done (a2a-compat); 19 more reference http_server.py and need per-assertion review.

## Decisions needed
- test-local-agent-offline-resilience.py: archive (router half tests removed task_router, cc392da25) or port offline degradation to routing_contract. Not archived here.
- test-llm-router-integration.py: is "implement a new REST API endpoint" meant to route to the free tier or local? Then convert to real asserts.

## Rebuild / restart
Test, manifest and requirements changes need none. The route_handler fix needs a hybrid-coordinator restart (rebuild if the unit uses the Nix store copy); the lib/ shell fixes take effect on next sourcing.

## Residual Risk
Verified in a venv built from ci-test-requirements.txt on this host, not on a GitHub runner. fido2 is unpinned like the other entries. Runs left small artifacts only in scratch (moved, not deleted).

## Rollback Plan
Revert the commit. Product fixes stand alone: route_handler.py returns to raising NameError on local synthesis, so reverting it should be deliberate. Exemptions return with the revert.

## Hint Feedback
No hints were consulted. The sweep report and each test's code defined the work.
