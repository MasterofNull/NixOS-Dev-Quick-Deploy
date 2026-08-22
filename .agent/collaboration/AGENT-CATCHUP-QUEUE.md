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
