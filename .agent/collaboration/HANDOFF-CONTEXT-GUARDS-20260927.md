# Start here — context guards and agentic infrastructure

Owner priority: memory/cache/context/token accounting and supporting tools are high-priority core infrastructure. Verify structure, actual use, implementation, enablement, and telemetry across ALL models. Previous MVP/security review work is dropped from active scope. Antigravity owns ACP; do not activate security/containment.

## Established
- Prior thread: 56 Astra requests, 6.32M input, 97.5% cached; no native compaction. After low-budget warning: 19 requests/2.82M input. Full RCA: `.agent/memory/token-burn-20260927.md`.
- Native Codex auto-compaction: 50,000 total tokens installed in ~/.codex/config.toml and .codex/config.toml; persisted via nix/home/base.nix. Private `config.toml.before-context-guard` backups alongside each. CLI config loading succeeds. Previous running thread did NOT reload: verifier measured 197,497 input and returned handoff_required.
- `scripts/ai/aq-session-compact` is read-only. `--verify-rollout PATH` checks Codex native event + subsequent measured decrease. `--verify-usage JSON` applies provider-neutral evidence contract and ceiling min(50000, 80% model window). Only verified decrease returns 0; unknown/pending/oversized return 2.
- Shared canon projects measured guard/priority to all agent instructions. This is NOT universal runtime enforcement.

## Next, without broad discovery
1. DONE in resumed session `01a0e46b-02d9-73f2-8475-6976b698ae11`: native compaction event observed; measured input decreased from 50,958 to 30,523 tokens. `scripts/ai/aq-session-compact --verify-rollout /home/hyperd/.codex/sessions/2026/09/27/rollout-2026-09-27T12-50-13-01a0e46b-02d9-73f2-8475-6976b698ae11.jsonl` returned exit 0, `verified_reduction`. Both configuration files still specify 50,000. Five verifier tests rerun: PASS. This proves this Codex session only; other providers remain unverified.
2. Wire supported native compaction/fresh-session adapters and telemetry for Claude, Gemini/Antigravity, local, future lanes to the SAME contract. These runtime adapters are NOT implemented. Do not delete transcripts, fake token counts, or apply a local-model ceiling to remote models.
3. Repair memory persistence: aq-memory printed success after permission failure; save_working_memory returned 500. store_memory only returned queued. Repository checkpoints remain the reliable fallback.
4. Audit cache/retrieval and request/poll amplification using measured usage. No full-history forks; bounded paths/outputs; no repeated model-driven gate polling.

## Validation / integration
5 tests PASS: `python3 scripts/testing/test-aq-session-compact.py` (includes provider parity, stale/unknown/oversized cases). py_compile, Nix parse, canon check, changed-code whitespace check PASS. Previous rollout correctly failed closed with handoff_required; resumed session now verifies reduction (see step 1).
No new commit: shared checkout/index contains unrelated peer work. Full integration gate NOT passed; old gate exceeded its bound. Do not sweep-stage or rewrite peer changes. Focused previous workspace fixes passed 16 tests, remain separate.
PRD: `.agent/PROJECT-CODEX-CONTEXT-GUARD-PRD.md`. Implementation: `scripts/ai/aq-session-compact`; policy: `canon/blocks/memory-cache-sop.md`. Read these bounded sections only as needed.

Provider-neutral JSON fields: session_id, input_tokens (TOTAL including cache), context_window_tokens, before_input_tokens, compaction_observed, before_request_sequence, request_sequence. Adapters must ensure one session, actual measurements, and increasing sequence.

## Resumed slice result — 2026-09-27
- Fixed aq-memory false success: `_save` now propagates persistence exceptions. Four subprocess tests cover text add, JSON store, reload in a new process, and failed expire. Existing directory as storage reproduces the swallowed write exception; pre-fix script returned exit 0/status added.
- Implementer: memory_fix (aq_implementer). Root Codex reviewed the exact small diff and corrected initial inadequate regression cases; reran four tests successfully. py_compile and whitespace checks pass. No storage ownership change and no live fact-file mutation.
- Full tier0 NOT passed: focused CI was terminated at the 120-second bound; sandbox QA evidence lock failed read-only. Gate continued after TERM and was explicitly interrupted. Escalated QA retry produced no result before interruption; do not report QA success. No commit created.
- Next: complete integration validation, repair store ownership declaratively and diagnose coordinator working-memory HTTP 500. Then implement other-provider adapters and audit cache/retrieval amplification. `store_memory` queued remains insufficient durability evidence.
- Repository checkpoints retained because working-memory MCP save returned HTTP 500; get reported absent. ACP/security ownership boundary unchanged.

