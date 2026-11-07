# Recovery sweep P2.1: every test file executed (2026-11-06)

## Objective
Execute every test file once, isolated, and produce a dated red list (P2.1, system-integrity-recovery). Report only: no test and no exemption was changed.

## Workflow/Session IDs
Branch feat/sweep-tests, worktree `.agents/delegation/worktrees/p21-tests-sweep`. Date 2026-11-06. Tool: `scripts/governance/sweep-tests.py`; its unit test is `scripts/testing/test-sweep-tests.py`.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet 5.5 (Rule 17: bounded script, test and report).

## Commands Executed
```
sweep-tests.py --date 2026-11-06 --workdir /tmp/aq-sweep-p21 --state /tmp/aq-sweep-p21/state.jsonl --report docs/harness-first/evidence/2026-11-06-sweep-tests.md --no-watch
```
Isolation: sandbox=bwrap (read-only filesystem except a per-test temp dir and a private repo clone, no network, private pid/ipc/uts, /run/user /run/dbus /run/systemd masked), env whitelist, HOME/XDG/TMPDIR redirected, every service URL -> http://127.0.0.1:9, own process group + hard timeout 90s + marker sweep, nice 19, 2 worker(s).

## Validation Evidence
Runtime of the sweep 22.3 min wall (report regenerated from the saved state file); 744 of 770 test files executed (resumed runs accumulate in the state file).

### Counts per class

| class | count |
|---|---|
| PASS | 618 |
| FAIL | 13 |
| TIMEOUT | 3 |
| NOT_RUN | 26 |
| FLAKY | 1 |
| EXEMPT_NOW_PASSES | 2 |
| EXEMPT_STILL_FAILS | 107 |

Flags (orthogonal, a test can carry several):

| flag | count |
|---|---|
| UNDECLARED | 1 |
| NO_ASSERTIONS | 0 |
| TIME_BOMB | 1 |
| TREE_MUTATION | 0 |
| LIVE_MUTATION | 4 |
| LEFTOVER_PROCS | 0 |
| RO_BLOCKED | 1 |

### Root-cause groups (FAIL, TIMEOUT, EXEMPT_STILL_FAILS)

| group | count |
|---|---|
| stale assertion | 47 |
| missing file | 28 |
| missing module | 21 |
| unclassified | 18 |
| real product bug (suspect) | 5 |
| timeout | 3 |
| environment | 1 |

### EXEMPT_NOW_PASSES (2): known-failing exemptions whose test passed; each exemption can be removed

- `scripts/testing/test-capability-lease.py` (3.4s)
- `scripts/testing/test-dashboard-compat-routes.py` (2.9s)

### Passed here but exempt for another class (9); NOT evidence the exemption can go (this run has no live stack)

- `scripts/testing/test-aq-loop-review-repair-guard.py` [mutates-state]
- `scripts/testing/test-aq-memory-persistence.py` [sandbox-env]
- `scripts/testing/test-codex-config-reconcile.py` [sandbox-env]
- `scripts/testing/test-dashboard-advanced-runtime-summary.py` [mutates-state]
- `scripts/testing/test-factory-gate-readiness.py` [slow]
- `scripts/testing/test-functional-prompt-eval.py` [sandbox-env]
- `scripts/testing/test-local-inference-throughput.py` [unstable]
- `scripts/testing/test-model-catalog-freshness.py` [sandbox-env]
- `scripts/testing/test-web-research-lane.py` [unstable]

### Findings table (everything not a plain PASS)

