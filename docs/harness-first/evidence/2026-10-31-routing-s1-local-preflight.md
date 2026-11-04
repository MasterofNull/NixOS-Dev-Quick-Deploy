# Harness-First Task Evidence

Date: 2026-10-31
Task ID: HF-20261031-routing-s1-local-preflight

## Objective
- Routing slice S1 (frozen plan, owner freeze 2026-10-31): refuse oversize local work before launch and normalize dispatch evidence in the registry.
- Preflight measures the assembled direct-mode request (system + grounding + role + user prompt, template framing) plus the output allowance against the per-slot context limit. Limit SSOT: the live llama-server `/props` (`n_ctx / total_slots`), falling back to `config/local-model-config.yaml` `inference.ctx_size`. Token count via `/tokenize`; if unreachable, a conservative byte guard (labeled `byte_guard`).
- Implemented in new `scripts/ai/lib/local_preflight.py` (dispatch.py is whole-file pinned by the L2B contract and is left byte-identical; the helper imports its resolution and payload builder unmodified).
- Refusal: exit 3, structured JSON on stderr and in the output file, a `failed`/`outcome=refused` registry row; no worktree, claim, or inference is started.
- Registry rows gain additive fields: `dispatch_id, source, risk, complexity, model_requested, model_effective, effort, requested_lane, effective_lane, substitution_reason, classification_version, policy_version, preflight{method,measured,limit,verdict}, outcome`. Unknowns are `unknown`/`n/a`/null.

## Workflow/Session IDs
- Worktree: .agents/delegation/worktrees/routing-slice1, branch feat/routing-local-preflight. Session ID: n/a (delegated Claude sub-agent, slice S1).

## Delegation Decision
- Bounded slice implemented by a Sonnet sub-agent (Rule 17 balanced tier). Not committed; left for orchestrator review and tier0.

## Commands Executed
```bash
scripts/testing/test-dispatch-preflight.py
python3 scripts/testing/test-local-delegation-artifact.py
python3 scripts/testing/test-delegate-headless-budget.py
python3 scripts/testing/test-claude-dispatch-payload-safety.py
scripts/ai/delegate-to-local --mode direct --no-consult --wait --prompt-file <oversize>   # refused, exit 3
```

## Validation Evidence
- test-dispatch-preflight.py: 6/6 (oversize refused before launch with registry row; output allowance counts toward limit; accepted prompt fits total context and writes no row; byte-guard fallback labeled; registry fields present with honest unknowns; legacy rows still summarize).
- Live dry-run against the running llama-server: 22565 measured tokens vs 8192 limit (`tokenize`, `llama_props`), exit 3, nothing launched.
- Phase-0 check 0.12.9 passes (static wiring plus throwaway-dir oversize fixture).
- Observability: `TaskRegistry.monitor_payload()["dispatch_evidence"]` (refusals, preflight verdicts, coverage by source) flows to `aq-report --machine` (`local_agent_monitor`) and the dashboard Local Inference Queue card.
- Existing readers: legacy keys (`id, agent, role, status, output_file`) unchanged; related existing tests pass. `test-local-agent-monitor-visibility.py` times out at 10s on `--monitor` identically on the unmodified tree (1572-row registry, ~7s), pre-existing.

## Rollback Plan
- Revert the commit. New fields are additive; older readers ignore them. Per-run bypass is not provided by design (a refusal is advisory-free); relax by raising the llama ctx size or lowering `--max-tokens`.

## Residual Risk
- Agent/hybrid/ralph modes: tool-schema overhead is not measured (labeled `agent_tool_schema_excluded`); only prompt plus output allowance is enforced there.
- `source`, `requested_lane`, `risk`, `complexity` stay `unknown` until S2/S3 populate them; gemini records model as `unknown`.
- Template framing (8 tokens/message) and byte guard (2 bytes/token) are conservative, env-overridable constants.
- Activation: requires no rebuild for CLI paths; dashboard backend/JS card is visible after the dashboard restart. Owner activation deferred to the next deploy.

## Hint Feedback
- Hint worked: aq-report/phase0 0.12.5-0.12.8 patterns made the observability surface a one-key addition.
- Friction: `delegate-to-local --monitor` is slow on the large registry (7s), which flakes the 10s monitor test.
