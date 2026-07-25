# Agent catch-up queue (model/agent-agnostic)

**Purpose:** durable record of agent inputs that were SOLICITED but MISSED because an agent was
unavailable, so a returning agent can fold in its input (confirmatory audit / additional findings /
post-commit follow-up) on the exact subject it missed — without ever blocking the pipeline while it
was down. Owner directive 2026-07-22 ("model/agent-agnostic factory + catch-up cache/queue").
Generalizes the former `CODEX-REVIEW-QUEUE.md` to ALL agents. SSOT principle:
`memory/feedback-agent-agnostic-roles-and-catchup.md`.

## How it works

- **Roles are agnostic.** Every role instance (orchestrator/architect/implementer/reviewer/binding-
  acceptance) is routed at dispatch time to whichever agent is available + eligible + independent +
  cheapest — never hardcoded to one agent. If the first-choice lane is down, the orchestrator routes
  to the next eligible lane, proceeds, and files a catch-up entry here for the down lane.
- **Catch-up, not block.** A slice does not wait for a specific agent. When an eligible agent is
  unavailable, its intended contribution is recorded here (subject + exact hashes/commit + role it
  would have filled). On return, that agent processes its catch-up entries: confirmatory audit of an
  already-committed slice, or additional findings that become a follow-up slice if they warrant it.
- **A commit made while an agent was down is not permanently unreviewed by it** — it's queued for that
  agent's catch-up (advisory/confirmatory unless it surfaces a real defect → follow-up).

## Entry format

| # | Slice / subject | Exact subject (hashes / commit) | Role the missed agent would fill | Missed agent(s) + why down | Status |
|---|---|---|---|---|---|

## Live entries

| # | Slice / subject | Exact subject | Missed role | Missed agent(s) | Status |
|---|-----------------|---------------|-------------|-----------------|--------|
| C1 | B3-C1 canon compiler (committed d1c8e55b/90a55e06) | commit `90a55e06`+`d1c8e55b` | confirmatory acceptance | Antigravity (Gemini) — design-only reviewed, no code confirm; local Qwen — slow | open — fold Gemini/local confirmatory audit on availability |
| C2 | L2B-B payload normalization (committed 99364942) + AM4 reconciliation (pending) | commit `99364942`; AM4 cand `e42fb548`… | confirmatory acceptance | Antigravity, local Qwen | open |
| C3 | VF-7 evidence collector (committed e5578e5c) | commit `e5578e5c` | confirmatory acceptance | Antigravity, local Qwen | open |

## Notes for a returning agent

- Verify each subject's on-disk/commit hashes against this queue before reviewing; a mismatch means
  the tree advanced — treat as a fresh confirmatory pass on the current bytes, not a stale replay.
- A confirmatory PASS closes the entry. A defect found post-commit opens a bounded follow-up slice
  (do NOT silently rewrite committed history).
- Superseded lane-specific note: the earlier `CODEX-REVIEW-QUEUE.md` is retained as history; Codex is
  now one eligible lane among several, not the sole acceptance authority.

## local-embed-context program (queued 2026-07-23 for confirmatory audit)
Committed while Codex quota-down; independent acceptance via Antigravity (2b design lane) + fresh Opus. On Codex return, confirmatory-audit these subjects against current bytes:
- `6b018b00` Slice 1 aq-local-review (chunked review tool) + `457fd467` DIRECT_MAX_TOKENS/timeout fix
- `44530e73` Slice 2a context_cache.py (embed cache library)
- `0846b83f` Slice 2b — agent_executor prune-path hook + local-delegation-reliability-golden.json re-pin (agent_executor sha ad401788, source_manifest df4d94d9). **Priority:** this re-pinned the reliability track's OWN golden manifest — the reliability-track authority should confirm the re-pin is honest (defect characterizations D3/D4/D6/D7 intact, matches_frozen True) and net-clean (HEAD baseline fails identical test_02/15/16 = pre-existing task_registry drift).
Advisory unless a real defect surfaces → then a bounded follow-up, never rewrite history.

### [QUEUED] codex — Foundation C design packet confirmatory audit
- Subject: `.agents/plans/aqos-foundation-c/DESIGN-PACKET.md` (Foundation C security spine; absorbs F3 4/4 consensus + keystone zero_trust; Q3-ratified direction).
- Why queued: codex in quota-cooldown at design time; independent review ran via fresh Opus. codex = deepest F3 contributor (epoch revocation, bwrap⇄lease, allowed_output_paths) → on return, confirm the packet is faithful to its F3 additions + sanity-check C0→C6 decomposition.
- Status: advisory on return (real defect → bounded follow-up, never rewrite). Solicited 2026-07-24.

### [QUEUED] codex — Foundation C **C0** confirmatory audit
- Subject: commit `0319488b` — `config/schemas/capability-lease.schema.json`, `scripts/ai/lib/capability_lease.py`, `scripts/ai/aq-lease`, tests+fixtures (report-only CapabilityLease primitive).
- Why queued: codex in cooldown at build time; independent crypto review ran via fresh Opus (caught + fixed a non-numeric-constraint widen fail-open in attenuate()). codex = deepest F3 crypto/epoch contributor → confirm HMAC canonicalization + attenuation monotonicity + verify() fail-closed ordering.
- Status: advisory on return (real defect → bounded follow-up, never rewrite). Solicited 2026-07-24.

### [QUEUED] codex — Foundation C **C1** confirmatory audit
- Subject: commit `f121c713` — capability_lease_issuance.py + aq-capability-shadow + shadow-record schema + tests (shadow admission→issuance, log-only, decoupled).
- Why queued: codex in cooldown; independent Opus review PASSED (0 blocking; 2 SHOULD-FIX folded). Confirm the additive/non-enforcing decoupling + admission→lease policy mapping + no false would-issue on blocked/needs-review.
- Status: advisory on return. Solicited 2026-07-24.

### [QUEUED] flagship reviewer — Foundation C **C2** independent DESIGN review (blocking for activation)
- Subject: `.agents/plans/aqos-foundation-c/C2-DESIGN-AND-AUTHORIZATION.md` (first enforcement slice; flag-gated default-off tool-lease gate at switchboard _resolve_tool_lease).
- Why queued: first reviewer (Claude flagship/Opus) hit the Anthropic session limit 2026-07-25 (resets 11:40am); codex in cooldown. Rule 18 substitution recorded — route to next flagship reviewer on return (fresh Opus post-reset OR codex). Antigravity NOT used (untrusted-advisory; security-enforcement design).
- Focus: fail-open audit, off-is-inert parity, hash-bound governance, ceiling, F3 faithfulness (S1/S3/S4 + property tests).
- Status: **BLOCKING** — C2 cannot be frozen/owner-activated until this PASSES. Solicited 2026-07-25.