| test | class | exempt | group | first failure / note | flags |
|---|---|---|---|---|---|
| `check-aq-report-metric-smoke.sh` | FAIL |  | stale assertion | [INFO] seed-tool-audit-traffic failed on attempt 1/3; retrying in 3s |  |
| `test-a2a-compat.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-activation-signer.py` | FAIL |  | unclassified | activation_signer.SignerError: invoking user cannot search the directory above t1-v8sv02lx in /tmp/aq-sweep-p21/t1-v8sv02lx/tmp/tmpo03a0g4c/priv/doc.md |  |
| `test-adk-declarative-wiring.sh` | EXEMPT_STILL_FAILS | known-failing | missing file | bash: /tmp/aq-sweep-p21/w1/repo/lib/adk/wiring-validator.sh: No such file or directory |  |
| `test-adk-reviewer-gate-checklist.sh` | EXEMPT_STILL_FAILS | known-failing | missing file | scripts/testing/test-adk-reviewer-gate-checklist.sh: line 6: /tmp/aq-sweep-p21/w1/repo/lib/adk/implementation-discovery.sh: No such file or directory |  |
| `test-advanced-features-control-plane.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-advanced-reasoning-patterns.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/ai-stack/agentic-patterns/self_consistency.py' |  |
| `test-agent-auth-s5.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'shared' |  |
| `test-agent-auth-s7-s9.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-agent-evaluation-bias.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-agent-lesson-registry.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: expected one registry lesson |  |
| `test-agent-lesson-schema.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: expected at least one lesson candidate |  |
| `test-agent-monitoring-audit.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: 3 != 1 |  |
| `test-agent-pool-integration.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w0/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-agent-status-integration.py` | EXEMPT_STILL_FAILS | known-failing | unclassified | ✗ No agents in pool |  |
| `test-ai-coordinator.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: gemini profile inference failed |  |
| `test-ai-insights-dashboard.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-ai-insights-roadmap-surfaces.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: roadmap readiness should expose agentic pattern library readiness for phase 4 |  |
| `test-ai-metrics-instrumentation.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-ai-service-health-monitoring.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-ai-stack-health-monitor.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: health monitor unit must set TimeoutStartSec >= 490s (harness timeout + margin) |  |
| `test-ai-stack-health.sh` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-aidb-library-catalog-sync-fetch.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-approval-recovery.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'fido2' |  |
| `test-approval-runbook-engine.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | FAIL (8): |  |
| `test-approval-signer.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'fido2' |  |
| `test-aq-approve-headless.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'fido2' |  |
| `test-aq-completions.sh` | FAIL |  | unclassified | bash: line 1: complete: codex: no completion specification |  |
| `test-aq-confine.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-aq-help-center.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: Missing /tmp/aq-sweep-p21/t1-bao0heq9/home/.local/share/applications/aq-help-center.desktop |  |
| `test-aq-qa-continue-config.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: aq-qa phase 0 should describe the switchboard ingress contract for Continue config |  |
| `test-aq-report-reliability-interpretation.py` | EXEMPT_STILL_FAILS | known-failing | real product bug (suspect) | TypeError: format_text() missing 1 required positional argument: 'editor_rescue_windows_summary' |  |
| `test-aq-report-tool-audit-sources.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: expected only fresh entry inside window |  |
| `test-aq-tool.py` | FAIL | sandbox-env | stale assertion | AssertionError: known pkg 'hello' should run and exit 0: warning: you don't have Internet access; disabling some network-dependent features |  |
| `test-aq-worktree-reap.py` | FAIL |  | unclassified | subprocess.CalledProcessError: Command '['git', 'push', '-u', 'origin', 'main']' returned non-zero exit status 1. |  |
| `test-attention-notifications.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError |  |
| `test-auto-tool-select-skill-routes.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: auto-tool-select routes should expose /skills/list |  |
| `test-autonomous-capability-discovery.sh` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-boot-stability-regressions.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: base module should identify user-writable service workdirs separately from root-owned state roots |  |
| `test-c6a-launch-dashboard-runtime-probe.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | FAIL: a provisioned TEG uid whose launch-group topology cannot be confirmed live must NOT be reported enforced=True |  |
| `test-candidate-lifecycle.py` | PASS |  |  |  | LIVE_MUTATION |
| `test-capability-lease.py` | EXEMPT_NOW_PASSES | known-failing |  | static: future date literal(s) 2026-12-31 beside a wall-clock call | TIME_BOMB |
| `test-chat-intent.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion |   FAIL  agentic confidence == 1.0 |  |
| `test-check-checkout-fresh.sh` | FAIL |  | stale assertion |   ✗ FAIL: expected exit 3, got 0 |  |
| `test-check-mcp-health-defaults.sh` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-claude-dispatch-payload-safety.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: task claude-20261106-223705-rc84ib did not reach done |  |
| `test-codex-subagent-configuration.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/.codex/config.toml' |  |
| `test-continue-coordinator-ingress.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-continuous-learning-watchfiles-throttle.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError |  |
| `test-coordinator-strangler-route-ownership.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-dashboard-a2a-insights-ui.py` | EXEMPT_STILL_FAILS | known-failing | unclassified |   - Analytics + A2A |  |
| `test-dashboard-ai-insights-ui.py` | EXEMPT_STILL_FAILS | known-failing | unclassified |   - /api/insights/report/full |  |
| `test-dashboard-ai-metrics-switchboard-local-runtime.py` | FAIL |  | stale assertion | AssertionError: long-running local switchboard lane should surface as busy-long-running |  |
| `test-dashboard-aidb-health-live-mode.py` | EXEMPT_STILL_FAILS | known-failing | unclassified |   - fetch(`${FASTAPI_BASE}/api/aidb/health/detailed`, { cache: 'no-store' }) |  |
| `test-dashboard-command-center-graph-ui.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: expected command-center graph panel in dashboard configuration section |  |
| `test-dashboard-command-lenses-ui.py` | EXEMPT_STILL_FAILS | known-failing | unclassified |   - .welcome-banner |  |
| `test-dashboard-compat-routes.py` | EXEMPT_NOW_PASSES | known-failing |  |  |  |
| `test-dashboard-config-control-plane.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: front-door routing should expose implementation alias mapping |  |
| `test-dashboard-config-ui.py` | EXEMPT_STILL_FAILS | known-failing | unclassified |   - compatibility_overrides |  |
| `test-dashboard-deployment-ui.py` | EXEMPT_STILL_FAILS | known-failing | unclassified |   - /api/ws/deployments |  |
| `test-dashboard-operator-links-api-base.py` | EXEMPT_STILL_FAILS | known-failing | unclassified |   - updateOperatorLinks(); |  |
| `test-dashboard-orchestration-api-base.py` | EXEMPT_STILL_FAILS | known-failing | unclassified |   - fetch(`${FASTAPI_BASE}/api/aistack/orchestration/evaluations/trends`) |  |
| `test-dashboard-orchestration-sessions.py` | EXEMPT_STILL_FAILS | known-failing | real product bug (suspect) | AttributeError: 'FakeClientSession' object has no attribute 'closed' |  |
| `test-dashboard-phase5-7-integration.py` | EXEMPT_STILL_FAILS | known-failing | real product bug (suspect) | AttributeError: 'FakeClientSession' object has no attribute 'closed' |  |
| `test-dashboard-program-progress.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-dashboard-qa-provider-probe.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: QA Phase 0 Status card must have exactly 5 pre-existing + 6 new probe rows |  |
| `test-dashboard-routing-posture-ui.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: expected live routing posture panel in dashboard config section |  |
| `test-dashboard-routing-ratio.js` | PASS |  |  |  | UNDECLARED |
| `test-dashboard-security-headers.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-dashboard-testing-ui.py` | EXEMPT_STILL_FAILS | known-failing | unclassified |   - /api/testing/execute |  |
| `test-dashboard-visual.sh` | FAIL | slow | unclassified | ── API Endpoints ── |  |
| `test-delegate-agent-mapping.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-delegate-claude-model-routing.py` | EXEMPT_STILL_FAILS | known-failing | real product bug (suspect) | IndexError: list index out of range |  |
| `test-delegate-codex-quota-precheck.sh` | FAIL |  | stale assertion | PASS: (a) wait-mode quota error writes parsed cooldown (2027-07-25) |  |
| `test-delegate-coding.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-delegate-local-agent.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-delegate-timeout-config.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: expected delegate handler to read timeout slack from env |  |
| `test-delegate-to-claude-lifecycle.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: 3 != 0 : [delegate-to-claude] no free claude slot for role=implement (DELEGATE_CLAUDE_MAX_PARALLEL=2; one slot reserved for review). Retry later |  |
| `test-delegate-wrapper-shell-safety.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/t0-dcebo2g3/tmp/delegate-shell-safety-jjp5i58l/.agents/delegation/registry.jsonl' |  |
| `test-delegate.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-delegated-prompt-efficiency-integration.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w0/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-delegated-quality-integration.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w0/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-delegation-failover.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w0/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-delegation-feedback.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: expected delegated failure count |  |
| `test-delegation-local-gemini.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-deployment-dashboard.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-desktop-cosmic-greeter-config.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: COSMIC greeter config seed should run before greeter startup |  |
| `test-event-bus-a2a.py` | PASS |  |  |  | RO_BLOCKED |
| `test-execution-cell-adapter.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-execution-cell-clone.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-execution-cell-perf-harness.py` | EXEMPT_STILL_FAILS | known-failing | real product bug (suspect) | [FAIL] test_cache_validity_gating — test raised RuntimeError: no disk-backed writable temp directory found for cache-validity fixtures (design §4 requires real  |  |
| `test-execution-cell-runner.py` | FAIL | sandbox-env | stale assertion | [FAIL] write_grant_green — expected green, got quarantined/tree-not-proven-absent (stage=supervise) |  |
| `test-factory-gate-install.py` | FAIL |  | stale assertion | AssertionError: unexpected exit 1: /tmp/aq-sweep-p21/t0-0mj5y6jb/tmp/factory gate fixture 7zl51t4v/green field/.factory/gate-bundle/self-test.sh |  |
| `test-factory-gate-retrofit.py` | FAIL |  | stale assertion | AssertionError: unexpected exit 1: /tmp/aq-sweep-p21/t0-2y0v52jj/tmp/factory retrofit fixture yfrqcq_6/existing repo/.factory/gate-bundle/self-test.sh |  |
| `test-functional-prompt-eval.py` | PASS | sandbox-env |  |  | LIVE_MUTATION |
| `test-gate-checkout.py` | PASS |  |  |  | LIVE_MUTATION |
| `test-graph-build.py` | PASS |  |  |  | LIVE_MUTATION |
| `test-harness-delegation-live.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-harness-hooks.py` | FLAKY | unstable | stale assertion | 1st: AssertionError: 138.14545499917585 not less than 100.0 : SessionStart hook latency exceeded 100ms: 138.15ms \| rerun: PASS |  |
| `test-http-query-audit-metadata.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w0/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-integration-completeness.py` | EXEMPT_STILL_FAILS | known-failing | unclassified | ✗ Service: hybrid-coordinator: hybrid-coordinator is not running |  |
| `test-llm-router-integration.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ERROR: Failed to import required modules: No module named 'llm_router' |  |
| `test-local-agent-config.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: hyperd should pin the local llama.cpp lane to qwen3.6-35b-mtp-q5 for harness testing |  |
| `test-local-agent-offline-resilience.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'task_router' |  |
| `test-local-delegation-reliability.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-local-subprocess-discipline-smoke.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-meta-learning-integration.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w0/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-model-optimization-advanced-runtime.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'synthetic_data' |  |
| `test-model-optimization-mcp-tools.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: MCP handlers should expose capture_training_example |  |
| `test-model-optimization-runtime-integration.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: interaction outcome should still update qdrant payload |  |
| `test-multi-agent-collaboration.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'agents' |  |
| `test-network-policy-packaging.sh` | EXEMPT_STILL_FAILS | known-failing | unclassified | usage: scripts/testing/test-network-policy-packaging.sh AQ_NETWORK_POLICY NMCLI RESOLVECTL |  |
| `test-no-host-repo-paths-in-tests.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | FAIL: host-specific repo paths in tests (derive from __file__): |  |
| `test-ops-handler-extraction.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-optional-performance-completion.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/.agents/plans/PHASE-4-5-COMPLETION-ROADMAP-2026-03-30.md' |  |
| `test-orchestration-runtime-integration.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-orchestration-visibility.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | ❌ FAIL: Missing UI elements: |  |
| `test-pipeline-orchestration.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w0/repo/ai-stack/agentic-patterns/pipeline_orchestration.py' |  |
| `test-plans-index.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: False is not true : delivery-loop-simplification: missing .plan-classification.json |  |
| `test-pm-tracker-owner-acceptance.py` | TIMEOUT |  | timeout | .... |  |
| `test-pre-commit-whitespace-check.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: Function should be called before exit |  |
| `test-progressive-context-integration.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w0/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-project-payload-manifest.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: {'.github/CODEOWNERS'} |  |
| `test-prompt-effectiveness.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'local_orchestrator' |  |
| `test-prompt-injection-resilience.sh` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-qa-provider-probe-lifecycle.py` | EXEMPT_STILL_FAILS | known-failing | environment | subprocess.TimeoutExpired: Command '['/home/hyperd/.nix-profile/bin/python3', '/tmp/aq-sweep-p21/w0/repo/scripts/testing/test-qa-provider-probe-lifecycle.py', ' |  |
| `test-quality-system-health.py` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-query-performance.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'lib.search' |  |
| `test-real-time-learning-integration.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-real-world-workflows.sh` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-revocation-epoch-authority.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | FAIL: replay over socket: denied |  |
| `test-route-handler-adaptive-timeouts.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ImportError: cannot import name 'routing_config' from '<unknown module name>' (unknown location) |  |
| `test-route-handler-backend-audit.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ImportError: cannot import name 'routing_config' from '<unknown module name>' (unknown location) |  |
| `test-route-handler-classifier-context-cap.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ImportError: cannot import name 'routing_config' from '<unknown module name>' (unknown location) |  |
| `test-route-handler-context-budget.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ImportError: cannot import name 'routing_config' from '<unknown module name>' (unknown location) |  |
| `test-route-handler-discovery-gating.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ImportError: cannot import name 'routing_config' from '<unknown module name>' (unknown location) |  |
| `test-route-handler-local-synthesis-budget.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ImportError: cannot import name 'routing_config' from '<unknown module name>' (unknown location) |  |
| `test-safety-layer.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'tool_registry' |  |
| `test-scope-gate.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: 0 == 0 |  |
| `test-search-router-collection-timeouts.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'knowledge' |  |
| `test-security-contract-gates.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: parity plan missing PA-2 |  |
| `test-security-cve-rsi-gate.py` | EXEMPT_STILL_FAILS | known-failing | missing file | AssertionError: 'HIGH/CRITICAL CVE detected' not found in '\x1b[90m10:47PM\x1b[0m \x1b[31mFTL\x1b[0m \x1b[1munable to load gitleaks config, err: open /tmp/aq-sw |  |
| `test-security-nix-closure-scan.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: '\|\| true' unexpectedly found in 'sudo rm -rf \\\n  /usr/share/dotnet \\\n  /usr/local/lib/android \\\n  /opt/ghc \\\n  /opt/hostedtoolcache \\ |  |
| `test-security-workflow-integration.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'audit_logger' |  |
| `test-switchboard-continue-context-window.sh` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-switchboard-local-tool-calling.sh` | NOT_RUN | live-service |  | live-service: exempt as needing the live stack; not run (use --include-live to run it isolated) |  |
| `test-task-classifier-local-continuation.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'core' |  |
| `test-tier0-staged-isolation.sh` | EXEMPT_STILL_FAILS | known-failing | missing file | cp: cannot stat '/tmp/aq-sweep-p21/w1/repo/.agent/collaboration/RESUME.json': No such file or directory |  |
| `test-vector-similarity-search-perf.py` | TIMEOUT | unstable | timeout | scripts/testing/test-vector-similarity-search-perf.py::TestVectorIndexPerformance::test_index_growth_to_100k_vectors |  |
| `test-vscodium-extension-runtime-guards.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError: repair path should prune oversized Gemini and Qwen startup state |  |
| `test-vscodium-gpu-mitigation.py` | EXEMPT_STILL_FAILS | known-failing | unclassified |   - vscodiumArgvJSON = pkgs.writeText "vscodium-argv-baseline.json" |  |
| `test-workflow-automation.py` | EXEMPT_STILL_FAILS | known-failing | missing module | ModuleNotFoundError: No module named 'workflows' |  |
| `test-workflow-deviation-broker.py` | TIMEOUT | slow | timeout | workflow_deviation_transport.TransportUnavailable: socket-unverified |  |
| `test-workflow-orchestration-defaults.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w1/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-workflow-pattern-adoption.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w0/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-workflow-run-policy-overrides.py` | EXEMPT_STILL_FAILS | known-failing | missing file | FileNotFoundError: [Errno 2] No such file or directory: '/tmp/aq-sweep-p21/w0/repo/ai-stack/mcp-servers/hybrid-coordinator/http_server.py' |  |
| `test-worktree-isolation.py` | EXEMPT_STILL_FAILS | known-failing | stale assertion | AssertionError |  |
| `test-write-region.py` | FAIL |  | unclassified |   PASS  out-of-range error includes current_line_count |  |

