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

### Current integration state — 2026-09-17

Codex remains the sole shared-checkout integrator. Claude reviews/plans without
switching its HEAD or staging competing source. The older CS-1F2 revision report
is superseded by accepted corrective `0d835c13`, reviewed independently by Claude
on exact subject `6000afac6971d3d95828a3965ae56e4b67550ba0506a951b7fd536853447b67f`.
Elapsed-time display `c5b829a8` and generated-artifact hygiene `5e3c7b7d` are also
accepted. CS3-F1 source is independently accepted and synchronized in `f9ab7e42`
on exact subject `3332984f446889f3fd0aa52bd4e68e072f5ab1be58c42440f9bac3a2f21e24f1`.
The guarded production commit passed Tier-0 53/0 and normal push 22/22; live lease
status was held, foreign hook refused, then idle after release. This is cooperative
explicit-path transaction protection, not interception of every ordinary git add or
a same-user security boundary. CS-4 deployed visibility/parallel-dispatch proof is
still pending. Failed draft `1a9a0567` is preserved separately, activation-blocked.

### [QUEUED] Claude — CS3-F1 confirmatory audit and producer timing catch-up

- Exact accepted subject: commit `f9ab7e429874eb32f91c04889aa7189daa213787`,
  reviewed subject `3332984f446889f3fd0aa52bd4e68e072f5ab1be58c42440f9bac3a2f21e24f1`.
- Missed role: independent code review; eligible cold flagship substitution
  `/root/cs3_final_review` delivered actual PASS. Claude's confirmed quota reset is
  13:30 Pacific / 20:30 UTC; no Claude review is credited for this subject.
- On return: confirm CS3-F1 staged-deletion/rename hash parity and production lease
  behavior; read the separately authorized local producer timing execution packet in
  `/tmp/aq-local-producer-timing-20260917`. Its source is still under implementation,
  not accepted. Route real findings into bounded follow-ups; do not re-open accepted
  history or block delivery solely on Claude's availability. No staging/shared edits.

The obsolete installer-v1 task is preserved at
`.agent/archive/antigravity-inbox-20260910/aqos-installer-prd-review.md`, SHA-256
`84f480573f1e003cde5cf706824916c8019ee858711f87a195de19508b79fb90`.
The completed ECC task is preserved at
`.agent/archive/antigravity-inbox-20260917/.claimed-ecc-pinned-parity-report-20260916-d14854d8fcd8`,
SHA-256 `d14854d8fcd8027f4566076bb5a7beac7cb421d3b0f3c41b8548b57baee792e1`.
Historical entries below remain evidence of their original state, not instructions
to restore or redispatch completed inbox tasks. Completion receipts remain immutable.

| # | Slice / subject | Exact subject | Missed role | Missed agent(s) | Status |
|---|-----------------|---------------|-------------|-----------------|--------|
| C1 | B3-C1 canon compiler (committed d1c8e55b/90a55e06) | commit `90a55e06`+`d1c8e55b` | confirmatory acceptance | Antigravity (Gemini) — design-only reviewed, no code confirm; local Qwen — slow | open — fold Gemini/local confirmatory audit on availability |
| C2 | L2B-B payload normalization (committed 99364942) + AM4 reconciliation (pending) | commit `99364942`; AM4 cand `e42fb548`… | confirmatory acceptance | Antigravity, local Qwen | open |
| C3 | VF-7 evidence collector (committed e5578e5c) | commit `e5578e5c` | confirmatory acceptance | Antigravity, local Qwen | open |
| C4 | Track S defensive-security architecture + S0-A intake truth | PRD `68e3f33c…`; plan `bb75f4d2…`; S0-A design `dd5fb5ce…`; prepared auth `04cb48b41…` | advisory architecture/security/SRE/privacy/license review | Claude — Fable, Sonnet 4.6, and Opus 4.8 headless attempts all exited without evidence; likely weekly/session eligibility limit | open — durable/manual-dispatch-required; dispatch once when Claude eligibility reopens; no repeated polling storm |
| C5 | Agent/model configuration parity design + Codex C1A | PRD/plan and C1A exact hashes to be frozen after current review | advisory architecture/runtime review and confirmatory C1A audit | Claude — weekly session limit reached; owner reports reset at 02:00 UTC 2026-07-30 | open — dispatch once after reset; findings create bounded revision, never stale acceptance |
| C6 | TEG C1 R2 Slice-One pre-build advisory (committed `3a544936`) | commit `3a544936`; advisory `.agents/plans/aqos-foundation-c/ANTIGRAVITY-TEG-C1-SLICEONE-ADVISORY-20260815.md` (verdict PASS) | confirmatory audit of the frozen R2 CORE spec + Antigravity's watch-items before/at build | Codex (implementer/binding) — quota-down until ~Aug 21 | open — Antigravity advisory PASS committed by orchestrator; on return, confirm the R2 CORE spec + fold watch-items into the build |
| C7 | herdr `review_repair_integration_coverage` ESCALATION adjudication | HERDR-ESCALATION-ADJUDICATION-20260816.md (verdict DEFER+ACCEPT); loop_state.py:181-182 + test-aq-loop-review-repair-guard.py:52-54 | orchestrator adjudication + binding acceptance of the H2A slice | Codex (usual herdr owner) — quota-down until ~Aug 21 | ADJUDICATED (defer+accept) — 3-way convergence local(`kpz157`)+Antigravity+orchestrator, both Antigravity code claims VERIFIED against source. On return Codex MODIFIES/confirms against current bytes; advisory unless a real defect → bounded follow-up |
| C8 | ACP-P0 approval-request record + executor (committed `dee72d38`) | commit `dee72d38`; scripts/ai/lib/approval_request.py + approval_executor.py + test-approval-request.py; golden hash `ff83ff79…b6aa8` | binding confirmatory review of the security primitive | Codex — quota-down until ~Aug 21 | REVISED (bounded fix `117aeb66`) — local(`qopywx`) + Antigravity(P1 review) confirmatory done; Antigravity found CRITICAL cross-request-signature-reuse → FIXED (request_id in CANONICAL_FIELDS, golden re-pinned, regression test). On return Codex confirms the fix + canonicalization against current bytes |
| C10 | ACP-P2 approval-surface BUILD + ACP-P3 runbook-engine BUILD | BUILT: P2 `4e3178b8` (surface 22/22), P3 `887e103a` (engine 16/16); records ACP-P2/P3-BUILD-20260817 | binding confirmatory review of both builds | Codex — quota until ~Aug 21 | BUILT + orchestrator-reviewed PASS (sonnet lane after reset) — combined tree P0 8/8 + P1 20/20 + P2 22/22 + P3 16/16 + tier0 26/0; default-OFF pending deployment activation. On return Codex confirms surface privacy/WYSIWYS + engine idempotency/scope-bound vs current bytes; advisory unless real defect → bounded follow-up |
| C9 | ACP-P1 WebAuthn signing service DESIGN (committed `11a7e478`) | commit `11a7e478`; .agents/plans/approval-control-plane/ACP-P1-DESIGN-20260816.md | binding design review before build | Codex — quota-down until ~Aug 21 | REVIEWED (local `6so7v7` + Antigravity, both folded — Antigravity verdict CONCERNS drove the P0 CRITICAL fix + 4 hardenings, commit `117aeb66`). Codex binding on return before build |

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

- **Repo cleanup / integration checkpoint 2026-07-30 (owner-authorized).** The 140-file uncommitted pile-up (concurrent-cycle stage-don't-commit work) was landed in 3 gate-clean commits: 734333d0 (C4 design + gitignore + tracker-WIP archive), aa0d1a41 (plan/review evidence docs), 81e43a21 (in-process file edits incl. codex C0.6-T agent-ops slice). **CODEX: your C0.6-T edits (agent_ops_projection.py, phase0.py, aistack.py, dashboard.js, aq-tui-dashboard, test-agent-ops-*, schema) were integrated gate-clean (full focused-CI passed) on owner authorization — continue from 81e43a21 on return; nothing rewritten.** Tracker-refresh slice NOT committed — preserved at .agent/archive/20260730-tracker-wip/ (0.10.40 blocker; owner/originator finishes with the test re-pin).

- **C5 + C6 (antigravity PASS 2026-07-30) → codex confirmatory.** C5 (spans-as-truth, NON-enforcement, C5_DESIGN_REVIEWED_PASS) + C6 (epoch control + scheduler seam, ENFORCEMENT-TIER, C6_DESIGN_REVIEWED_PASS). Foundation C design ladder C0–C6 now COMPLETE + reviewed. Light-model passes — codex confirmatory required for C6 scheduler-seam (+ R5, C4) before activation. Codex to deep-audit C6 scheduler-lease-gate + epoch-bump atomicity + C5 span secret-freedom on return.

- **C2 tool-lease enforcement ACTIVATED (owner-authorized 2026-07-30) → codex audit on return.** CAPABILITY_LEASE_ENFORCEMENT=1 added to ai-switchboard Environment (switchboard.nix); LIVE after nixos-rebuild switch. C2 has codex depth review (043758 REVISE → 163121 PASS); 83/83 flag-ON pre-flight. Codex: audit the LIVE activation on return (first-party lease admission of built-ins, deny-closed behavior, no tool-calling regression); propose adjustments (advisory unless real defect). Record: C2-ENFORCEMENT-ACTIVATION-20260730.md. Other enforcement slices remain OFF/unbuilt pending codex.

- **C2 enforcement VALIDATED LIVE 2026-07-30.** Flag ON + aq-lease-signing-key provisioned (SOPS /run/secrets); resolve_key is_dev=False; first-party leases admit run_command/write_file/read_file/store_memory/delegate_to_remote; deny-closed on unknown. C2 is the FIRST fully-activated enforcement slice (integrated+ON+real-world-validated). Codex: audit the live activation on return.

- **C3b R5 BUILT (owner-activated ffd469a6, 2026-07-31) → codex verifies on return.** Switchboard adapter + Ed25519 grant signing, flag CAPABILITY_CELL_ADAPTER default-OFF (6d17f9e6). Ed25519 keypair provisioned (private SOPS /run/secrets/aq-grant-signing-key, public tracked config/grant-signing-public-key; matched pair self-verified). Opus caught+fixed a raw-vs-hex key-format defect the tests missed. 49/49; C2/runner suites unchanged. Codex: audit the production Ed25519 signer + key path + adapter deny-closed behavior. NOT live — R6 flip (CAPABILITY_CELL_ADAPTER=1 + runner enable + rebuild) is a further owner act.

### 2026-07-31 — R5-shadow rollback + runner-deployment-hardening (for codex Aug-4)
Shadow activation of the C3b runner surfaced 5 deployment bugs (runner never deploy-exercised).
4 fixed (commits b41c81e3, d950f0fe + R5 build key-hex). 5th is a blocker: runner self-binds its
UDS instead of consuming socket-activation, destroying SocketGroup=clients. Shadow ROLLED BACK to
safe C2(enforcing)+C5(observing); adapter+runner code intact but DORMANT.
- VERIFY: the 4 unit fixes are correct + minimal; the rollback is byte-clean (only flags flipped).
- VERIFY the deferral doc `.agents/plans/aqos-foundation-c/RUNNER-DEPLOYMENT-HARDENING.md` scopes
  the real fix correctly (socket-activation adoption, not a group hack).
- LATE-FINDING WELCOME: any 6th deploy issue behind #5 (cgroup delegation / bwrap-under-NNP /
  validator) — advisory unless a real defect, then a bounded follow-up.