## Subagent payload diagnosis — 2026-09-27
Measured native Codex rollouts, not estimated billing: memory_failure first request 31,353 input tokens; memory_fix 31,438, despite task-only forks. Final cumulative child input 223,088 + 812,149 = 1,035,237, of which 881,920 cached. These are replayed input totals, not unique content or billable-equivalent tokens. Deduplicated usage updates: explorer 6, implementer 21; raw token_count events overcount requests. Parent had 12 exec calls containing write_stdin, adding polling round trips.
Role TOMLs are short, with economical model choices and nested agents disabled. They omit per-role MCP/skill configuration; official Codex docs confirm omitted mcp_servers and skills.config inherit parent settings. Child recorded developer messages approximately 54k characters and user messages approximately 26k characters; these serialized totals are not a clean first-request component breakdown. Main demonstrated drivers: substantial initial context and repeated model turns; tool output also accumulated. Cache was working. No evidence yet attributes this chat's consumption to coordinator routing or orphan processes. Both native children completed. Host process names alone cannot establish outbound model traffic.
Next bounded slice: preserve mandatory safety/ownership instructions, select narrow role profiles dynamically, explicitly disable irrelevant optional MCP servers/skills per role, retain task-only forks, supply file pointers and acceptance criteria, and reduce polling. Measure first-request input and cumulative uncached/cached usage on the same small task before/after. Do not silently truncate AGENTS.md or claim savings before measurement. Official reference: https://learn.chatgpt.com/docs/agent-configuration/subagents .

## Implemented role guard slice — 2026-09-27
Installed the three role TOMLs into the active `/home/hyperd/.codex/agents/` path and mirrored them under the repository `.codex/agents/` source files. Each role now sets `mcp_servers = {}` to prevent inherited optional MCP schemas and has a bounded output/read contract: explorer evidence (max 8 bullets), implementer owned files plus compact change/validation/blocker report, reviewer exact subject plus compact verdict. TOML parsing passed for all active role files. This narrows optional payload surface while preserving repository AGENTS.md as mandatory policy. No new child was launched solely for benchmarking because the objective is to reduce token burn; before/after savings remain unmeasured.

## Implemented progressive-disclosure contract — 2026-09-27

### Recovery and PRSI budget slice — 2026-09-28

RSI dispatch now synchronizes incidents without model-backed aq-report. Both ordinary execution and RSI reserve estimated tokens under one state-file lock before launching work; failed attempts retain reservations and dry runs do not charge. Focused intake and budget tests pass, including four simultaneous reservation processes and optimizer failure/timeout. This bounds estimates, not actual provider usage.

The previous tier0 session disappeared during recovery: PID absent, checkout available, tool session unknown. Its completion result is unverified. Do not infer PASS. No unattended repair activation or deployment performed. Next: finish gate validation, fix writable isolated execution under existing protections, queue concurrency/crash recovery, and measure real token attribution. Existing dirty/staged peer work must be preserved.

Recovery friction: aq-event resume rejected an invented --next-action flag; --help confirmed --hint and corrected command succeeded. A no-match zsh report glob also failed; use bounded rg discovery instead. Avoid repeating either command.

Recovery continuation: tier0 completed with 51 passed gates and two failures: stale minimum-three-Ralph-timers assertion and three mvp-delivery-sop canon regions. Fixed timer assertions; focused CI rerun passed 56 checks (`/tmp/prsi-budget-focused-ci.json`). Regenerated canonical blocks with canon-compile.py --write; --check passes. Live phase0 passed 189 checks in `/tmp/prsi-budget-tier0.log`. Original gate remains failed; no clean integrated rerun, commit or deployment claimed. New unstaged PRSI tests ran explicitly; staged-only focused selection did not include them. For pulses use `aq-event pulse --agent codex --action "description" --scope path`; `--message` is invalid. Keep these exact verified arguments in recovery context.

Added the same strict always-on envelope and fetch-on-demand triggers to `.agent/WORKFLOW-CANON.md`, `.agent/CODEX.md`, `CLAUDE.md`, `.agent/LOCAL-AGENT.md`, and `.agent/GEMINI.md`. Delegation guidance now explicitly excludes parent history, full policy transcripts, whole files, and full skill bodies. This is a source-of-truth guard for future sessions; it cannot reduce tokens already spent in the current rollout. Savings remain unmeasured until a fresh comparable session is run.