## Rollback Plan
Delete this report, the sweep script and its test; nothing else was changed.

## Residual Risk and heuristic limits
- Root-cause groups come from regexes over the text around the first failure line (the exception line of the last traceback, or the first FAIL/Error line, with 2 to 3 lines of context). 'stale assertion' and 'real product bug (suspect)' cannot be told apart without reading the test: an AssertionError may be either. A traceback ending in a non-assertion exception is labelled 'real product bug (suspect)'. A test failing for an earlier reason can be filed under a later group, and 'environment' also catches failures caused by this sweep's own isolation (no network, read-only filesystem, mapped uid).
- NO_ASSERTIONS is a textual check on source (no assert/raise/sys.exit/check-helper tokens for .py; no exit/fail/test/grep -q tokens or `set -e` for .sh); a test that delegates asserting to a library or subprocess is a false positive, and one with a decorative `assert True` is a false negative. Only tests that exited 0 are checked.
- TIME_BOMB (static) means a future date literal sits in a test that also reads the wall clock: a candidate, not proof. The exercised second run (libfaketime) covers only passing tests that mention dates or clocks and only when `--faketime-lib` is given.
- FLAKY is one re-run of FAIL results only; TIMEOUT results are not re-run. A test that fails 1 in 10 and passes both times is not detected.
- Tests marked live-service in the exemption list are NOT_RUN unless `--include-live`. A pass in this sandbox (no network, read-only filesystem) is not proof a test passes on the host.
- LIVE_MUTATION is detected by mtime of watched live paths during a test window, which only catches writes to them; the read-only mount is the real guard (an attempted write shows as RO_BLOCKED). TREE_MUTATION means the test wrote inside its private repo clone, which is discarded.

