# Harness-First Task Evidence

Date: 2026-11-18
Task ID: HF-20261118-constrained-decoding

## Objective
Owner approved frontier item fe-2ab16cb00ee3 (2026-11-18): constrain every local-model request whose output a machine parses with llama.cpp json_schema decoding. Delivered:
- `attach_json_schema`, `REVIEW_VERDICT_SCHEMA`, `render_review_verdict`, `json_schema_enabled` in `ai-stack/mcp-servers/shared/llm_config.py`. Wire form is `response_format: {type: json_schema, json_schema: {name, schema, strict}}` on `/v1/chat/completions`, the form `scripts/ai/lib/aqos_ai_propose.py` already uses.
- Reviewer path: `DirectRunner` in `scripts/ai/lib/dispatch.py` attaches the verdict schema only when `role == reviewer` AND `AQ_LOCAL_VERDICT_SCHEMA=1` (explicit opt-in, set by aq-land and aq-review-request; rsi_convene reviewer calls are free-text diagnoses and stay unconstrained), then renders the JSON back to the `Reviewed-head-sha:` / `Review-Disposition:` lines that aq-land, aq-review-receipt and aq-review-request read. Raw JSON is kept in `<output>.verdict.json`. Invalid JSON leaves the raw output untouched.
- Guard: `ignore_eos` is dropped whenever grammar, json_schema or a json_schema response_format is present (llama.cpp b12489 answers 400), in both the helper and `build_llama_payload`.
- Kill switch `AQ_LOCAL_JSON_SCHEMA=0`; default ON for the reviewer path.
- Plan dir `.agents/plans/frontier-adoption-20261118/` (VERIFY.md, tracker.json, .plan-classification.json).

Call-site map (machine-read vs free text):
- Constrained: delegate-to-local direct mode with role reviewer and AQ_LOCAL_VERDICT_SCHEMA=1 (aq-land local lane, aq-review-request local lane); both parse the verdict line. Left free: rsi_convene local reviewer (five-line diagnosis); other role=reviewer callers (aq-loop, aq-cascade, aq-collab-round, prsi-orchestrator) go to gemini, not local.
- Already constrained, unchanged: `aqos_ai_propose.py` (response_format json_schema); `agent_executor.py` tool calls (GBNF grammar).
- Left free text: `claude-local-wrapper.py` (chat), `llm_code_reviewer.py` (prose review), the non-reviewer DirectRunner roles (implementer/architect output is read by humans or by agents), hybrid and agent modes (multi-step tool loops; tool calls are already grammar-bound), `local_agent_runtime.py` (loop payloads, not a single parsed record).
- Follow-up candidates, not done: other `task_type=structured` callers once found to parse JSON (none found in ai-stack by rg).

## Workflow/Session IDs
- Workflow ID: none (bounded implementer slice)
- Session ID: Simurg@claude/sonnet, dispatched by Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
Delegated by the orchestrator to a Claude sonnet implementer under Rule 17 (explicit cheap-model override). Review by an independent lane is pending; the implementer does not review its own work.

## Commands Executed
```bash
git -C <repo> worktree add -b feat/constrained-decoding .agents/delegation/worktrees/constrained-decoding origin/main
python3 scripts/testing/test-constrained-decoding.py
python3 scripts/testing/test-plans-index.py
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
curl -s -m 30 localhost:8080/slots
python3 <scratchpad>/baseline.py   # baseline method below
```

Baseline method (format-failure rate of machine-read local runs):
1. Take `.agents/delegation/registry.jsonl` rows whose agent starts with `local` (1368 of 2043 rows).
2. Machine-read = `role == reviewer` or the prompt demands `Review-Disposition` / `Reviewed-head-sha` / strict JSON (286 runs).
3. Keep runs whose output file still exists (33; 253 were pruned).
4. A format failure is TRUNCATED in the output, or a done run with no valid `Review-Disposition: PASS|PASS_WITH_FOLLOWUPS|REQUEST_CHANGES` line.
Result: 27 done, 0 format failures (0.0%). 6 runs had status failed (timeout x1, context-limit refusal x3, agent-loop exit x2); none is a format failure. Across all 154 surviving local outputs, 0 contain TRUNCATED. `.usage.json` finish_reason sidecars do not exist in the history, so length-cut stops cannot be counted. The baseline is therefore small and already near zero; the gain this slice buys is a structural guarantee plus a metric that keeps being measured, not a large measured drop. Recorded in VERIFY.md row 1.

## Validation Evidence
- `scripts/testing/test-constrained-decoding.py` (stub llama.cpp HTTP server): schema attached as response_format; `ignore_eos` stripped with a schema (helper and build_llama_payload, three schema forms); `AQ_LOCAL_JSON_SCHEMA=0` sends the free-text payload; the reviewer output still has the `Reviewed-head-sha:` and `Review-Disposition:` lines and a `.verdict.json` sidecar; no source file mixes `ignore_eos` with grammar/json_schema. Output: `PASS test-constrained-decoding`.
- Live llama.cpp request: SKIPPED. `curl localhost:8080/slots` showed slot 0 `is_processing: true`; the slot-busy rule forbids a request. The schema field name is the one already live in `aqos_ai_propose.py`, but the end-to-end behaviour of `pattern` and `maxLength` under this pinned build is unverified until the first live reviewer run (first run after rebuild/restart is the check).
- Tier0 / static gates / plans-index: see the commit trail and the orchestrator report.

## Rollback Plan
Set `AQ_LOCAL_JSON_SCHEMA=0` in the delegation environment: reviewer runs return to free text with no code change. Full rollback: revert the commit `feat(local): json_schema-constrained decoding for machine-read local outputs`. Trigger: any reviewer run with no verdict line, a 400 from llama.cpp, or a rise in TRUNCATED on schema runs.

## Residual Risk
- No live llama.cpp verification yet (slot busy). If this build rejects `pattern` or `maxLength`, reviewer runs will fail with a 400; the kill switch is the mitigation.
- `maxLength` 1500 on notes limits review detail; findings must fit in about 400 tokens. `max_tokens` 900 leaves room for the other fields.
- Constrained output is guaranteed well formed, not correct: the head sha is still checked by aq-land against the real head.
- Sample for the baseline is small (33 of 286 runs); the 14-day review in VERIFY.md uses the new metric against real data.

## Hint Feedback
- No aq-hints queried for this bounded slice; no hint IDs used.
