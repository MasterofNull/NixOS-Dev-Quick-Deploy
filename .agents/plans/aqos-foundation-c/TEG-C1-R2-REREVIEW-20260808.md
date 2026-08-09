---
doc_type: plan
id: teg-c1-r2-rereview-20260808
title: TEG C1 R2 — independent re-review (freeze gate)
status: draft
parent_prd: trusted-execution-gateway
slice: C6-B3R-C1
date: 2026-08-08
reviewer: "Claude Opus 4.8 (independent of authoring; Codex authored R1+R2)"
verdict: "PASS — freeze-eligible"
---

Subjects (exact-hash): TEG-C1-DESIGN-PACKET-20260808.md (R2) sha256
`94e6ab22fff3824b441f289a034ef593edb4630b1b2aff97d07816b6faaa3477`;
PROJECT-TRUSTED-EXECUTION-GATEWAY-PRD.md (R2) sha256
`2286e564c2e7a617d6d7027cba8964b34817bd71916731fbdd46860d9c4069f0`;
predecessor pinned to accepted ALA-C2 commit `3d45e03ccea880ee22ab6022cdd730f98b0513d1`.
Independence caveat: I wrote the R1 orchestrator concurrence on DIRECTION, not the design packet.

# TEG C1 R2 independent re-review

Verified R2 against the blocking findings in TEG-C1-DESIGN-REVIEW-20260808.md (R1–R5) and the orchestrator
staging guard in TEG-C1-ORCHESTRATOR-REVIEW-20260808.md. Read the full R2 packet; did not author it.

## Findings closed
- **R1 (lifecycle + token ordering):** CLOSED. §3 one normative transition table incl. `revoked`
  (queued→revoked, held→revoked) with sole-actor / expected-revision-fence / durable-evidence / slot-release
  per row; launch invariant create+fsync-token → CAS held→launch_authorized → handoff → consume-once → CAS
  →running; `launch_authorized` is the linearization point; post-commit epoch bump = `already_starting_or_running`,
  never claimed prevented.
- **R2 (crash-after-linearization):** CLOSED. §4 parked `possibly_started` (no new state), never auto-relaunch/
  misreport; ≤3 authenticated queries in 60s then park. §6 full crash matrix at every marker/fsync/replace/
  dir-fsync/CAS-ack/handoff/consume/provider/receipt boundary; invariant provider-start ≤1, consume ≤1, no
  slot release before durable evidence, no false terminal.
- **R3 (identity/idempotency/cancellation):** CLOSED. §2 TEG-assigned 128-bit id; idempotency bound to
  domain-separated envelope_digest + (namespace, contract_revision, key); equal-key/different-digest →
  `idempotency_conflict`; public response only a redacted correlation receipt; cancellation reserved to the
  separately-authenticated `aq-teg-cancellation-authority`; SO_PEERCRED/UID/group never authorize disclosure/cancel.
- **R4 (private UDS identity + response integrity):** CLOSED. §7 one principal; split public/private sockets +
  groups; owner + ALL agents excluded from private; expected server UID via peer creds; symlink-safe; crypto
  verification of ALA/C2 facts; the launch epoch must EQUAL the epoch bound into the signed C2 context (mismatch
  denies) — cleanly resolves the unsigned no-key epoch reader. 6 named adversarial tests.
- **R5 (CAS + fencing):** CLOSED. §5 stable pre-created lock inode + O_NOFOLLOW + type/owner/mode validation;
  monotonic persistent fence; O_CREAT|O_EXCL|O_NOFOLLOW markers; fsync-temp + atomic same-dir replace + dir
  fsync; corruption fail-stop; stale-writer exclusion at CAS/rename/ack; monotonic deadlines + wall-rollback
  fail-closed; restricted old-fence evidence reconciliation lane that cannot create a token or authorize launch.

## Orchestrator staging guard — INCORPORATED
§8 Slice one = CORE broker + lifecycle/CAS/fence/crash + launch linearization + one-use token + ALA/C2/epoch
verification + hermetic fake-authority/fake-provider proof + minimum observable AND intervenable health.
Follow-ons (ceiling-matrix tuning, cancellation-authority service, extended TUI/Agent-Ops panels) explicitly
"do not enlarge slice one." Conservative caps are enforcement-not-tuning.

## Boundary checks
- C4 network-egress explicitly out of scope (§3) + stop-on-C4-expansion (§9). CLEAN.
- No unbuilt program made authoritative ("TEG, not aq-dispatchd", §1).
- Predecessor pinned to accepted ALA-C2 commit 3d45e03c (§1, §9); byte-level supersession requires re-pin +
  independent review.
- PREPARED_ONLY maintained throughout; authorizes no implementation/activation/Nix-eval/socket-start/commit.

## Verdict
**PASS — freeze-eligible.** All R1–R5 closed, staging guard incorporated, predecessor pinned, C4 clean.

## Independence caveat + recommendation
I authored the R1 orchestrator concurrence on DIRECTION (not the design). For a security-critical freeze, an
OPTIONAL fresh-lane confirmatory pass (a Codex sub-agent or Gemini/Antigravity advisory) before the eventual
CORE build grant would be belt-and-suspanders; it is not required to freeze. Freeze is the owner's call.

Next gate: owner freezes the R2 design → (later, separate, staged) CORE build grant binding these exact SHAs.
No implementation/activation authorized here.