### 2026-07-31 — runner-deployment-hardening FREEZE: codex depth-review is a REQUIRED build gate
Design frozen (subject sha256 68e3b120…, .agents/plans/aqos-foundation-c/RUNNER-DEPLOYMENT-HARDENING.md
+ FREEZE record). Local gave PASS but truncated before the security-regression + open-question depth.
On return, codex MUST depth-review before any owner activation/build:
- Confirm fd-3 adoption cannot bypass SO_PEERCRED or the Ed25519 grant verify (orchestrator closed
  this by design-invariant; codex is the binding confirm).
- Confirm the ceiling is minimal (serve_forever seam only) and the deploy-exercise gate is real.
- Rule on Q-H-1 (strict fd 3) and Q-H-2 (keep guarded fallback vs test-only shim).
This is a HARD gate (enforcement-tier security slice), not advisory. Only after codex PASS does the
owner's single-use activation apply.

### 2026-08-01 — codex returned early; runner-hardening REQUEST_REVISION (bug #6)
Codex depth-reviewed the frozen runner-hardening slice: fd-3 fix correct + secure, 3 committed fixes
sound, BUT found bug #6 — the Nix unit sets no AQ_EXECUTION_CELL_RUNNER_CLIENT_UID/GID so
peer_authorized() rejects every peer (masked behind bug #5). Design revised to rev2 (subject
147324b087d2d37a), ceiling expanded to 4 files (runner.py + execution-cell-runner.nix client-UID +
env-contract.yaml + test). NEXT: codex re-review of rev2 → re-freeze → owner activation.
Still queued for codex (binding): C4 fc7534de, C6 89b2b65d, C3a-2 3ff34439 (antigravity advisory-PASSed all 3).

### 2026-08-03 — R7 provisioning design queued for codex binding review
R7-PROVISIONING-DESIGN-20260803.md (base HEAD a439527f) is DESIGN/PREPARED_ONLY and needs codex binding
depth-review before freeze -> owner activation -> build. R7 provisions the deferred R3 pieces (bare repo
mirror + trusted_repo_mirrors wiring + durable reservation store) so the confinement runner reaches a
typed GREEN cell round-trip; it satisfies C6's retained runner-live-cell gate.
Context codex should confirm on return:
- R6 milestone: runner-hardening deployed+validated live; deploy bugs #2/#5/#6/#7/#8 fixed (all committed,
  small-batched: 0cf1192e..a439527f). The shadow proved plumbing+security end-to-end; adapter now OFF pending R7.
- Also awaiting codex: C4/C6/C3a-2 build-activations (PASS_DESIGN/PREPARED_ONLY; C6 gated behind R7).
- Verify: R7 ceiling is minimal (runner nix + build_config_from_env + a durable store), switchboard anchor
  untouched, mirror-freshness contract sound (stale -> typed clone-failed deny, never a wrong result).

## [2026-08-06] Codex confirmatory: C6-P0 rev3 + C2 scheduler-context issuer designs
Two PREPARED_ONLY Foundation-C prerequisite designs authored by Claude Opus (unblock C6 -> C4).
A fresh Claude flagship is doing the binding review now; local Qwen advisory in parallel. Codex on
return: independent confirmatory audit (advisory unless it surfaces a real defect -> bounded follow-up).
Subjects (sha256 prefix):
- C6-P0-TRUST-ANCHORS-REV3-20260806.md  54d6443907c39a430add  (NARROWED per rev2 reviewer's option 1:
  pure declarative anchors — owner allowlist + 2 schemas + offline test; removes issuer/transport).
- C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md  5785da300596b344653d  (opens Q-C6-1: dedicated
  default-OFF issuer service, SOPS signer key, Nix-resolved peer, switchboard.nix untouched).
Confirm: does P0 rev3 honestly close the rev2 REQUEST_REVISION by narrowing (not hiding the prereq)?
Does the issuer slice fully close finding 1 (signer provisioning/rotation/fail-closed) + finding 2
(transport peer identity)? Any missed trust-boundary defect (context forgery, admission spoof, key
leak, replay/epoch coherence)?

