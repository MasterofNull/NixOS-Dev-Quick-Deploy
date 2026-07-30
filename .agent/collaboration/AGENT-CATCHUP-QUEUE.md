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
| C4 | Track S defensive-security architecture + S0-A intake truth | PRD `68e3f33c…`; plan `bb75f4d2…`; S0-A design `dd5fb5ce…`; prepared auth `04cb48b41…` | advisory architecture/security/SRE/privacy/license review | Claude — Fable, Sonnet 4.6, and Opus 4.8 headless attempts all exited without evidence; likely weekly/session eligibility limit | open — durable/manual-dispatch-required; dispatch once when Claude eligibility reopens; no repeated polling storm |
| C5 | Agent/model configuration parity design + Codex C1A | PRD/plan and C1A exact hashes to be frozen after current review | advisory architecture/runtime review and confirmatory C1A audit | Claude — weekly session limit reached; owner reports reset at 02:00 UTC 2026-07-30 | open — dispatch once after reset; findings create bounded revision, never stale acceptance |

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

### [QUEUED] cheap implementer — classify the ~22 review-needed plans for supersession (owner-approved delegation)
- Subject: the REVIEW-NEEDED list in `.agents/plans/pm-tracker-standard/SUPERSESSION-MAP.md` (agent-connection-reliability, agent-ops-traceability-r0m, antigravity-lane-restoration, antigravity-routing-honesty-accept, c05-tiered-policy-architecture, capability-intake-security, delegate-codex-quota-precheck, dispatch-integration-review, generic-flake-baseline, lean-ctx-workspace-identity, local-delegation-reliability-r0, multi-agent-edge-harness, qa-provider-probe-reliability, reentry-intent, rsi-readiness, security-validation-reliability, stream-auth-rereview, usability-parity, usability-parity-v2, b1-parity-design-review, phase-173, tiered-agent-memory).
- Task: for EACH, read its status doc + `git log -1 --format=%cs -- <dir>` (via subprocess — shell truncates git log) → propose lifecycle ∈ {complete (shipped/landed), superseded (absorbed → name the superseding plan), active (still open)} with one-line evidence. Output a table; do NOT write markers. Owner confirms verdicts, THEN orchestrator applies `.plan-lifecycle.json` markers + regenerates the dashboard.
- Why queued: Claude subagent lane session-limited (reset 3:30pm 2026-07-25); local can't multi-read reliably; codex cooldown. Owner approved delegation 2026-07-25.
- Status: advisory analysis (no markers applied without owner confirm). Solicited 2026-07-25.

### [QUEUED] Claude — Track S defensive-security + S0-A confirmatory review
- Subject: `.agent/PROJECT-AQOS-DEFENSIVE-SECURITY-FACTORY-PRD.md`
  (`68e3f33cf187b7b7cf797be788c24cd837010c50730842f630770598fa4fa491`),
  `.agents/plans/aqos-defensive-security/PROGRAM-PLAN.md`
  (`bb75f4d2a36f1bb6d397ee734668908091d5e4dbba07622d0415188623f01325`),
  S0-A design (`dd5fb5ce69ffc75ce9bd59f3935d366439e6326334a1b06c6ab5ee2b1ba1d813`),
  and prepared authorization
  (`04cb48b411aacdf2572805d46a2bcd3b47729c108fa3677749c2eaceccd781ed`).
- Why queued: monitored Fable, Sonnet 4.6, and Opus 4.8 review attempts all
  registered and then exited without output, consistent with a Claude
  weekly/session eligibility limit rather than a model-specific defect. Codex
  independent review passed; Antigravity and local inputs are advisory and
  non-gating.
- Focus on return: scope and egress escape, no-hack-back canaries, Piyaz
  A2A/tracker/vector-RAG-DAG pattern extraction without authority duplication,
  Sn1per/RAPTOR quarantine, evidence custody, BOD-inspired ordering,
  disclosure/bounty gates, S0-A closed-schema compatibility, and Service
  Coverage sequencing.
