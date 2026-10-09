# Capability triage 2026-10-09 (plan item ci-6, parity-rule amendment)

Owner directive (binding): unused or unreferenced is never sufficient grounds to archive. An item is archived only when a named, working equivalent exists (`superseded_by` evidence) or its approach was deliberately replaced (RETIRE-WITH-REASON, owner review below). Otherwise it is revived and wired, or kept in place with a real hook.

## Retired (owner review)

These stay archived under archive/deprecated/20261009-capability-triage/ with no full equivalent; each is obsolete by design. Reverse any with `git mv archive/deprecated/20261009-capability-triage/scripts/ai/<name> scripts/ai/<name>`.

| item | why retired | closest partial equivalent |
|---|---|---|
| ai-commit-simple | Commits with git add -A and no tier0 gate, 72-char head-only messages; violates commit discipline and commit-verbosity policy. Message suggestion can be re-added to aq-commit-agent if wanted. | Partial only: aq-commit-agent (tier0-gated explicit-path commit, no message generation); /commit skill |
| ai-env-summary.sh | Profile selection is now declarative Nix (nix/modules/profiles/*, nix/hosts/*/facts.nix); the env vars it prints are installer-era and read by nothing else. | Partial: aq-model --active (model catalog), aq-system-state, scripts/governance/edge-model-registry-validate.sh |
| ai-validate-and-commit | Mandated review-before-commit flow already exists with independent reviewers; this one hardcodes ~/.npm-global/bin/qwen and commits with git add -A, bypassing tier0 and trunk protection. | Review: delegate-to-local --role reviewer, aq-local-review, reviewer-gate skill; commit: aq-commit-agent |
| export-container-config | Nix is the single source of truth (feedback-nix-single-source-no-bloat 2026-10-01): no parallel Docker layers. Its guide lives only in docs/archive/legacy-2025. | None by design |
| local-harness-proxy.py | Self-declared superseded by the MCP bridge; arbitrary command execution from a writable file has no allowlist (Rule 7). .agent/comms files are empty placeholders. | Native MCP: scripts/ai/mcp-bridge-hybrid.py (wired in nix/home/base.nix) for coordinator tools; aq-agent-loop / lean-ctx ctx_shell for command execution |
| optimize-and-validate.sh | Session-bound (hardcoded tools/target, placeholder 'apply' step) and broken: depends on aq-report JSON key tool_performance that no longer exists. Generic before/after delta could be added as `aq-report --compare` (follow-up). | Partial: aq-report trend vs 24h baseline, aq-optimizer, aq-inference-bench |
| test-ux-improvements.sh | Verified failing on its first assertion: dashboard.html no longer contains empty-state, success-toast, NotificationManager, KeyboardShortcutsManager etc. Asserts removed UI. | Dashboard UI replaced; new smoke test scripts/testing/test-revived-capabilities-smoke.sh covers the revived UX libs |

## Decision counts

- Set A (17 archived by the first pass): ARCHIVE=6, REVIVE-INTEGRATE=4, RETIRE-WITH-REASON=7, MERGE-INTO=0
- Set B (16 OWNER-DECISION): ARCHIVE=4, REVIVE-INTEGRATE=12, RETIRE-WITH-REASON=0, MERGE-INTO=0
- Unchanged from first pass: KEEP-DECLARED=23, KEEP-HOST-SPECIFIC=10, REVIVE-WIRE=3 (listed at the end)

REVIVE-INTEGRATE for set B means kept in place (never archived) and given a real hook. The 7 ai-stack legacy shims are a judgment call: equivalents exist, but the shims are pinned by scripts/testing/verify-flake-first-roadmap-completion.sh (CI and nixos-quick-deploy.sh), so archiving needs that verifier edited; the owner may still archive the group together with its verifier entries.

Machine-readable copy: `decisions` in config/capability-triage.json. Smoke test: scripts/testing/test-revived-capabilities-smoke.sh.

## Set A: the 17 scripts archived by the first pass

