# Capability triage 2026-10-09 (plan item ci-6)

Input: aq-capability-audit DEAD-CANDIDATE = 69. After: see counts below.

Decision counts: ARCHIVE=17, KEEP-DECLARED=23, KEEP-HOST-SPECIFIC=10, OWNER-DECISION=16, REVIVE-WIRE=3

KEEP-DECLARED items are recorded in config/capability-triage.json (read by capability_audit.py, class KEEP-DECLARED). ARCHIVE items moved with git mv to archive/deprecated/20261009-capability-triage/. REVIVE-WIRE items got a hints rule in static_rules.py. Units are all Nix-declared option-gated modules; none archived.

| item | decision | evidence |
|---|---|---|
| adk-discovery-workflow.sh | ARCHIVE | Mar 2026 ADK experiment; refs only in roadmap docs |
| ai-commit-simple | ARCHIVE | May; superseded by commit skill + tier0 flow; zero refs outside generated graph |
| ai-env-summary.sh | ARCHIVE | Mar cleanup leftover; only a repo-structure-allowlist line (harmless stale entry) |
| ai-validate-and-commit | ARCHIVE | May; bypasses tier0 commit discipline; zero refs outside generated graph |
| aq-enrich-plans | ARCHIVE | May impeccable-integration helper; zero refs, no tests |
| aq-propose | ARCHIVE | June proposal generator; zero refs, no tests |
| aq-qa-agent | ARCHIVE | 19-line wrapper of 'aq-qa --machine' (cwd-relative path); redundant, zero refs |
| autonomous-coordinator-simple.sh | ARCHIVE | same as autonomous-coordinator.sh; docs-only refs |
| autonomous-coordinator.sh | ARCHIVE | May: phase-c2 archived its siblings; refs docs only, no code/test/Nix |
| bash-completion.sh | ARCHIVE | Mar UX bundle; only referenced by test-ux-improvements.sh; archived together |
| cli-enhanced.sh | ARCHIVE | Mar UX bundle; only referenced by test-ux-improvements.sh; archived together |
| cli-utils.py | ARCHIVE | Mar UX bundle; only referenced by test-ux-improvements.sh; archived together |
| export-container-config | ARCHIVE | Mar 2026 container spinoff (docs/archive/legacy-2025 only); no refs |
| local-harness-proxy.py | ARCHIVE | self-declared 'Superseded by the native MCP bridge'; zero refs |
| mcp-db-setup | ARCHIVE | Mar cleanup leftover; only a repo-structure-allowlist line (harmless stale entry) |
| optimize-and-validate.sh | ARCHIVE | Apr session artifact; refs only in 2026-04-09 session summaries |
| test-ux-improvements.sh | ARCHIVE | tests only the archived UX bundle; not in tier0/CI |
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
| ai-metrics-auto-updater.sh | OWNER-DECISION | Mar compat shim, in repo-structure-allowlist + script-header-waivers + verify-flake-first-roadmap-completion.sh; recommend: archive shim group together with that verifier after owner OK |
| ai-model-setup.sh | OWNER-DECISION | compat shim group (see ai-metrics-auto-updater.sh) |
| ai-stack-e2e-test.sh | OWNER-DECISION | compat shim group |
| ai-stack-feature-scenario.sh | OWNER-DECISION | compat shim group |
| ai-stack-resume-recovery.sh | OWNER-DECISION | compat shim group |
| ai-stack-troubleshoot.sh | OWNER-DECISION | compat shim group; also tests/unit/ai-stack-troubleshoot.bats |
| aq-factory | OWNER-DECISION | May Toolbox Factory skill generator; 36 lines; unclear if superseded by aq-skill-factory/aq-factory-pack; recommend: archive |
| aq-push-intelligence | OWNER-DECISION | simulated AIDB push stub, but referenced by tests/integration/test-phase5-production-hardening.py; recommend: archive stub with that test |
| aq-skill-factory | OWNER-DECISION | PAEA Phase 89 skill-stub generator; auto-generated skills cite it as provenance; recommend: keep-declare if learning loop still feeds gap_patterns, else archive |
| autonomous-coordinator-local.sh | OWNER-DECISION | listed in config/aq-integrity-logical-orphans.json; recommend: archive with the other two and drop the orphan entry |
| backfill-interaction-history-qdrant.py | OWNER-DECISION | one-shot backfill (June); a DB backfill is running now; recommend: keep-declare as operator tool |
| generate-module-dashboard.py | OWNER-DECISION | 941 lines, edited July-Oct, referenced in plans; may feed html-learning-docs; recommend: keep-declare |
| llama-model-cli.sh | OWNER-DECISION | compat shim group |
| prime-local-agent | OWNER-DECISION | Apr context dump for local agent; may overlap aq-prime; referenced in a codex review note; recommend: archive if aq-prime covers it |
| render-continue-config.sh | OWNER-DECISION | Continue.dev config renderer; ai-stack/continue/config.json exists but template missing; recommend: archive unless Continue is used |
| resume-model-download.sh | OWNER-DECISION | cited as a recovery step in qwen-36-switch-recovery-plan.md; recommend: keep-declare |
| aq-claim | REVIVE-WIRE | advisory slice/path claim registry (2026-09 hardened); added hints rule parallel_lanes_claim_paths |
| aq-transcribe | REVIVE-WIRE | local video/audio transcription for research (2026-09); added hints rule transcribe_media_locally |
| aq-verify-committed | REVIVE-WIRE | pipe-immune committed-bytes check (2026-07); added hints rule verify_committed_bytes_not_piped_hash in static_rules.py |
