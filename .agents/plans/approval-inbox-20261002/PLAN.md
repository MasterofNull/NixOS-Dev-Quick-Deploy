# Approval inbox SOP — plan (owner-approved 2026-10-02)

Supersedes the 2026-09-30 "approvals CLI-first" rule. Owner direction: easiest + most durable; approve in chat; numbered list of found-but-deferred issues.

## SOP
1. One inbox, one record: `aq-approve` lists/acts over the canonical PRSI/RSI queue + attention queue. State stays in those files (fail-closed queue loader, prsi-actions.jsonl audit).
2. Two sections, one numbering: **Needs approval** (PRSI/RSI rows: risk high, status rsi_pending|rsi_failed, no approval.verifier_by; attention alerts pending with an executor) and **Deferred** (open RSI ledger incidents not awaiting approval; other pending attention alerts). Agents add deferred items through the existing `rsi_lifecycle failure` intake — no new intake path.
3. Seen without asking: `aq-resume` banner shows inbox counts + top items; agents print the list at turn end when they added items; `aq-approve` anytime.
4. Decide in chat: owner says "approve 1 3" / "dismiss 2"; the agent runs `aq-approve approve 1 3 --tag <t> --door chat`; the Claude Code permission prompt (ask-always rule) is the owner's confirmation. Codex: same via its approval prompt. Local: propose only.
5. Durability: each listing prints a snapshot tag (hash of ordered item keys+status); numbered actions require the tag and refuse on mismatch (re-list). Every decision logged with door + timestamp. Dismiss hides an item (inbox-side record), never marks it resolved (anti-gaming).
6. `/approve` page (ACP) wiring: DEFERRED 2026-10-02 — same backend later.

## Slices
- S1 `aq-approve` inbox: list/--json/--summary, approve/deny/dismiss by number with tag, door + audit; legacy `aq-approve attn-xxx` unchanged. `aq-resume` banner uses `--summary`. Regression test.
- S2 ask-always permission rule for aq-approve (Claude settings) + SOP text in CLAUDE.md, .agent/CODEX.md, .agent/LOCAL-AGENT.md, .agent/GEMINI.md, .agent/WORKFLOW-CANON.md (Rule 16 parity).
- S3 live validation: owner re-approves the two sign-offs wiped in the 2026-10-02 queue incident through the chat door.

## Acceptance
Inbox lists both sections with stable numbering + tag; stale tag refused; approve on a PRSI row sets verifier_by=owner via prsi-orchestrator; deny/dismiss recorded; aq-resume shows counts; agents cannot run aq-approve without an owner prompt; real chat-door approval succeeds.