| item | function | parity equivalent (evidence) | decision | reason |
|---|---|---|---|---|
| adk-discovery-workflow.sh | Weekly grep-scored ADK parity self-assessment + discovery log | lib/l4-coord/adk/implementation-discovery.sh + parity-tracker.py (dashboard/backend/api/routes/adk.py calls both; scripts/testing/test-adk-integration.py; scripts/automation/adk/schedule-discovery.sh) | ARCHIVE | Same-day (2026-03-20) superset: release monitoring, parity tracker, dashboard API, scheduler. |
| ai-commit-simple | Suggest a one-line commit message from the diff via local /query, then git add -A + commit | Partial only: aq-commit-agent (tier0-gated explicit-path commit, no message generation); /commit skill | RETIRE-WITH-REASON | Commits with git add -A and no tier0 gate, 72-char head-only messages; violates commit discipline and commit-verbosity policy. Message suggestion can be re-added to aq-commit-agent if wanted. |
| ai-env-summary.sh | Print legacy HOST_PROFILE/AI_PROFILE/AI_STACK_PROFILE env + edge-model registry count | Partial: aq-model --active (model catalog), aq-system-state, scripts/governance/edge-model-registry-validate.sh | RETIRE-WITH-REASON | Profile selection is now declarative Nix (nix/modules/profiles/*, nix/hosts/*/facts.nix); the env vars it prints are installer-era and read by nothing else. |
| ai-validate-and-commit | Local-agent diff review (APPROVE/REJECT) then commit with generated message | Review: delegate-to-local --role reviewer, aq-local-review, reviewer-gate skill; commit: aq-commit-agent | RETIRE-WITH-REASON | Mandated review-before-commit flow already exists with independent reviewers; this one hardcodes ~/.npm-global/bin/qwen and commits with git add -A, bypassing tier0 and trunk protection. |
| aq-enrich-plans | CLI client that annotates .agents/plans/*.md with tool sequences via coordinator /tools/enrich-plan | None for the CLI: server endpoint exists (auto_tool_select_handlers.py) and MCP auto_select_tools/tool_catalog cover per-task lookup, but nothing batch-annotates plan files | REVIVE-INTEGRATE | Revived to scripts/ai/aq-enrich-plans; added --help. Trigger: `aq enrich-plans` (router auto-discovery) + hints rule annotate_plans_with_tools. |
| aq-propose | Render .agents/proposals/<id>.md from high-trust candidates.json (Phase 153) | None: sole producer of .agents/proposals (11 live files); candidates.json still written by improvement_detector.py | REVIVE-INTEGRATE | Revived to scripts/ai/aq-propose; added --dry-run/--help. Trigger: `aq propose` + hints rule generate_improvement_proposals. |
| aq-qa-agent | Machine-readable aq-qa | scripts/ai/aq-qa --machine (same flag; aq router `aq qa`) | ARCHIVE | Exact wrapper of the live flag; the wrapper also used a cwd-relative path. |
| autonomous-coordinator-simple.sh | Execute pending roadmap batches via CLI delegation, auto-commit | scripts/ai/aq-loop-queue (+aq-loop; --no-fanout for local-only) drains the backlog sequentially | ARCHIVE | Reads NEXT-GEN-AGENTIC-ROADMAP-2026-03.md, which no longer exists; auto-commits with git add -A bypassing tier0. |
| autonomous-coordinator.sh | Same, via delegate-to-claude | scripts/ai/aq-loop-queue + aq-loop | ARCHIVE | Same as autonomous-coordinator-simple.sh. |
| bash-completion.sh | Tab completion for aq-report, deploy, aq-orchestrator, dashboard | scripts/ai/aq-completions.sh (_aq_report_complete, router, aq-hints; installed by nix ai-stack.nix when mySystem.aiStack.shellCompletions, default true in ai-dev profile) | ARCHIVE | Only aq-report completion was real and is covered; the others complete commands that do not exist (aq-orchestrator absent, generic deploy/dashboard). |
| cli-enhanced.sh | Bash UX helpers: spinner, run_with_spinner, humanize_bytes/duration, print_table, show_error, progress, confirm | Partial only: lib/l7-interaction/user-interaction.sh + progress.sh cover print_*, confirm, progress bar; no spinner/humanize/table/show_error | REVIVE-INTEGRATE | Revived to scripts/ai/cli-enhanced.sh (source-able). Trigger: hints rule cli_output_helpers + smoke test. Merge into lib/l7-interaction left as follow-up (not small). |
| cli-utils.py | Python UX helpers: Logger, ProgressBar, Spinner, confirm, ContextualError, format_table, humanize_* | None: no Python equivalent in repo (rg for humanize/Spinner/ProgressBar finds nothing live) | REVIVE-INTEGRATE | Revived to scripts/ai/cli-utils.py. Trigger: hints rule cli_output_helpers + smoke test (humanize assertions). |
| export-container-config | Generate Docker/Podman compose + env for a standalone containerized AI stack | None by design | RETIRE-WITH-REASON | Nix is the single source of truth (feedback-nix-single-source-no-bloat 2026-10-01): no parallel Docker layers. Its guide lives only in docs/archive/legacy-2025. |
| local-harness-proxy.py | File-drop bridge: runs shell commands from .agent/comms/command.json | Native MCP: scripts/ai/mcp-bridge-hybrid.py (wired in nix/home/base.nix) for coordinator tools; aq-agent-loop / lean-ctx ctx_shell for command execution | RETIRE-WITH-REASON | Self-declared superseded by the MCP bridge; arbitrary command execution from a writable file has no allowlist (Rule 7). .agent/comms files are empty placeholders. |
| mcp-db-setup | Renamed alias to mcp-db-validate | scripts/ai/mcp-db-validate (the exec target itself) | ARCHIVE | Pure rename shim. |
| optimize-and-validate.sh | One-off 2026-04-09 optimization session: baseline vs optimized aq-report p95 for 3 tools, 50% target | Partial: aq-report trend vs 24h baseline, aq-optimizer, aq-inference-bench | RETIRE-WITH-REASON | Session-bound (hardcoded tools/target, placeholder 'apply' step) and broken: depends on aq-report JSON key tool_performance that no longer exists. Generic before/after delta could be added as `aq-report --compare` (follow-up). |
| test-ux-improvements.sh | Phase 6.2 structural test of dashboard.html UX features + UX bundle files | Dashboard UI replaced; new smoke test scripts/testing/test-revived-capabilities-smoke.sh covers the revived UX libs | RETIRE-WITH-REASON | Verified failing on its first assertion: dashboard.html no longer contains empty-state, success-toast, NotificationManager, KeyboardShortcutsManager etc. Asserts removed UI. |

## Set B: the 16 owner-decision items

| item | function | parity equivalent (evidence) | decision | reason |
|---|---|---|---|---|
| ai-metrics-auto-updater.sh | Legacy-name shim: bounded refresh loop over collect-ai-metrics.sh | Wrapped tool scripts/observability/collect-ai-metrics.sh; shim itself pinned by verify-flake-first-roadmap-completion.sh (CI tests.yml + nixos-quick-deploy.sh) | REVIVE-INTEGRATE | Kept in place: archiving would break the CI/deploy verifier; wired via hints rule legacy_ai_stack_script_names; smoke --help. |
| ai-model-setup.sh | Legacy shim over ai-model-manager.sh / update-llama-cpp.sh | ai-model-manager.sh, update-llama-cpp.sh, aq-model; CI-pinned | REVIVE-INTEGRATE | Same as ai-metrics-auto-updater.sh. |
| ai-stack-e2e-test.sh | Legacy shim: aq-qa 0, aq-qa 1, real-world workflow smoke | aq-qa + scripts/testing/test-real-world-workflows.sh; CI-pinned | REVIVE-INTEGRATE | Same. |
| ai-stack-feature-scenario.sh | Legacy shim over aq-context-bootstrap / workflow smoke | aq-context-bootstrap; CI-pinned | REVIVE-INTEGRATE | Same. |
| ai-stack-resume-recovery.sh | Legacy shim over aq-system-act / aq-runtime-act | aq-system-act, aq-runtime-act; CI-pinned | REVIVE-INTEGRATE | Same. |
| ai-stack-troubleshoot.sh | Writes artifacts/troubleshooting bundle (failed units, aq-qa 0, dashboard health) | Partial: aq-runtime-plan / aq-runtime-diagnose do not write this bundle; tested by tests/unit/ai-stack-troubleshoot.bats | REVIVE-INTEGRATE | Kept in place (has a bats test, unique bundle output); hints rule; bash -n smoke (run needs live services). |
| llama-model-cli.sh | Legacy shim: model status/logs/debug/update/reload | ai-model-manager.sh, aq-llama-debug, aq-model; CI-pinned | REVIVE-INTEGRATE | Same as ai-metrics-auto-updater.sh. |
| aq-factory | One-command skill scaffolder | None: template-skill is copy-by-hand; lint-skill-template.sh only lints; aq-skill-factory starts from gap patterns | REVIVE-INTEGRATE | Old output (no frontmatter, 'Not implemented' __init__.py) failed the current skill lint contract. Rewritten to emit name/description frontmatter SKILL.md; added --root/--dry-run. Trigger: `aq factory` + hints rule scaffold_new_skill. |
| aq-push-intelligence | Extract lessons from aq-insights and push to AIDB agent-intelligence | ai-crystallize-sessions timer running scripts/ai/aq-crystallize (nix ai-stack.nix:2156), aq-lesson-promote, coordinator lessons (ai_coordinator_handlers.py) | ARCHIVE | The push was SIMULATED (log only). Removed its existence/run test from tests/integration/test-phase5-production-hardening.py. |
| aq-skill-factory | Draft skill stubs from delegation gap_patterns (PAEA 89.5) | None: training_ingest still emits gap_patterns; .agent/skills/auto-generated holds its output | REVIVE-INTEGRATE | Kept in place; hints rule scaffold_new_skill; smoke --help. |
| autonomous-coordinator-local.sh | Local-only (aq-hints + local model) roadmap batch executor | scripts/ai/aq-loop-queue --no-fanout (local-only) | ARCHIVE | Roadmap file it reads is gone; auto-commit bypasses tier0. Dropped its mention from config/aq-integrity-logical-orphans.json. |
| backfill-interaction-history-qdrant.py | Backfill AIDB interaction_history into Qdrant interaction-history | None: aq-vector-reconcile covers imported_documents->knowledge, not interaction-history | REVIVE-INTEGRATE | Kept in place (operator tool; a DB backfill is running now, not executed). Hints rule; --help smoke only. |
| generate-module-dashboard.py | Generate assets/modules/*.html from system-capability-catalog.json (linked from dashboard.html) | None: aq-capability-catalog renders markdown only | REVIVE-INTEGRATE | Actively used; added --out-dir for safe preview; hints rule regenerate_module_dashboard_pages; smoke generates into tmp. |
| prime-local-agent | Markdown context dump for a local agent (service status, quick commands) | scripts/ai/aq-prime (health check, roles, progressive disclosure, --format json; mandated in CLAUDE.md session start); /primer workflow | ARCHIVE | Refers to missing .agent/LOCAL-AGENT-HARNESS-PRIMER.md. |
| render-continue-config.sh | Render Continue.dev config.json from template with port substitution | nix/home/base.nix home.activation.createContinueConfig (config version 34.0, switchboard-profile driven) | ARCHIVE | Template no longer contains the shell variables it substitutes, so the script was a no-op copy. |
| resume-model-download.sh | Byte-range resumable model download | Partial: llama-cpp-model-fetch (nix ai-stack.nix:1185) retries but restarts from zero (no curl -C -) | REVIVE-INTEGRATE | Generalised from hardcoded Qwen3.6 Q4: --repo/--file/--dest-dir/--dry-run. Hints rule resume_interrupted_model_download. |

## Unchanged first-pass decisions

| item | decision | evidence |
|---|---|---|
| aq-adopt-workflow | KEEP-DECLARED | operator-run adoption helper; referenced by harness_qa phase0 and aq-integrity-logical-orphans.json |
| aq-bitnet-compare.py | KEEP-DECLARED | BitNet benchmarking for bitnet-profile hosts; has test-bitnet-compare.py |
| aq-capability-flush | KEEP-DECLARED | operator/agent-lane flush tool; has test-capability-flush.py |
| aq-capability-shadow | KEEP-DECLARED | Foundation-C capability-lease shadow admission (schema + test-capability-lease-issuance.py); gitignored shadow records |
| aq-coach-events | KEEP-DECLARED | local-agent coach telemetry reader; has test-aq-coach-events.py |
| aq-editor-rescue | KEEP-DECLARED | editor-state recovery, documented in EDITOR-STATE-RECOVERY-RUNBOOK.md; has test |
| aq-factory-push | KEEP-DECLARED | factory-pack fp-2 outward push (2026-09), companion of aq-factory-pack; operator-run by design |
| aq-index-knowledge-graph | KEEP-DECLARED | GraphRAG index builder (phase0 check, env-contract.yaml, test-aq-index-knowledge-graph.py) |
| aq-llama-benchmark.py | KEEP-DECLARED | inference benchmark; has test-llama-benchmark.py; PROJECT-AQ-INFERENCE-BENCH-PRD |
| aq-llama-staging-status.py | KEEP-DECLARED | llama staging status reader; has test-llama-staging-status.py |
| aq-local-dogfood-run | KEEP-DECLARED | local-agent dogfood runner; 3 guard tests, in suspend-resume-workloads.json |
| aq-local-review | KEEP-DECLARED | local-embed review lane (July); has test-aq-local-review.py |
| aq-model-eval | KEEP-DECLARED | probes loaded llama.cpp model and writes model-profile.json; operator-run after model load |
| aq-prm-eval | KEEP-DECLARED | FE-1 process-reward steering A/B (2026-10-08 evidence doc); operator-run eval |
| aq-qdrant-prune-test-collections | KEEP-DECLARED | Qdrant test-collection hygiene; operator-run, covered by test_vector_routing_collections.py |
| aq-worktree-reap | KEEP-DECLARED | zero-change delegate worktree reaper (2026-10-07); has test-aq-worktree-reap.py |
| aq-worktree-write-guard | KEEP-DECLARED | wired by .claude/settings.json PreToolUse hook (outside audit scan trees); has test |
| mcp-aidb | KEEP-DECLARED | MCP stdio helper launched from external MCP client config (outside repo); keep |
| mcp-hybrid-coordinator | KEEP-DECLARED | MCP stdio bridge launched from external MCP client config (outside repo); keep |
| project-import | KEEP-DECLARED | generic skill; skills rarely log use; mirrored in ai-stack/agents/skills |
| slack-gif-creator | KEEP-DECLARED | generic imported skill; rarely used, listed in aq-integrity-logical-orphans.json |
| sync-workflow-sessions.py | KEEP-DECLARED | named as state authority in config/system-state-authorities.yaml and aqos ADRs |
| template-skill | KEEP-DECLARED | skill authoring template, intentionally never invoked |
| activation-auto-revert | KEEP-HOST-SPECIFIC | Nix-declared, option-gated unit (disabled by default or on this host only); enabled per host/profile; ai-dev profile opt-in (default false), has test-activation-auto-revert-guard.py |
| ai-headroom-proxy | KEEP-HOST-SPECIFIC | Nix-declared, option-gated unit (disabled by default or on this host only); enabled per host/profile; headroom payload-compression proxy (Phase 164) |
| aq-auto-update-check | KEEP-HOST-SPECIFIC | Nix-declared, option-gated unit (disabled by default or on this host only); enabled per host/profile; U3 unattended-update pipeline, default off |
| aq-auto-update-run | KEEP-HOST-SPECIFIC | Nix-declared, option-gated unit (disabled by default or on this host only); enabled per host/profile; U3 unattended-update pipeline, default off, in suspend-resume-workloads.json |
| audit-rules-nixos | KEEP-HOST-SPECIFIC | Nix-declared in core/logging.nix (SuccessExitStatus override of upstream audit-rules unit); not an own unit |
| battery-charge-thresholds | KEEP-HOST-SPECIFIC | laptop-only hardware module nix/modules/hardware/mobile.nix; not applicable on desktop hosts |
| llama-router | KEEP-HOST-SPECIFIC | Nix-declared, option-gated unit (disabled by default or on this host only); enabled per host/profile; llama.cpp router service (enable option) |
| meta-optimization-analysis | KEEP-HOST-SPECIFIC | Nix-declared, option-gated unit (disabled by default or on this host only); enabled per host/profile; meta-optimization.nix |
| meta-optimization-applier | KEEP-HOST-SPECIFIC | Nix-declared, option-gated unit (disabled by default or on this host only); enabled per host/profile; meta-optimization.nix |
| meta-optimization-validator | KEEP-HOST-SPECIFIC | Nix-declared, option-gated unit (disabled by default or on this host only); enabled per host/profile; meta-optimization.nix |