### NOT_RUN reasons

- live-service: 26

### LIVE_MUTATION

- `scripts/testing/test-candidate-lifecycle.py`: /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agent/memory/issues-backlog.md
- `scripts/testing/test-functional-prompt-eval.py`: /home/hyperd/.local/share/nixos-ai-stack
- `scripts/testing/test-gate-checkout.py`: /home/hyperd/.local/share/nixos-ai-stack
- `scripts/testing/test-graph-build.py`: /home/hyperd/.local/share/nixos-ai-stack
Assessment: all four are most likely concurrent writers, not these tests. Every test ran with a read-only filesystem (only its temp dir and a private repo clone writable) and none hit a read-only error; `.agent/memory/issues-backlog.md` is appended by other agents, and the `security` subdirectory of `~/.local/share/nixos-ai-stack` was last modified at 22:41:43, inside the sweep window, by the live stack. The watch cannot prove the absence of a write, only the mount can; no test was skipped by the family stop (every NOT_RUN is a live-service exemption). Not verified: which process wrote the paths.

### Not done
- TIME_BOMB exercised second run (libfaketime via `aq-tool libfaketime`): not run; only the static candidate (test-capability-lease.py, 2026-12-31, already fixed by fix/capability-lease-timebomb) is reported.
- 26 live-service exempt tests: NOT_RUN by design.
- TIMEOUT results (3) not re-run; per-test timeout was 90 s.
