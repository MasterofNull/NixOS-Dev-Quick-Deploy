# local[Qwen] — round contribution retry

_Latest dispatch: `local-20260709-002835-7qsrf2`._

Status: partial substantive output, truncated by direct-lane token heuristic.

## Verdict

**AGREE.** `background_task.v1` is the correct first slice. The current black-box delegation model creates operational ambiguity that prevents debugging and automated recovery. Without a standardized, queryable task state machine, operators cannot distinguish between a stalled inference process, a network timeout, or a logic error in the agent loop. This slice provides the foundational telemetry required for all subsequent UX improvements across dashboard, CLI, and replay.

## Evidence Read

1. **Local inference wedge:** local llama became unresponsive and required manual restart while registry state still suggested work was running.
2. **False success signals:** an earlier Qwen lane returned only `COMPLETED: The previous output was incomplete`, which was collected as a valid contribution even though it was not substantively useful.
3. **Tool-call hallucination:** Qwen agent-mode retry `local-20260709-001430-f3llz1` returned textual `Thought:` / `Tool:` content instead of executing the tool or producing the proposal, and the runner marked it successful.
4. **Stale registry entries:** three Codex rows appeared to be hanging in switchboard, but their PIDs were gone and registry reconciliation marked them stale.
5. **Antigravity constraint:** Antigravity remains a no-key IDE/OAuth watched-inbox lane, so task state must be inferred from inbox/output file events rather than keyed provider RPC.

## Qwen-Specific Finding

The local model agrees with the first-slice consensus, but the retry itself exposed two local-lane quality gaps:

- agent-mode false success classification accepts textual tool-call output as success;
- direct-mode token selection can be accidentally capped by prompt wording even when the operator intends a full report.

These should be treated as `background_task.v1` fixtures, not as reasons to skip Qwen. The fix is better liveness/progress/result-quality telemetry plus explicit output-budget control, not arbitrary time/tool-call caps.

## Local Contribution To Consensus

Local/Qwen supports keeping `background_task.v1` as the first implementation slice. Its added emphasis is that "done" must require a usable artifact or explicit terminal reason, not just a process exit or a regex-matched completion string.

VERDICT: PASS — Qwen agrees with `background_task.v1` first, with local false-success and token-heuristic failures included as validation fixtures.