### Update 2026-08-06: binding review DONE (fresh flagship) — C2 issuer now rev2
Flagship binding verdict: C6-P0 rev3 PASS (freeze-only); C2 issuer rev1 REQUEST_REVISION — CONFIRMED
HIGH defect (switchboard runs as human uid -> SO_PEERCRED not caller authority; issuer trusted a
caller-asserted ALLOW). Rev2 (committed d8702e4c) moves authority to the signed C2 lease
(issuer verifies the presented Ed25519 lease + re-derives admission; peer-uid = defense-in-depth).
Codex on return: confirm rev2 closes it (subject = C2-SCHEDULER-CONTEXT-ISSUER-DESIGN rev2), and
independently check the lease-verification seam (can a caller replay a valid lease across tasks?
does the issuer bind the context to the lease's single-use/epoch?). Record in
C6-P0-AND-C2-ISSUER-BINDING-REVIEW-20260806.md.

### [2026-08-06] Codex confirmatory: Asymmetric Lease Authority design (ALA)
New foundational prerequisite (owner-chosen) fixing the rev2 FAIL — Ed25519 confined lease signer.
Subject: ASYMMETRIC-LEASE-AUTHORITY-DESIGN-20260806.md. Fresh flagship binding review running; local
advisory in parallel. Codex on return: press the SIGNING-ORACLE risk (does the confined authority
sign whatever the owner-uid gate presents?) and the SCHEME-DOWNGRADE attack (attacker sets
sig_scheme=hmac-sha256 + forges with the dev key -> bypasses Ed25519). Confirm flag-OFF byte-parity.

## [2026-08-07T21:46:30-07:00] C2-SCI confirmatory reviews (lane session-limited to 7:50pm PT / Codex Aug 8)
- Independent code review QUEUED for: `0bd67174` (B2.5 durable ledger), `ad5d95dd` (B3 gate/dispatch), `2c36e7d3` (B4 coverage). All orchestrator-verified + default-OFF; advisory unless a real defect surfaces (then bounded follow-up, never rewrite history). B1/B2 already independent-review PASS.

## [2026-08-08] Codex lane RETURNED — batched confirmatory audit DISPATCHED
Task: codex-20260808-112547-06dnqgxxxxxx (edit-mode, read-only; writes only the verdict doc).
Covers the full queued set: ALA (signing-oracle + scheme-downgrade + OBLIG-1), C2-SCI B2.5/B3/B4
(0bd67174/ad5d95dd/2c36e7d3 — lease-replay, durable-ledger race, flag-OFF parity), C6-P0 rev3 +
issuer rev2 (d8702e4c — honest narrowing + peer-uid HIGH fix), C6 rev3/B1/B2 (read_epoch never-0 +
apply_bump race). Advisory unless a real defect surfaces -> bounded follow-up. Verdict ->
.agents/plans/aqos-foundation-c/CATCHUP-CODEX-CONFIRMATORY-AUDIT-20260808.md. Runs concurrent with the
C6-B3 amended build (codex-20260808-111113).

## [2026-08-08T18:48Z] QUEUED for Codex-return (cooldown until 19:29:41Z)
- C6-B3 independent code review (target 36a5e2c4; CP-1..CP-4 + A2 + flag-OFF byte-parity). B3 committed,
  orchestrator-gated, amendment PASS-reviewed, default-OFF → safe while dormant; review is the
  confirmatory acceptance gate. Brief: scratchpad/c6b3-review-brief.md. Auto-redispatch waiter armed.
- C2-SCI HIGH+MEDIUM fix slice (from the catch-up audit): needs OWNER build grant (touches frozen ALA +
  C2-SCI) + implementer=Codex. One canonical ALA/C2 lease contract + fail-closed issuer epoch + real
  integration test (no fixtures). Blocks c2sci-activate.

## [2026-08-08T20:10Z] Codex DOWN until Aug 15 (usage limit, probe-verified) — queued for return
Codex hit a hard usage limit (probe `codex-...195843` → "try again Aug 15th 1:32PM"). Treat all Codex
outputs as non-gating until then; route gating reviews to Claude/local/Antigravity meanwhile (Rule 18).
Queued for Codex confirmatory audit on return (advisory unless a real defect surfaces):
- TEG-C1 R2 design (packet `94e6ab22`, PRD `2286e564`) — Claude re-review PASS(freeze-eligible); Codex
  confirmatory optional-but-wanted before the CORE build grant.
- H2A revised inventory (`1d7052f`, H2A-P0/H2A-P0B split) — Claude orchestrator re-review pending; Codex
  confirmatory on return.
- Flat-org friction consensus — Claude's 5 frictions logged; also routed to Antigravity NOW for the second
  independent view; fold Codex's view in on return.

## [2026-08-08T20:10Z] Antigravity lane has an UNDRAINED backlog (wake mechanism down)
Inbox has 3 pending advisories NOT processed: `c2-scheduler-context-issuer-rev4-review`,
`ala-c2-c6-b3r-advisory-20260808`, `flat-org-friction-consensus-20260808` (just dropped). Root cause: the
auto-wake watcher is enabled in the ai-dev profile but NOT running (the earlier failed nixos-rebuild did not
activate it), and `aq-antigravity-inbox wake` is owner-manual-gated; the direct switchboard path is dead by
design (503 remote_key_endpoint_mismatch — no API keys for Antigravity). OWNER ACTION to drain: either
restore the auto-wake service (rebuild/restart the user path unit) or run `aq-antigravity-inbox wake
<task> --actor owner-manual`. Until then Antigravity contributes nothing new despite 3 queued tasks.

## [2026-08-21] Codex RETURNED — large local-agent-reliability + harness batch queued for confirmatory audit
PROCESS NOTE (owner-flagged 2026-08-21): the commits below were built via a fast Claude-orchestrator →
Sonnet-implementer → local-dogfood → Claude-review-and-commit loop that SKIPPED PRD/plan ceremony (only
DESIGN.md docs written for 2 slices) and was NOT registered here as it landed — a discipline + communication
lapse, not a config issue. Registering retroactively now. These are advisory-review targets for Codex on
return (Rule 18): work committed while Codex was down; Codex's confirmatory audit is advisory unless it
surfaces a real defect (then a bounded follow-up, never rewrite history).

Commit range (all pushed to origin/main): cc63ac57 → 4650b1e6.
- cc63ac57 feat(local-agent): tool-call reliability — GBNF grammar fix (grammar_cache.py _object_rule:
  unquoted-keys + forced-empty-args), 256→512 budget, context supply chain (assembler+read_file gate),
  3 loop interventions (reread/noaction/edit-feedback). SECURITY-ADJACENT: grammar constrains model output.
- 47e03ea9 feat(local-agent): write_region line-range edit tool (Aider whole-format) + maturity gap analysis.
- ae9029ef fix(local-agent): shell_tools run_command artifact-strip (trailing JSON-envelope tail). SECURITY:
  touches the shell-injection guard — Codex, verify the trim never weakens injection rejection.
- 950f56e4 feat(local-agent): LLM record/replay cassette harness (llm_cassette.py + _call_llama wiring).
  Verify default-OFF is a strict no-op + request_key can't collide distinct requests + replay can't mask
  regressions.
- Ad-hoc Codex review ALREADY dispatched 2026-08-21 (codex-20260821-162310) covering these — fold its
  findings when it completes; this entry is the formal record.
Also NEW open finding (cassette-diagnosed): local-over-explores-run_command-instead-of-editing (issues-backlog).

## [2026-08-21] Verified-defect fix pass — PROVISIONAL commits, independent reviews QUEUED (async, non-blocking)
Owner directive 2026-08-21: dev velocity must not depend on lane presence. These Tier-0 fixes are committed
FORWARD (orchestrator-verified + tests) as `provisional-pending-review`; independent review is QUEUED here,
not blocking. Each flips committed→ACCEPTED only when its queued review lands clean. Absent-lane findings
fold in as bounded follow-ups (advisory unless a real defect; never rewrite history).

REVIEW TARGETS (for Codex — the reliable auto-reviewer — and any returning lane):
- `5c3e7a1d` fix(write_region+edit_file Tier-0 safety): path-traversal/symlink reject (reuses
  validate_file_path), stale-line-drift guard, EOF newline-merge, atomic write, truthful errors.
  test-write-region 57/57. VERIFY: is validate_file_path the RIGHT boundary (not bypassable via the new
  optional-guard path)? does the atomic os.replace preserve perms/ownership? is expected_region_sha
  computed over the exact bytes the agent will see (front-loaded citations)?
- PENDING (Cluster 1, building): replay/cassette CRITICALs — mock-tools default, flock, fail-closed replay,
  request_key collision+digest, retry-no-ReplayMiss. Will be committed provisional + queued here on landing.
- Codex's own 12-finding review + Antigravity's 2 verified CRITICALs are the source list; this pass fixes
  them — Codex should confirm each fix actually closes its finding (not just adds a test).
- `[Cluster 1]` replay/cassette CRITICALs (committed provisional): mock-tools-default, flock, fail-closed
  replay, request_key+digest, retry-no-ReplayMiss. VERIFY: does mock-tools stub leave the cassette KEY
  identical (it must — only side-effect skipped)? is the request_key now over-inclusive (keying on a field
  that legitimately varies could cause spurious misses)? does ReplayConfigError propagation ever strand a
  half-written cassette row?
- `[Cluster 3]` grammar_cache.py GBNF malformed-JSON (committed provisional): control-char exclusion,
  parenthesized alternations, required/optional ValueError. VERIFY: does [^"\\\x00-\x1f] correctly still
  allow all valid non-control UTF-8? does the ValueError-on-partial-required break any real caller that
  passes optional-prop schemas (search callers)? is the `value` rule truly complete for nested cases?
- [Cluster 4] agent-loop hard-termination-bound (committed provisional): ceiling 40 + wall 3600s + overrides.
  VERIFY: is 40 too low for any legitimate multi-turn task (would truncate real work)? does the wall-clock
  check use monotonic time (not wall clock that jumps)? does a bound-trip leave the worktree/state clean?
- [Cluster 5] artifact-strip moved to parser boundary (e8599514): tool_registry._strip_envelope_tail_artifacts
  + narrowed shell_tools net `\n}[}\s,]*\Z`. VERIFY: is the parser-boundary strip applied to ALL arg values
  or only the last? could a legit value legitimately contain a trailing `\n}` (rare but possible)? does the
  narrowed shell net still catch every real envelope-leak shape?
- [Cluster 6] gate the harness regression suites in tier0 (72c069ad): gate_agent_harness_regression_suites.
  VERIFY: does a deliberately-broken test ACTUALLY fail tier0 --pre-commit end-to-end (do the real break-it/
  fix-it proof)? are all 9 suites in the list (any missing, e.g. test-run-command-artifact)? does running 9
  suites add meaningful pre-commit latency?
- [PM-live + DoD-6] (committed provisional): propagate DoD dimension 6 "PM-tracked (live)" to
  .agent/CODEX.md, .agent/LOCAL-AGENT.md, .agent/GEMINI.md, .agent/WORKFLOW-CANON.md (Rule 16 parity —
  REQUIRED same cycle; currently only DEFINITION-OF-DONE + CLAUDE.md carry it → INCOMPLETE until propagated).
  Also: dashboard assets/aqos-progress-tracker.html should RENDER the now-available deps (gantt arrows) +
  priority_lane (kanban columns). VERIFY: does check-pm-tracker gate stay green with the new tracker editorial?
- [SUSPECT — cancellation-lifecycle 93f1eff4] The first local agent run AFTER this 378-line
  dispatch.py/task_registry.py rewrite produced a model_call that ran 1501s with tokens_out=0 /
  tok_per_sec=0.0 (silent first-token stall) on a ~2500-token prompt — while a direct curl to the SAME
  model/endpoint returns a small prompt in 8s. Candidates: (a) APU contention (load 7), (b) the slice's
  child wall-clock/watchdog/stream wiring regressed the agent-loop inference read. Codex/reviewer: verify
  _compute_agent_wall_clock + the child watchdog + streaming-read path don't starve/block the first token.
  Isolation test running to distinguish.
- [RE-DO — cancellation lifecycle] 93f1eff4 was REVERTED (1c317f2e) — A/B-proven it broke agent-loop
  inference (0 tokens for full budget; revert restored tool_calls in <1min). The clean-termination goal
  is real + was validated. RE-DO carefully: the child sessionization (new PGID/session) or the watchdog/
  wall-clock rewire blocks the child's HTTP stream to llama.cpp. Its acceptance MUST include an
  inference-smoke check (a tiny agent task produces tokens) so an inference regression can't ship again.
  Prior [SUSPECT] flag above is now CONFIRMED + reverted.
- [Rule 21 parity] COLLABORATIVE STEWARDSHIP added to CLAUDE.md — Rule-16 parity REQUIRED: propagate to
  .agent/CODEX.md, .agent/LOCAL-AGENT.md, .agent/GEMINI.md, .agent/WORKFLOW-CANON.md same cycle.
- [edit-verify coach gate] (provisional): AQ_EDIT_VERIFY post-edit no-op/dead-code/task-relevance coach.
  VERIFY: do the coach's static checks false-positive on any legit edit shape (multi-line strings, decorators,
  re-exported defs, dynamically-referenced names)? is the bounded retry truly bounded under all paths?
- [coach lint check + pyflakes] (provisional): the Python undefined-name coach needs pyflakes (added to
  base.nix) + a REBUILD to be live; shell path works now. After rebuild, re-run dogfood-01 to confirm.
  VERIFY: _reconstruct_pre_edit_content (edit_file reverse-substitution) — does it mis-handle multi-occurrence
  new_string? does new-breakage diffing hold when line numbers shift a lot?
- [edit_file kwarg-filter — CRITICAL un-block] (provisional): tool_registry.execute_tool_call did
  `handler(**tool_call.arguments)` verbatim. Local's GBNF tool-call JSON leaked the envelope's own
  "function" key INTO arguments → `edit_file_handler() got an unexpected keyword argument 'function'` →
  EVERY edit_file (and any handler without **kwargs) failed ok=False. This silently starved the entire
  local edit path AND the verify/coach gate (only runs on a SUCCESSFUL edit) — the root cause behind
  "coach_fired=0 despite the re-without-import bug landing." Fix: filter arguments to the handler's
  inspect.signature params (keep everything if it declares **kwargs); drop unknown keys with a debug log.
  Verified: edit_file with a stray {"function":...} now completes + mutates the file; write-region 57/57,
  edit-verify 37/37 unchanged. Applied directly by orchestrator (Opus) as a tiny/critical/fully-diagnosed
  hotfix — Rule-17 deviation reason: critical un-block, ~25-line defensive filter, no design surface.
  VERIFY (reviewer): (a) is silently dropping unknown kwargs the right call vs. erroring loudly — could it
  MASK a real schema drift where the model means a param the handler renamed? (b) does any registered
  handler rely on receiving an arg NOT in its signature (partial/functools-wrapped)? (c) should the drop be
  WARN not DEBUG so we still SEE the model emitting junk keys (observability of local's tool-call hygiene)?
- [env-tunable dogfood payload limit] (provisional): agent_executor _DOGFOOD_PAYLOAD_JSON_LIMIT
  (raised 14000->32000 in 0b8b1bef) is now read at call time via AQ_DOGFOOD_PAYLOAD_JSON_LIMIT
  (default 32000, invalid/<=0 -> default). Root cause it fixes: raising the default silently
  disabled test-noaction-intervention's before-HTTP rejection probe (15000-char prompt stopped
  exceeding the higher default -> the call fell through to the mocked HTTP path -> AttributeError
  on `except httpx.ReadTimeout`). Test now pins the ceiling (8000) instead of the module default.
  VERIFY (reviewer): (a) is call-time env read the right seam, or should the limit be frozen once
  per process for determinism? (b) does any operator doc need the new env var surfaced?
- [complete revert 1c317f2e test surface] (provisional): the cancellation-lifecycle revert
  (1c317f2e) reverted dispatch.py + task_registry.py + 2 fixtures but LEFT the 1060-line test
  test-local-delegation-artifact.py (created by the reverted slice 93f1eff4) asserting the
  reverted API (_publish_terminal_once / record_process_topology / _proc_start_time) -> 13/24
  AttributeError -> QA phase 0 (0.10.9 + 0.10.25) red since the revert. Fix: a live hasattr
  capability-guard skips exactly those 13 tests as SKIP-pending-redo when the API is absent, and
  AUTO-RE-ARMS when the queued cancellation redo restores _publish_terminal_once. 11/11 base tests
  still assert. VERIFY (reviewer): (a) is the skip-set exactly the reverted-feature tests (no base
  coverage silently skipped)? (b) confirm the redo's acceptance re-runs all 13 (guard flips green).
  NOTE this is the FIX for the incomplete-revert gap flagged in the cancellation-lifecycle RE-DO entry.
- [FOLLOW-UP — codify trunk-protection, Rule-16 parity] Owner ratified 2026-08-26 "keep the hook,
  work on branches." Memory captured (feedback-trunk-protection-bound-review). REMAINING: propagate
  the trunk-protection model (main = bound-independent-review Review-Disposition; un-reviewed work on
  branches; SUPERSEDES commit-forward-provisional-to-main) into CLAUDE.md Commit Discipline + .agent/
  CODEX.md + .agent/LOCAL-AGENT.md + .agent/GEMINI.md + .agent/WORKFLOW-CANON.md (Rule 16 — all same
  cycle or INCOMPLETE). Land on its own branch through the bound-review flow. Update AGENT-PARITY-MATRIX.
- [ROUTE — independent review of c5d35db2] branch local-agent/edit-file-kwarg-unblock. When any
  independent lane is up (Codex / fresh Claude flagship / Antigravity / local once trustworthy — NOT
  the author), review the exact staged patch, then merge to main with Review-Disposition: ACCEPTED +
  Reviewed-subject-sha256 (git diff --cached --binary --full-index | sha256sum) + Reviewed-by.
- [ROUTE — review coach freshness-gaming check] branch local-agent/coach-antigaming-checks (off
  edit-file-kwarg-unblock). Adds _looks_like_freshness_gaming to _verify_edit_quality — rejects
  timestamp-only bumps on freshness fields (dogfood-07 gaming class). 41/41 test-edit-verify.
  VERIFY (reviewer): (a) false-positive surface — any legit edit that ONLY changes a date on a
  freshness-named line (e.g. intentionally correcting a wrong date)? (b) does the 4-line cap miss a
  multi-stamp gaming edit? (c) should it also gate on the task mentioning stale/refresh, or is the
  structural signal enough? Merge ACCEPTED with bound review after edit-file-kwarg-unblock lands.
- [ROUTE — review Qwen3.6-35B-A3B-MTP-Q5 switch + P1 resource tuning] branch
  local-inference/qwen35b-q5-resource-tuning. activeModel=qwen3.6-35b-mtp-q5, ctx 8192, OOMScoreAdjust=-900,
  TimeoutStartSec 300, carries the flake update (llama 9222 for MTP). VERIFY (reviewer): (a) does Q5_K_S
  24.5GB actually fit + load in 300s on 27GB, or does it OOM/swap-thrash (fallback: Q4_K_XL 22.5GB)? (b) is
  OOMScoreAdjust=-900 right vs -1000 (never-kill)? (c) confirm the fetch adopts the manually-placed file
  without a 24GB re-download. Measured follow-up: ctx raise + observability trim + governor A/B.
- [ROUTE — review behavioral-verify gate + runner-leak fix] branch
  local-agent/behavioral-verify-and-runner-leak (off main). TWO fixes:
  (1) BEHAVIORAL VERIFY (agent_executor _behavioral_verify + _verify_edit_quality tail): runs the task's
  real check (AQ_EDIT_VERIFY_CMD, {file} substituted, bounded, fail-safe) after static checks pass; coaches
  on non-zero exit. Catches semantic wrong-fixes static checks accept (dogfood-03). Wired in the dogfood
  runner via per-task verify_cmd/test field. ACTIVATION: queue tasks need a verify_cmd added to exercise it.
  (2) RUNNER-LEAK (aq-local-dogfood-run): compound declared-file now parsed (dogfood-10's "a + b" leak);
  ALWAYS revert every touched file (owned+stray) on exit, not gated on edit_landed/collision; pre-dispatch
  tree-clean guard. test-edit-verify 48/48; classifier unit-tested. VERIFY (reviewer): (a) is reverting a
  "foreign" file safe in ALL runner contexts (dedicated run = yes; any shared-tree use = check)? (b) behavioral
  verify subprocess: injection/isolation surface of AQ_EDIT_VERIFY_CMD (operator-set, not model-set — ok)?

## [2026-08-29T04:22:47Z] REVIEW-NEEDED: local-agent/deleted-def-guard (daeb06b9)
- Author: claude-opus-4.8 (Rule 17 deviation: cheap lanes down/ineligible — see commit body)
- Subject: _find_destructive_deletion + _verify_edit_quality wiring; 13/13 guard tests, 69/69 edit-verify no-regression, tier0 44/0
- Reviewer needed: NON-author (Codex on return, or fresh flagship / antigravity). Confirmatory audit of the ast-based deleted-def-still-referenced logic + the shared pre_edit_full refactor. ACCEPTED -> merge to main; defect -> bounded follow-up.

## [2026-08-29T15:43:56Z] RESOLVED: local-agent/deleted-def-guard -> main 8fb7f693
- Codex independently reviewed 5 rounds, caught 4 real scope-correctness defects (all fixed), ACCEPTED c4e403b5. Merged with Reviewed-by: codex-cli. No catch-up action needed.

## [2026-08-29T15:49:23Z] REVIEW-NEEDED: local-agent/coach-events-observability (b5ab4437 amended)
- Author: claude-opus-4.8 (Rule 17 deviation: local ineligible for from-scratch CLI, Codex quota-strained). Read-only telemetry viewer scripts/ai/aq-coach-events + test (11/11).
- Reviewer: non-author. Low-risk (read-only, stdlib, fail-soft). ACCEPTED -> merge to main.

## [2026-08-30T21:18:29Z] RESOLVED: local-agent/coach-events-observability -> main 6705a454
- Codex reviewed 2 rounds (caught non-object-JSON crash, fixed), ACCEPTED, merged. No catch-up needed.

## [2026-09-04] REVIEW-NEEDED: feat/aqos-installer-p0-hardware-detector (P0 slice p0-hardware-detector)
- Author: claude-opus-4.8. **Rule 17 deviation reason:** Codex (the intended coordinator/implementer for
  this P0 slice, per its own progress note) is away; local Qwen is ill-suited to a multi-site rework of a
  detection module; owner directed "keep our dev cycle moving by resuming and noting your progress for the
  other agents' information, upon its return." Committed to a BRANCH (not main) per the agent-down fallback
  of the review-before-commit workflow — independent review is QUEUED here, never bypassed.
- Subject: `scripts/ai/lib/hw_probe.py` + `scripts/testing/test-hw-probe.py`. Implements PRD v2 §96
  (driver-INDEPENDENT detection). Changes:
  - `_enumerate_pci_devices()` — reads `/sys/bus/pci/devices/*/{class,vendor,device}` → deterministic
    BDF-sorted inventory `{bdf, pci_class, vendor_id, device_id}`; returns None (recorded in `undetected`)
    when PCI sysfs is absent.
  - `_is_display_class()` — PCI class base 0x03 (display controller).
  - `_drm_index_by_bdf()` — DRM VRAM/card evidence keyed by PCI BDF (driver-dependent ENRICHMENT only).
  - `_detect_gpu()` reworked: PCI class 0x03 is the PRIMARY presence authority; DRM (matched by BDF) +
    lspci are enrichment/fallback; explicit `outcome` (detected / none / insufficient_evidence); each
    device carries an `evidence` field (pci / pci+drm / drm / lspci). Reuses the existing AMD-APU / shared /
    dedicated memory-type classification. Degrades to DRM/lspci with outcome=insufficient_evidence when the
    PCI inventory is None.
  - `probe_hardware()` adds a top-level `pci_devices` field; `schema_version` bumped 1 → 2.
- Tests: 7/7 in test-hw-probe.py pass, incl. 3 NEW hermetic fixtures — GPU-present-via-PCI-with-no-driver
  (the live-ISO case: evidence=pci, card=None), no-PCI-inventory → outcome=insufficient_evidence, and
  multi-GPU deterministic BDF ordering (non-display device filtered out). Live probe on this APU: 35 PCI
  devices, GPU found by class 0x030000 (AMD 0x1002:0x1638), matched to DRM → evidence=pci+drm, mem=shared.
- Tier0 --pre-commit: passing after this doc-surface stage (the cross-surface contract required a connected
  handoff surface for the runtime change — this entry is it).
- Reviewer needed (NON-author): Codex on return (owns this P0 thread), or a fresh flagship / Antigravity.
  Confirm the PCI-primary authority, the BDF↔DRM matching (readlink correctness), the insufficient_evidence
  conservatism, deterministic ordering, and that schema_version=2 consumers are accounted for.
  ACCEPTED → merge to main with the bound Review-Disposition envelope; a defect → bounded follow-up.
- Coordinator note for Codex: this is only the DETECTOR slice (tracker item `p0-hardware-detector`). Still
  open on P0: `p0-ai-fit-policy` (separate digest-pinned model catalog — do NOT embed a model table in the
  detector), `p0-resolver`, `p0-module-catalog`. PRD v2 §92/§96/§98 respected: detector produces reusable
  hardware evidence, it is NOT the AI-fit contract.

## [2026-09-04] REVIEW-NEEDED: feat/aqos-installer-p0-ai-fit-policy (P0 slice p0-ai-fit-policy)
- Author: claude-opus-4.8. **Rule 17 deviation reason:** same as the detector slice — Codex (intended P0
  coordinator/implementer) away, local Qwen ill-suited to a from-scratch schema+evaluator, owner directed
  "continue with p0-ai-fit-policy and all next steps." Committed to a BRANCH off
  feat/aqos-installer-p0-hardware-detector (this slice depends on the detector's schema_version=2 evidence);
  independent review QUEUED here, never bypassed.
- Subject: implements PRD v2 §92 — a SEPARATE, digest-pinned AI-fit policy/model catalog + a deterministic
  evaluator. No model table or threshold lives in the install-plan schema or the detector (§92 satisfied).
  Files:
  - `config/schemas/aqos-ai-fit-policy-v1.schema.json` — Draft 2020-12, additionalProperties:false
    everywhere; versioned; closed/secret-free.
  - `config/aqos-ai-fit-policy-catalog-v1.json` — measured DATA only (reserves, backends, 8 models spanning
    nano→large). Numbers sourced with provenance from `ai-stack/models/registry.json@2.1.0` +
    `config/hardware-capability-matrix.json` + aq-os measured UMBM (3GB OS / 1GB KV reserve, Renoir
    n_gpu_layers ceiling 12). **sha256 c1bb1455ca8b4c75c47eeb912f4a51f50b2d4b8859ea96257fc45d70c3a4fe25** —
    this digest is what the resolved lock binds as `catalog_digests.ai_fit_policy_catalog_sha256`.
  - `scripts/ai/lib/ai_fit.py` — deterministic evaluator: hardware evidence (hw_probe v2) + catalog →
    recommended/limited/not_advised, eligible models, selected backend, explicit reserves/offload cap/
    context cap/downgrade reasons. HARD invariants: never full offload without known VRAM; CPU-only is
    `limited` never `recommended`; RAM-unknown / insufficient-evidence resolve conservatively.
  - `scripts/testing/test-ai-fit.py` — 10-case fixture matrix (desktop dGPU recommended, APU shared partial
    capped, cpu-only limited, dedicated-VRAM-unknown never-full, insufficient-gpu-evidence, ram-unknown
    not_advised, ram-too-small, deterministic order, catalog↔schema+digest stability, CLI digest).
- Validation: 10/10 tests pass. Live end-to-end on this APU box: verdict=recommended, backend=vulkan/partial/
  cap-12, usable RAM 23.2GB, recommends qwen3-32b, flags qwen3.6-35b as **limited** (RAM-tight) — which
  honestly matches the measured reality that the resident 35B swaps under load. tier0 --pre-commit green.
- Reviewer needed (NON-author): Codex on return, or fresh flagship / Antigravity. Confirm: (a) the
  never-full-offload-without-VRAM invariant holds on every path; (b) reserve math + headroom margin are
  honest (2GB recommended_headroom is an explicitly-unmeasured conservative margin — challenge it); (c)
  catalog provenance is faithful to the cited sources; (d) determinism (sorted models, stable digest). A
  known follow-up (registered here, not silently deferred): hw_probe's legacy `derived` sizing block
  (model_size_class / suggested_n_gpu_layers) now DUPLICATES this policy — it should become a thin
  projection of ai_fit (or be deprecated) so there is one sizing SSOT; left in place this cycle to avoid
  breaking existing consumers (aq-report/dashboard).

## [2026-09-04] REVIEW-NEEDED: feat/aqos-installer-p0-module-catalog (P0 slice p0-module-catalog)
- Author: claude-opus-4.8. **Rule 17 deviation reason:** same as the other two P0 slices — Codex away,
  local Qwen ill-suited to a from-scratch schema+validator, owner directed continuing all P0 next steps.
  Committed to a BRANCH off feat/aqos-installer-p0-ai-fit-policy (stacked: this slice is the resolver's last
  data dependency). Independent review QUEUED here, never bypassed.
- Subject: digest-pinned inventory of installer-selectable NixOS modules + a completeness validator.
  Files:
  - `config/schemas/aqos-module-catalog-v1.schema.json` — Draft 2020-12, additionalProperties:false.
  - `config/aqos-module-catalog-v1.json` — 29 modules (3 profiles + 7 roles + 6 CPU + 7 GPU + 6 platform),
    each with support predicate, structured resource cost, deps/conflicts, projected mySystem.* fields, and
    source path. sha256 455b5b1b0343486bdddeddbe1af0669c2f98a653e361ed65335f8e5de6938e4f — binds into the
    resolved lock as catalog_digests.module_catalog_sha256.
  - `scripts/ai/lib/module_catalog.py` — validator: completeness vs ACTUAL import wiring
    (nix/modules/hardware/default.nix + roles/default.nix + profiles/), deterministic (category,id) order,
    dep/conflict closure, multi-GPU non-exclusivity, and projection resolution (every projected field is
    consumed in the Nix tree; a mislabeled generic parent like cfg.hardware cannot rubber-stamp a leaf).
  - `scripts/testing/test-module-catalog.py` — 11 cases incl. drift-fails-closed (missing/phantom entry),
    projection-drift, the hardware-vs-deployment mislabel guard, dep closure, multi-GPU, order, digest.
  - tier0: new gate_aqos_module_catalog runs the suite when catalog/validator files OR the import wiring
    (hardware/roles default.nix, profiles/*.nix) change — so adding a module without cataloging it fails.
- Validation: 11/11 tests; validator PASS on the real tree; tier0 --pre-commit green. The validator caught
  two real bugs in my first catalog draft: (1) rootFsckMode is under mySystem.deployment, not hardware
  (recovery.nix reads cfg.deployment.rootFsckMode); (2) accelerationClass/rocmGpuTarget are auto-detected by
  discovery, not installer-projected — removed from projected fields. Both fixed; fail-closed completeness
  working as designed.
- Reviewer needed (NON-author): Codex on return, or fresh flagship / Antigravity. Confirm: (a) the
  parent-fallback resolution rule (>=3-segment field may resolve via its >=2-segment parent) cannot mask a
  real drift; (b) resource_cost classes are honest qualitative estimates (labeled as such, not measured);
  (c) the 7 roles match roles/default.nix (antigravity.nix intentionally excluded — not in the default
  import). ACCEPTED -> merge to main; defect -> bounded follow-up.
- Coordinator note: with detector + ai-fit + module-catalog done, all FOUR p0-resolver data deps (p0-schema,
  p0-hardware-detector, p0-ai-fit-policy, p0-module-catalog) now exist on branches. Recommended sequencing:
  review+merge these four to main FIRST so their digests are stable, THEN build p0-resolver (its golden
  cross-adapter fixtures bind those digests; building on unreviewed branches would churn the goldens).
  p0-mysystem-fieldset depends on p0-resolver.

## [2026-09-07] Claude resumed Codex's in-flight work during a scheduled 90-min break
Owner-directed: "resume [Codex's] work and fold in your own progress to continue dev momentum."
Coordinator seat temporarily back with claude-opus-4.8 while Codex is away.

**What I did (all on branch feat/aqos-installer-p0-execution-verifier):**
- **Committed + validated Codex's staged execution-verifier slice → 37bf6a10.** Codex left it staged
  mid-commit. I reviewed it as a NON-AUTHOR (design read: fail-closed, non-executing, inert projection
  enforced via projection_not_inert, closed signing_key_id+hmac-sha256 with constant-time verify, JCS
  byte-equality, catalog-digest binding), ran the full gate (**tier0 --pre-commit 50/0**, execution 9/9,
  resolver 8/8, schema OK, external-mcp pass), and committed it with Codex as Co-Author. Codex's own
  adversarial self-review (1 critical + 3 high, in issues-backlog) was already folded.
- **Added the p0-execution-verifier tracker item → 6d626d57** (check-pm-tracker PASS).
- Earlier this session: committed video-transcription tooling + an agent-swarm research artifact →
  7a9d5425 (unrelated to the installer; isolated pathspec so your staged index was untouched).

**Merge-readiness (for your merge train, Codex):**
- 37bf6a10 (execution-verifier): independent non-author review by claude-opus-4.8 DONE, gate 50/0 —
  ready to merge to main. I deliberately did NOT merge it myself to avoid diverging trunk (you own the
  main<->origin/main push train) while you were briefly away.
- 7a9d5425 (my transcription/research commit): I authored it, so it needs YOUR non-author review before
  main. Low-risk (a wrapper script + package-list add + a research .md).

**Follow-up I flagged, not guessed (PM dashboard honesty):** tracker items carry no `detection` signals,
so the projector shows every item DESIGNED even though 6 P0 slices are on main. They shipped via YOUR
resolver merge 22295832 ("integrate trusted P0 resolver") — schema, hardware-detector, module-catalog,
ai-fit-policy, resolver — plus mySystem-fieldset via e4fb2b79/abe16d24. Wiring commit_match needs your
commit→item mapping; left to you to keep the projection honest.

**Next unblocked (P1):** p1-golden-profile (deps p0-mysystem-fieldset ✓ + p0-hardware-detector ✓) — the
AQ-OS Workstation golden profile. p1-guided-tui + p1-parity-suite follow it.

Note: my original 3 slice branch-commits (6bb2e2ba/fd867e97/112c943e) are NOT in HEAD history — you
folded their CONTENT into 22295832 rather than merging the branches. Content is on main (what matters);
the branches can be pruned.

## [2026-09-07] P1 STARTED: aqos-workstation golden profile (p1-golden-profile)
Author: claude-opus-4.8 (holding coordinator seat during Codex's break; owner asked to start p1-golden-profile).
Owner will trigger the rebuild/switch to validate the build.

**Slice:** the AQ-OS Workstation golden profile — one super-tuned, hardware-adaptive path for professional
dev + gaming with OPTIONAL local AI.
- `nix/modules/profiles/aqos-workstation.nix`: base (always) = desktop + cppDev + gaming + virtualization
  roles, hardened kernel/crowdsec/secureboot posture, gamemode, firmware, dev fonts, touchpad defaults.
  Local AI is OFF by default (mySystem.roles.aiStack.enable = mkDefault false) and EVERY AI dependency
  lives inside a single `lib.mkIf aiOn` guard, so the AI-off path pulls in zero AI stack. AI-on enables the
  stable core only (aiStack role + switchboard + mcpServers + commandCenter) — NOT the experimental
  Foundation-C capability-lease/execution-cell activations (those stay ai-dev/dev-box specific).
- `nix/modules/core/options.nix`: "aqos-workstation" added to the mySystem.profile enum.
- `nix/data/profile-system-packages.nix`: aqos-workstation package list (pro-dev + modern CLI + the local
  transcription tools; no AI-data-service tooling).
- `flake.nix`: imports the profile module.
- `scripts/testing/test-aqos-golden-profile.py` (5/5) + tier0 gate gate_aqos_golden_profile: lock the
  invariant that no AI option leaks onto the AI-off base.

**Functional validation done (Nix eval, extendModules with mkOverride 10 on the host):**
- AI-off: aiStack=false, gaming=true, cppDev=true, desktop=true, mcp=false, switchboard=false, 32 pkgs.
- AI-on:  aiStack=true, mcp=true, switchboard=true.
- Flake evaluates cleanly with the new module imported (inert for other profiles).
Remaining: the operator rebuild/switch is the "builds green" proof (owner will trigger).

**Deps satisfied:** p0-mysystem-fieldset + p0-hardware-detector (both on main). **Next P1:** p1-guided-tui
(thin TUI emitting a resolved plan into the ACTIVE nixos-quick-deploy.sh) then p1-parity-suite.
Reviewer (non-author) on return: confirm the aiOn guard is the ONLY AI-dep site and the hardened defaults
are appropriate for a beginner-facing blessed default.

---
## [2026-09-08T16:48:59Z] Codex confirmatory — P1 guided-tui + parity (Codex lane down)
**Why queued:** Codex reviewer hit its usage limit (resets ~13:33 local) mid-review of feat/aqos-p1-guided-tui; process exited `failed`, no verdict written. Per Rule 18 the review was RE-ROUTED (never blocked) to a fresh independent Claude reviewer (sonnet, cold context — non-author) + a parallel local (Qwen) adversarial pass.
**Subjects to confirm (exact):**
- guided-tui commit: `2e34f519811b101cbabc10db2ddc495518a66540` — scripts/ai/aqos-guided-install + scripts/testing/test-aqos-guided-install.py
- parity-suite commit: `fb4ec61b72494ef671d465a189dc8ea35f94b831` — scripts/testing/test-aqos-adapter-parity.py
**Confirm on return:** (1) non-destructive (no rebuild/disk mutation; only --out write); (2) AI answer hardware-honest; (3) guided==manual==ai==legacy byte-identical through the one resolver (parity test non-trivial). Tests green at route time: guided 5/5, parity 3/3.
**Disposition:** advisory unless a real defect surfaces → bounded follow-up, never rewrite history. Verdict of record from the primary reviewer: .agents/plans/aqos-installer-experience/GUIDED-TUI-REVIEW-20260908.md

**UPDATE [2026-09-08T16:56:43Z]:** primary reviewer caught a real silent-data-loss defect (FAIL) → fixed at commit `5c95ff79` (guided emits {answers,host_target}; --adapter guided now exercised; round-trip regressions added). Codex on return: confirm the FIXED head `5c95ff79`, not the pre-fix commits. Tests: guided 6/6, parity 4/4, golden 5/5.

<!-- union-merged from factory/slice-claim (frontier branch) on integration -->
## [2026-09-08] Frontier context folded into pending reviews (via aq-frontier context)
Frontier research is now incorporated into reviews by default (seam wired). Applied to the current
review queue via `aq-frontier context "<review subject>"`:
- **Foundation-C / capability-security reviews** → relevance=17 (core). FE-8 (Landlock/eBPF egress pin,
  ADOPTED) is the directly-relevant frontier slice: pin untrusted MCP servers to loopback-only; attach to
  the C-series activation evidence. Reviewers of any sandbox/lease change should confirm it doesn't
  regress the deny-closed posture FE-8 targets. FE-3 (MCP/A2A governance gaps) notes we are AHEAD via
  capability leases — do not regress to a looser standard.
- **factory/slice-claim + agent-collaboration reviews** → the C-1..C-4 swarm-lessons folds already landed;
  FE-3 (A2A v1.0 interop) is the monitor-tier frontier item for our signed-A2A — a gap-check, not a rewrite.
- **installer reviews** → installer-deployment is a coverage GAP (no assessed candidate yet); a targeted
  `aq-frontier scan-topic` is recommended before the P4 bare-metal path, not blocking P0/P1.
Our verdict leads over frontier hype; adoption still passes the benchmark gate + tier0.
## [2026-09-08] Installer P0/P1 review ROUTED to available lane (agent-agnostic model); Codex queued
Per the available-agent-debate + catch-up model (never block on an absent lane): Codex (usual reviewer)
is session-limited, so the binding independent review of branch `feat/aqos-installer-p0-execution-verifier`
(5 commits ahead of main: 7a9d5425 research tooling, 37bf6a10 P0 execution verifier [already
orchestrator-reviewed as non-author], 6d626d57 tracker, 1caca03f handoff, e547101c P1 golden profile) was
ROUTED to a fresh independent flagship lane NOW. Focus: the golden profile's AI-off-has-no-AI-deps invariant
+ the cascade re-pins + verifier inertness. On OVERALL: PASS -> merge to main with the bound Review-Disposition
envelope (Independent-Review: PASS + Reviewed-subject-sha256 of the staged merge diff + Reviewed-by). 
**Codex on return:** confirmatory audit of the same branch — advisory unless it surfaces a real defect (then
a bounded follow-up, never rewrite). Dev cycle does not wait.
## [2026-09-08] CORRECTION: frontier findings are PROPOSALS pending multi-expert debate (not adopted)
The earlier "[2026-09-08] Frontier context folded into pending reviews" note described FE-8 as "adopted" and
FE-1 as "approved". Per the owner's no-auto-approval directive (commit f20220d6), ALL frontier findings are
now PROPOSED (status new) and require multi-expert debate -> consensus (>=2 independent supports, no open
reject) -> accepted before any fold/implementation. FE-1/FE-3/FE-8/FE-10 etc. are candidates awaiting the
team's adversarial review, NOT accepted. Absent lanes' verdicts are queued here (same model): a finding can
reach consensus on available lanes now, and a returning lane's later verdict is folded as advisory unless it
surfaces a real defect (-> re-open). `aq-frontier review <id>` opens the debate; `verdict`/`accept` gate it.
## [2026-09-08] Multi-lane utilization audit + live routing (all lanes leveraged, absent ones queued)
Owner directive: fully leverage Antigravity/Gemini + local models within the agent-agnostic system.
Audit: `aq-antigravity-inbox` present + 3 antigravity daemons running; `delegate-to-local` present + local
Qwen serving (:8080 ok); `config/model-coordinator.json` lane ladder includes current Gemini IDs
(gemini-3.1-pro / 3.5-flash) AND local Qwen tiers. Wiring correct.
Live lane state:
- **local (Qwen) — ENGAGED, contributing.** Gave a substantive adversarial verdict in the frontier debate:
  FE-8 (Landlock egress) = CONCERNS — "redundant; bwrap cells already enforce network namespaces +
  loopback egress; Landlock adds kernel complexity without a new attack vector." Recorded via
  `aq-frontier verdict FE-8 --lane local`; FE-8 now BLOCKED (a real concern on record), correctly NOT
  auto-adopted. Local is a first-class debate lane.
- **Antigravity (Gemini) — WIRED + available (reviewer/advisory only, untrusted).** Has one OBSOLETE pending
  item (`aqos-installer-prd-review.md` = installer PRD v1 review, superseded by v2/done) — should be
  archived. ROUTE to it (fresh inbox task + owner/dispatch-once wake): FE-3 (MCP/A2A interop — its domain)
  advisory review + an installer-P1 advisory pass. Its input folds as advisory (never binding).
- **Claude flagship (installer binding review) — QUEUED.** The fresh-lane reviewer got tier0 49/0 (green)
  and was confirming the verifier fail-closed paths, then hit the Claude session limit (resets ~01:30 PT).
  Queue for its confirmatory completion on reset.
- **Codex — QUEUED** (session-limited) for confirmatory audit of the installer branch.
Installer merge: needs one capable non-author BINDING review. Both capable lanes (Claude flagship, Codex)
are session-limited -> per the model the dev cycle does NOT block; the binding review is queued for the next
capable lane to return (Claude ~01:30 PT), while local + Antigravity provide advisory input now. The branch
stays validated (tier0 green) on feat/aqos-installer-p0-execution-verifier; merge lands on the returning
binding PASS + envelope; Codex confirms after.
## [2026-09-08] Installer P0/P1 binding review -> FINDING -> FIX (review cycle working)
Codex (independent, non-author) reviewed feat/aqos-installer-p0-execution-verifier. Verdict:
- CONFIRMED GOOD: hash-chain + verifier checks consistent, expected MAC reproduced, all tamper cases fail
  closed, verifier has no execution primitive; package baseline re-pin HONEST (P1 parent + target both eval
  hyperd-ai-dev = 375, so 369->375 corrects stale evidence, not a hidden delta).
- BINDING DEFECT: "AI-off package leak" — the aqos-workstation golden base list carried openai-whisper +
  whisper-cpp (ML/ASR runners) on the ALWAYS-ON path, so AI-off installed AI packages (invariant violation).
  My golden test missed it (it checked mySystem options, not the package list — and actually REQUIRED
  openai-whisper).
FIX (claude-opus-4.8, commit 1f8920b7 on branch fix/aqos-golden-ai-off-leak, cut from installer HEAD
e547101c so it carries the full corrected branch): removed openai-whisper + whisper-cpp from the golden base
(kept in ai-dev where AI is always on; arrive via aiStack role on the golden AI-on path); yt-dlp + ffmpeg
stay (general media, not AI). Strengthened test-aqos-golden-profile.py to FORBID AI/ML runners on the golden
base. golden test 5/5; nix parse OK; hyperd-ai-dev baseline unchanged.
MERGE STATE: fix/aqos-golden-ai-off-leak is the mergeable corrected branch. Needs a light NON-AUTHOR
re-confirm of the single fix (does it close the leak without breaking anything) before merge to main —
queued for the next capable binding lane (Codex on its worktree release, or Claude flagship on reset). Codex
confirmatory audit continues. The dev cycle does not block; the branch is validated + corrected.


---
## [2026-09-09T20:05:09Z] QUEUED: research/graft-parity -> main review (reviewer lane flaky)
Subject: research/graft-parity branch (2 commits: trendshift+graft frontier sources + Graft/named-repo/trending candidates + round-table verdicts). Data-only (sources.yaml + BACKLOG.jsonl, ~31-line additive diff).
Why queued: local-direct reviewer failed twice (connection-closed, then hung) though the model is healthy; Codex busy on the body-hash re-target; not worth a heavy Claude spawn for a low-risk data diff.
Action on lane-return (Codex or fresh Claude): quick data-accuracy review (sources real, verdicts faithful to the round table, no secrets) -> merge to main with the bound envelope. Non-author reviewer required (Claude/Opus authored the entries).

---
## [2026-09-09T21:30Z] LANE DOWN: Codex usage-limited until ~2026-09-10 00:56 — reviews queued
Codex hit usage limit (resets Sep 10 12:56 AM). Never-block (Rule 18): work continues on branches with
substitute lanes; trunk stays gated. QUEUED for Codex on return (or a fresh independent Claude flagship):
1. **s1a — disko layouts + VM install harness** (end-to-end bare-metal plan, slice s1a). Being IMPLEMENTED
   now by a Claude sonnet sub-agent (Codex down; capability reason: disko/LUKS/qemu-install is complex
   systems integration beyond local's single-edit envelope). Orchestrator (Opus, non-author of the impl)
   reviews + merges build-verifiable parts; Codex confirmatory audit queued for the exact merged subject
   hashes. Substitution recorded per Rule 18.
2. **fix/aqos-golden-ai-off-leak** (1f8920b7) — still needs non-author re-confirm (I authored it; cannot
   self-review). Independent lane on return.
3. **research/graft-parity** — data-accuracy review still pending (I authored; local reviewer failed twice
   earlier — retry local now-resident, or Codex/Claude-flagship on return).
Local-Qwen (healthy) engaged in parallel on bounded s1b/s2 plain-language installer copy (never-skip-local).

---
## [2026-09-10T04:45Z] BOTH flagship implementer lanes rate-limited — s1a re-queued
Codex usage-limited until ~00:56; Claude sonnet sub-agent (s1a impl) hit session limit, resets ~00:50.
Local healthy (finished installer-copy well; on packaging-tool copy now). Never-block: design + local work
continues; s1a CODE implementation queued for whichever flagship resets first (~00:50-00:56).
**s1a breadcrumb (preserve — the sub-agent found this before dying):** disko's ROOTLESS in-VM test path is
`diskoLib.testLib` in the disko flake's `lib/tests.nix`. Start s1a's harness there (partition a virtual disk
+ boot, no host root). Full s1a brief: END-TO-END-BARE-METAL-PLAN.md slice s1a.
NEW TRACK queued: **aq-factory-pack** (state packaging/cloning tool) — spec written
(.agents/plans/factory-state-packaging/TOOL-SPEC.md); implementation queued for flagship reset. Parallel to
the install track.

---
## [2026-09-10T14:20Z] Codex OUT until ~2026-09-14 23:42 (multi-day) — re-route, do not wait
Codex usage limit now resets Sep 14 (not tonight) — it failed the s1a attempt at SessionStart. Re-route all
Codex-queued reviews to other eligible independent lanes (fresh sonnet / local), never wait days:
- fp-1 (6f3ffcd4) confirmatory SECURITY audit — route to fresh sonnet or Codex-on-return; findings already
  logged in issues-backlog (portability recipient, dry-run-reads, name-traversal).
- fix/aqos-golden-ai-off-leak re-confirm; research/graft-parity data review — still need independent non-author.
- s1a RE-DISPATCHED to a fresh sonnet sub-agent (Codex out); breadcrumb: disko rootless VM test =
  `diskoLib.testLib` in disko flake lib/tests.nix.

---
## [2026-09-10T21:30Z] s1a LANDED (5430d793) — Codex confirmatory audit queued
s1a (disko partition/install/boot, plain+LUKS) merged after Opus non-author review + both-layout VM proof.
QUEUE for Codex on return (~Sep 14): confirmatory audit of 5430d793 (esp. the LUKS test-keyfile fixture +
the two gate remediations: suspend-resume out-of-scope note, package-count baseline refresh).
Stray cleanup (not s1a): a working-tree deletion of .agent/collaboration/antigravity-inbox/
aqos-installer-prd-review.md (archived to .agent/archive/antigravity-inbox-20260910/) was RESTORED to unblock
the package-count guard's tar; if that archival was intended, redo it deliberately as its own commit.
Also untracked build artifact aqos-vm.qcow2 in repo root (from a VM run) — archive/gitignore when convenient.

---
## [2026-09-11] fp-2 aq-factory-push MERGED (8b8a665a) — Codex SECURITY audit queued (HIGH priority)
Security-critical (state -> git push). Opus non-author review PASS (encrypt-to-target pipe no-plaintext-to-disk,
fail-closed secret-scan on exact staged bytes before push, confirm-gated, OAuth-only, shellcheck 0, errexit
masking bug found+fixed). Codex on return (~Sep 14): confirmatory SECURITY audit of 8b8a665a — re-encryption
pipe, scan completeness vs .gitleaks.toml, confirmation/abort paths, LFS pointer integrity. Actual pushes are
owner-gated. Resolves fp-1 portability-recipient finding.

---
## [2026-09-14] RECORDED: L2B-B shadow-accepted (VERDICT PASS) + program-plan projection refreshed to ground truth
Pivot back to Phase-1 (Core Engine). Verified L2B-B is genuinely landed: subject files present at HEAD, focused
oracle 16/16 PASS, `payload_normalization_status` passthrough present, `VERDICT: PASS` in L2B-B-CODEX-ACCEPTANCE.md.
Landed 99364942 (base) + 0262be3c (AM4 reconciliation). It is a SHADOW kernel — `normalize_endpoint_payload` has
NO live callers yet (live cutover deferred→Product D by B1 design). Recorded in ACTIVATION-AUDIT.md with honest
5-dimension attestation + dated deferral. Retired the stale suspended AM5 drift-recovery draft (SUPERSEDED banner).
Refreshed UNIFIED-PROGRAM-PLAN projection (was stale, dated 07-13): L2B-B ✅; ALSO corrected Foundation C row
(was "NOT STARTED" — WRONG): C shadow-build slices already landed default-OFF (ALA rev4 51795389, C2-SCI issuer
2c36e7d3, cap-enforcement dashboard 81aa665a; flags default 0 / enable=false; activation gated on B1 tail + Q3).
CATCH-UP for returning independent lane (Codex or fresh Claude flagship, non-author of these doc edits): confirm
the projection edits faithfully match ground truth (commits are ancestors of HEAD; L2B-B shadow-not-live claim).
Advisory unless a real defect. NEXT Phase-1 work: B1 tail (chat/batch parity in shadow) → closes Foundation B1.

---
## [2026-09-17] QUEUED for Codex (+ Antigravity advisory): local-producer-timing + gate-hygiene + CS-4
Codex lane was absent while Opus (integrator seat) completed its queued local-producer-timing work.
Landed on main (independent non-author review PASS by a fresh Claude reviewer; Opus authored the
correctives, so an independent-lane confirmatory pass is owed):
- **d0b814cb** `feat(local): record producer phase timing metadata` — corrected candidate, subject
  `8611af11e684a37d2e9e4e12f886441102ed1b260f1daeeb6588d40a1486ae93`. Codex authored the substance
  (candidate 80b04d95); Opus found+fixed a regression it hid: `_call_llama` referenced
  `self._timing_invocation_sequence` (set only in `__init__`) → AttributeError for `__new__`-built
  executors (test-noaction-intervention.py make_executor). Fix = defensive
  `getattr(self, "_timing_invocation_sequence", 0) + 1`. CONFIRM: getattr fix behavior-preserving
  (0→1→2 for fully-init'd) + best-effort; content-free/fail-closed axes unchanged. Live probe validated
  (observed failure receipt, honest nulls). IMPLEMENTED_FOLLOWUP_REQUIRED — dashboard activation live.
- **caa2fb6f** `fix(governance): classify delegate-24h-success (0.8.1) as live-service`, subject
  `ea5edbff1ffa7683c70360efe20eb81a4e8dc846ee0bc291b28067293973e6c8`. Rule-19 gate hygiene: 0.8.1
  (delegate 24h success) added to LIVE_SERVICE_CLASS_IDS → WARN in --pre-commit, HARD in --pre-deploy
  (same class as 0.10.22). CONFIRM (anti-gaming): 0.8.1 is genuine live telemetry, rate not
  faked/suppressed, all-or-nothing WARN logic intact, deploy-gating preserved. WR-5 extension documents it.
- **CS-4** (in progress this session): concurrent-dispatch isolation proof + delegated-worktree
  visibility. Codex confirmatory review to be appended with exact subject sha once landed.
Antigravity/Gemini advisory dispatched to the inbox (task `timing-gate-hygiene-review-20260917`) for an
independent second perspective on d0b814cb + caa2fb6f. All advisory unless a real defect (then a bounded
follow-up, never rewrite history).

---
## [2026-09-17T22:05Z] CODex resume: timing candidate supersedes stale queue projection
The currently authoritative local-producer-timing candidate is isolated at
`/tmp/aq-local-producer-timing-20260917`, branch `factory/local-producer-timing-20260917`,
tip `c4bf94b32a27d903b518b951c15e51b5e428a994`, based on `f9ab7e429874eb32f91c04889aa7189daa213787`.
Combined diff SHA-256: `aa292cf1849d525dcdc976ac02b4d7514b1a3f502d9720ac519150034f28deeb`.
The candidate includes the bounded compatibility fix for lightweight `__new__` executor fixtures;
focused suites are green (50/50 no-action, 23/23 delegation, 16/16 L2B, 18/18 budget), and the
branch is pushed. Antigravity F2 advisory review is claimed and pending against this exact tip.
Luna/Terra remain quota-blocked; no review credit is assigned. Binding cold review and integrator
checkout Tier-0 remain required before promotion. Main is intentionally not staged or merged because
the shared tree contains preserved concurrent work.
**Catch-up actions for returning lanes:** Claude — perform independent review of c4bf94b3 and privacy/
identity invariants; Gemini/Antigravity — complete F2 advisory and flag only bounded defects; Luna —
retry a concise mechanical qualification only after quota reset. Do not rewrite the candidate or
claim acceptance without exact subject-hash binding.

---
## [2026-09-26] QUEUED: full-cohort coverage audit for recent Claude-authored work

Owner direction: recent Claude-authored or Claude-coauthored subjects that did not receive the full
flat-coordinator cohort must be reviewed by **Codex + local Qwen + Gemini/Antigravity** against the
same expert-team baseline. Existing single-lane or same-provider reviews remain useful evidence but
do not count as full-cohort completion. Reconcile this provisional inventory against exact review
artifacts before dispatch so already-covered subjects are not duplicated (finding-freshness rule).

Priority groups, all hash-bound:

- **P0 — security/runtime enforcement:** `29154d06` factory evidence/TOCTOU hardening;
  `a6d907cf` + `f82a92bc` activation auto-revert guard; `2ef1406e` C6 mechanism-test
  deactivation; `ebffbcb9` focused-CI freshness classification; `22c0c19b` + `4c6db070`
  C6d journal recovery; `6b289376` C6-S launch-socket topology; `1160f18f` C6a launch
  authorization (branch candidate, active round `c6a-impl-binding-review-20260925`, not yet main).
- **P1 — model/tooling/configuration:** `6d2a624c` baseline agentic toolchain;
  `4a979951` Anthropic model refresh; `240f26ee` Gemini/OpenAI model refresh; `a09a1ae8`
  state-of-the-art engineering-gap backlog.
- **P2 — Foundation-C plans/designs:** `c2d1e8b5`, `22e4b2b0`, `e87cc6c7`, `891b1eae`,
  `093c4881`, `51f34902`, `4d0005ef`, `9066e259`, `44b1c6e0`, `fbf5608d`, `f9c51dda`,
  and `2e733335`. Several have independent Codex binding-review documents; audit whether local and
  Antigravity saw the same frozen subject before marking cohort-complete.

Execution contract:

1. Generate a machine-readable ledger mapping subject hash -> author -> changed paths -> existing
   review artifact/hash -> missing cohort lanes. Absence of a `Reviewed-by` trailer is a review
   signal, not proof by itself.
2. Fan out bounded groups with `aq-collab-round`; do not ask local Qwen to ingest the whole set in
   one context. Each pass uses the same baseline across lanes; group by risk and shared files.
3. Each contribution states the exact subject hash and ends in a terminal disposition. Unavailable
   lanes receive a catch-up entry and no review credit.
4. A real defect opens a new bounded follow-up against current HEAD after freshness reproduction;
   do not rewrite merged history or issue an activation grant from stale findings.
5. Cohort completion is observable in the dashboard/QA review-coverage surface; if that surface
   cannot distinguish single-review from full-cohort coverage, log and implement that gap as a
   separate service-coverage slice.

---
## [2026-09-26] QUEUED: C6a revision (v2) confirmatory review — down lanes
Round `c6a-impl-binding-review-20260925` REJECTED 3/4 (codex, antigravity, claude; local pending) on subject `1160f18f`: `consume_launch` malformed-record accept + backward-time accept, source-grep dashboard observability, `task_revision` bool/int. Revision dispatched to Claude Sonnet (the only implementer lane up — local mid-review, Codex quota-limited) -> branch `factory/c6a-impl-v2`. CATCH-UP: local + Codex (on return) run a confirmatory binding review of `factory/c6a-impl-v2` against the three findings (subject sha256 in the branch handback); advisory unless a real defect, then a bounded follow-up. Do NOT gate the revision's fresh cohort round on the down lanes — they contribute in-situ or after return. Substitution recorded per Rule 18 (implementer routed to available lane; binding review stays multi-lane).

---
## [2026-09-26] BLOCKED (authorization gate, NOT lane-availability): C4 egress-gate implementation
C4-impl was dispatched and CORRECTLY STOPPED before any code (branch `factory/c4-impl` created, 0 commits, discarded). C4 is enforcement-tier; `C4-DESIGN-AND-AUTHORIZATION.md` frontmatter `implementation_authorization: NONE` + `PREPARED_ONLY`. The [AMEND-C4] amendment (merged as a *proposed doc* via #341, commit 2e733335) is still `status: PREPARED_ONLY — NOT accepted`. The earlier "ACCEPT" verdict for the amendment was produced by an Opus sub-agent but its review file (`CODEX-C4-AMENDMENT-BINDING-REVIEW-20260924.md`) was NEVER committed (untracked only) → NOT an authoritative accepted record. Base C4 design's only committed review = `REQUEST_REVISION`.
**Required before C4 (and therefore C6b/C6e) can build — cohort + owner:**
1. [AMEND-C4] gets its own independent binding review with a committed `PASS` (subject-hash bound). Binding acceptance may be Codex (on return) OR a fresh capable flagship OR Gemini/Antigravity OR local — whichever is up + independent; record it as a COMMITTED file per the review-record convention (not untracked).
2. C4 rev2 (as amended) gets a fresh committed independent `PASS` against its exact bytes.
3. Owner single-use build activation recorded for that frozen PASS'd revision.
Only then re-dispatch the C4 egress-broker/epoch-recheck-teardown implementation. Do NOT fabricate a PASS or build dormant around this gate (Root-Cause Discipline / anti-gaming). C6b + C6e depend on C4, so the C6 build stack pauses here pending this chain.

---
## [2026-09-26] UPDATE + QUEUED: [AMEND-C4] binding review COMMITTED (substitute lane) + citation fix — Codex confirmatory
Item #1 of the C4-blocked chain above is now progressed on an AUTHORITATIVE committed record. Codex hit its usage limit (resets ~13:59) mid-C4-amendment review → re-routed to a fresh Opus reviewer (Rule 18 substitution, recorded). Opus committed a binding review (`.agent/collaboration/CLAUDE-OPUS-C4-AMENDMENT-BINDING-REVIEW-20260926.md`): **all 5 substantive checks CONFIRMED, narrowing logic sound**, VERDICT = REQUEST_REVISION with the SOLE blocker being stale internal line-citations. That mechanical defect is now FIXED in the same PR (branch `factory/c4-amendment-review`): `supersedes_on_acceptance` §4/§7/§8/§9 anchors → 242-246/302-305/327-330/387-389, `scope`+A.4 teardown refs 140-144 → 237-241; each anchor re-verified against the committed 396-line geometry before editing. Independent local bounded re-verify was dispatched (`b274hlqls`) but ABORTED incomplete (aq-agent-loop read-stagnation guard, reads=5; llama.cpp itself healthy — see issues-backlog LOCAL-LANE); owner directed skip-local. Independent second-lane confirmation therefore rests on Codex's queued pass below (plus orchestrator ground-truth re-check of every anchor against the committed 396-line file before editing).
CATCH-UP for Codex on return: confirmatory binding review of `factory/c4-amendment-review` (subject sha256 in PR) — confirm (a) the 5 substantive checks and (b) the corrected citations resolve to the right content. Advisory unless a real defect (then bounded follow-up). Once a committed confirmatory PASS lands, the amendment is promotable at C4 freeze → unblocks chain items #2/#3. Do NOT gate the citation-fix PR merge on Codex's return — the fix is a verified mechanical correction of the reviewer's own prescription; ACTIVATION (C4 freeze/flag-on) remains gated on the full chain + owner act.

---
## [2026-09-26] QUEUED: Stage 1 owner-key-lever (P-F4) activation-readiness consensus vote — Codex + local
Round `stage1-owner-key-lever-activation-20260926` OPENED (proposal + orchestrator vote committed). Decides ACTIVATION readiness ONLY — no switch flips; activation stays the owner's gated act after consensus + guard-armed. Roster reality at open: claude voted `ACTIVATE_WITH_CONDITIONS` (split 1a enable-only / 1b P-F4; guard revert = allowlist-rollback; ceremony via `submit --signed --socket`; Stage 1 is C4-independent); Antigravity task dropped to its inbox (3 tasks already undrained — IDE not actively responding, so async); Codex quota-limited until ~13:59; local SKIPPED (owner-directed, read-stagnation loop).
CATCH-UP:
- **Codex (on ~14:00 return):** binding confirmatory vote in `.agents/plans/stage1-owner-key-lever-activation-20260926/codex.md` — read PROPOSAL.md + claude.md; confirm/dispute the 5 questions, especially Q3 (allowlist-rollback revert adequacy for a Nix-module `enable=true` control) and Q1 (1a/1b split). This is the independent second lane the consensus needs before the owner's activation act.
- **local:** skipped this round (broken); optional late vote if restored, advisory.
Do NOT close the round or greenlight activation on the thin (claude-only) roster — round stays OPEN until ≥1 independent lane (Codex or Antigravity) votes. Orchestrator aggregates via `aq-collab-round aggregate` when votes land.