- Status: advisory catch-up; durable/manual-dispatch-required until the broker
  owns executable catch-up retries. A real defect opens a bounded follow-up and new
  subject hash; a PASS closes C4. Queue once on eligibility reopening—do not
  replay the three failed task IDs. Solicited 2026-07-27.

### [IN-PROGRESS 2026-07-29] Claude picked up Track S S0-A confirmatory review
- Returning Claude lane (fable-5) folded the codex-prepared catch-up: subjects drift-verified current (PRD 68e3f33c, PROGRAM-PLAN bb75f4d2 unchanged). Dispatched independent Opus confirmatory review (a1e9a43d) on all 9 codex axes → writes S0-A-CLAUDE-CONFIRMATORY-REVIEW.md. CONFIRM-PASS closes it; a real defect opens a bounded follow-up + new hash.

### [CLOSED 2026-07-29] Track S S0-A confirmatory — CONFIRM-PASS
- Claude (Opus, fable-5) confirmatory catch-up = CONFIRM-PASS; codex's PASS holds. All 9 axes verified against source; both codex blocking revisions resolved+tested fail-closed; authorization single-use/owner-activated/not-self-activating. NO defect, no bounded follow-up. Receipts: S0-A-ACTIVATION-RECEIPTS.md. Advisory: antigravity review untrusted/loose (does not count). Catch-up item CLOSED.

## codex outage 2026-07-29 → 2026-08-04 (usage limit) — C3b R1 substitution
Codex hit its usage limit mid-C3b-R1-authoring (retry Aug 4th 22:09). Per Rule 18 (route to next
eligible + record, never block): C3b R1 design authoring re-routed to Opus (deepest current context
from the R0 review); binding independent review re-routed to a fresh Claude flagship subagent
(codex-substitution). **Catch-up on codex return (≥Aug 4):** codex to run a confirmatory audit of
C3B-R1-DESIGN-AND-AUTHORIZATION.md (subject hash recorded at freeze) + the R0 review it already
PASSED — advisory unless it surfaces a real defect (then a bounded R1 follow-up, never rewrite).
Codex remains the deepest F3/C3b contributor; its return audit is expected, not optional.

- **C3b R1 (antigravity-reviewed PASS 2026-07-29) → codex confirmatory on return.** `C3B-R1-DESIGN-AND-AUTHORIZATION.md` status R1_REVIEWED_PASS via antigravity/gemini (codex-substitution) + Opus verification + 3 folded findings. Codex (deepest C3b contributor) to confirmatory-audit R1 (grant schema, Ed25519 SF-1 decision, conservative classification, golden vectors) on its ≥Aug-4 return — advisory unless a real defect → bounded R1 follow-up.

- **C3b R2 (antigravity-reviewed PASS 2026-07-29) → codex confirmatory on return.** `C3B-R2-DESIGN-AND-AUTHORIZATION.md` status R2_REVIEWED_PASS (self-contained clone primitive: bare-mirror source, transactional clone at verified OID, typed quarantine/reconcile, fd-relative rebase). Codex to confirmatory-audit R2 isolation guarantees on ≥Aug-4 return.

- **C3b R3 (antigravity-reviewed PASS 2026-07-29) → codex confirmatory + OWNER ACTIVATION gate.** `C3B-R3-DESIGN-AND-AUTHORIZATION.md` status R3_DESIGN_REVIEWED_PASS (dedicated bwrap cell runner, grant-verified, cgroup epoch-fence, out-of-cell validator). ENFORCEMENT-TIER: build needs single-use owner activation. Codex to confirmatory-audit R3 confinement/kill/fence on ≥Aug-4 return.

- **C3b R4 + R5 (antigravity-reviewed PASS 2026-07-30) → codex confirmatory on return.** R4 (perf gate, non-enforcement, R4_REVIEWED_PASS) + R5 (switchboard adapter+grant signing, ENFORCEMENT-TIER, R5_DESIGN_REVIEWED_PASS). Both light-model PASS — codex confirmatory REQUIRED for R5 before activation (production Ed25519 private-key signing + SOPS provisioning is high-stakes; antigravity PASS alone is insufficient assurance). Codex to deep-audit R5 grant-signing/key path + R4 protocol on >=Aug-4 return.
