# B1 Chat/Batch Parity Oracle — Acceptance

**Verdict: PASS** (accepted for commit).
**Authorization:** `auth-aqos-foundation-b1-parity-20260723` (hash `25573a20…`),
owner-activated 2026-07-23 (report-only slice, on owner's explicit standing
authorization; drift-verified). **Single-use authorization now CONSUMED** by this
2-file candidate.

## Reviewer / independence
- Implementer: `claude-subagent-b1-parity-oracle-implementer` (Sonnet). It completed
  the deliverable (both files) and hit the Anthropic session limit only on its final
  PULSE line — the code is complete.
- Acceptance: fable-5 (orchestrator), rigorous behavior-verification. Independent of
  the implementation (Sonnet wrote it); NOT fully independent of the design (fable-5
  authored the packet/authorization). Report-only lowest-risk slice + the design was
  independently reviewed (Opus). **Queued for a confirmatory audit** (Codex/fresh
  flagship) on return — AGENT-CATCHUP-QUEUE.

## Verified (behavior, not just green)
- `PASS: local-inference-chat-batch-parity`, exit 0. Offline (no live service).
- Result: **4 byte-equivalent-on-projection**, **8 typed-divergence (evidence, not
  failure)**. The 8 are exactly the design-review-predicted known divergences
  (`budgets.max_tokens` 1024-vs-budget; `repeat_penalty`/`repeat_last_n` set-vs-unset)
  — recorded as L3/L4-scoping evidence, NOT slice failures (anti-gaming honest).
- No MUST-FAIL divergence surfaced (enable_thinking/temperature/model-id/role/
  profile/authority/sampling are byte-equivalent on the projection) — parity holds
  on the security-critical surface.
- **Harness-drive purity guarded:** `AQChat.__init__` is poisoned (`_forbidden_init`
  raises "PARITY ORACLE VIOLATION" if invoked); builders driven via a
  `types.SimpleNamespace` stub carrying only `temperature`/`local_tools_enabled`.
  Batch adapter = the REAL `llm_config.build_llama_payload` (not the dispatch.py
  fallback clone).
- **Read-only refs byte-unchanged:** `git diff HEAD -- scripts/ai/aq-chat
  ai-stack/mcp-servers/shared/llm_config.py scripts/ai/lib/dispatch.py` is EMPTY.
- **Ceiling:** exactly the 2 new files; nothing under a frozen manifest; py_compile
  clean; tier0 --staged-isolated.

## Meaning (B1 exit)
The offline chat/batch parity oracle exists and passes — the B1 "chat/batch parity
in shadow" evidence instrument. The 8 typed divergences precisely scope the L3/L4
live-adoption work (chat and batch don't yet share max_tokens resolution or the
repeat-penalty defaults). Per the design review §6.3, this satisfies the B1 shadow-
exit item but is NOT license for L4 duplicated-logic removal (that gates on a later
live-shadow parity pass).
