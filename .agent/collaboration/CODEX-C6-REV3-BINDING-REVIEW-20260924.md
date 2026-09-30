# C6 Revision 3 — Independent Binding Re-Review

Subject: `.agents/plans/aqos-foundation-c/C6-DESIGN-AND-AUTHORIZATION.md` revision 3  
Review role: independent binding reviewer  
Disposition: **REQUEST_REVISION — not freeze-eligible**

The cryptographic shapes are directionally sound: bump requests are owner-signed and schema-closed; unknown/revoked keys deny; the C2-SCI issuer verifies an asymmetric lease and signs an audience-bound context; the scheduler gate is specified default-OFF; and authority-unavailable paths are intended to deny privileged work. Those properties do not cure the binding defects below.

## Numbered findings

1. **HIGH — No authenticated carrier connects the landed C2-SCI decision to the live F2.5 runner.**  
   **Location:** `C6-DESIGN-AND-AUTHORIZATION.md` §3.1 lines 212–219, §3.2 lines 223–228, and §4 lines 244–273; `scripts/ai/lib/dispatch.py` at rev3's landed baseline, lines 1125–1231; corroborating integration evidence in `C6-B3-LIVE-SEAM-RECONCILIATION-20260808.md` lines 17–18 and 30–50.  
   **Failure/attack scenario:** the landed `verify_ingress_scheduler_context()` is intentionally inert and verifies a supplied candidate, while `DirectRunner`/`slot_queue.acquire()` has no authenticated path by which the switchboard's minted context reaches it. If the implementation preserves the listed inventory, gate-ON direct dispatch supplies `None` and becomes deny-all. If an implementer makes the feature usable by accepting JSON, an environment value, a CLI argument, or an ordinary same-user file, a compromised owner/agent-UID process can inject or replay an authority-bearing context, contradicting “not the shell caller.” The rev3 inventory authorizes only `dispatch.py`/`slot_queue.py` edits and names no distinct principal, private service-to-service channel, or sole lifecycle writer capable of closing this seam.  
   **Required revision:** freeze an exact trusted carrier/gateway boundary: dedicated principal and private authority-client memberships, caller-untrusted submission contract, authoritative acquisition/storage of the context, and an end-to-end test proving the caller cannot supply or replace it while a valid context reaches the live runner.

2. **HIGH — The stale-lease proof has an unclosed epoch-bump race at the provider boundary.**  
   **Location:** `C6-DESIGN-AND-AUTHORIZATION.md` §2.2 lines 189–196 and §3.2 lines 230–240; `DESIGN-PACKET.md` §2 lines 66–70 and §9 lines 216–220; corroborating integration evidence in `C6-B3-LIVE-SEAM-RECONCILIATION-20260808.md` lines 19–23 and 75–101.  
   **Failure/attack scenario:** rev3 requires rereads during queue wake/tick and “immediately before dispatch execution,” but it defines neither an execution-start linearization point nor an atomic transition shared by the held reservation and provider launch. An epoch can advance after `slot_queue.acquire()` performs its last check and returns but before `DirectRunner` starts provider I/O. The stale reservation then reaches execution despite the bump. The earlier C2 admission check cannot close this later scheduler-to-provider TOCTOU. This violates F3 proof obligation (3), `stale-lease-can't-revive-after-epoch`.  
   **Required revision:** specify and inventory a `pre_execute`/launch-authorization fence at the actual provider boundary, with an authoritative epoch reread, task/context/expiry verification, single-use launch authorization, and a durable linearization point. A bump before that point must prevent provider I/O; a bump after it must be reported truthfully as already starting/running.

3. **HIGH — The revision-3 baseline cannot be reproduced or hash-bound as written.**  
   **Location:** `C6-DESIGN-AND-AUTHORIZATION.md` front matter line 9, revision-3 table lines 49–73, normative §1 lines 112–143, and freeze requirements lines 306–312.  
   **Failure/attack scenario:** declared `base_head=e7bf91deb4693a6667cd3c3ed10b0988b4143ef6` contains the rev2 hashes and does not contain the C6-P0 anchors. The abbreviated rev3 hashes instead match the later post-C2-SCI tree at `4687d7200df9d5751bb8b4ae76d5330f6a944ef3`. Meanwhile normative §1 still binds the old full hashes and declares the now-landed schemas/issuer surfaces absent. A freeze verifier can therefore either honor `base_head` and omit the claimed prerequisites, or honor the abbreviated table and disregard the packet's exact baseline; it cannot satisfy both. At review time, `HEAD=6d2a624cfbddd4f668e60eaa8d17dfd1340e711a` also differs materially, so the packet's own stop-on-drift rule applies.  
   **Required revision:** re-anchor to one exact commit; replace the normative table with full SHA-256 values; reconcile every NEW/EDIT/verify-only path; bind the accepted C2-SCI commit plus owner and scheduler signer allowlist hashes/revisions; and remove the superseded rev2 blocker/record text.

4. **MEDIUM — The operator kill lever has no frozen, authorized path from placeholder owner key to usable authority.**  
   **Location:** `C6-DESIGN-AND-AUTHORIZATION.md` §2.1 lines 155–172, §4 lines 242–273, and §6 lines 306–330; `C6-P0-TRUST-ANCHORS-REV3-20260806.md` §3 lines 53–61.  
   **Failure/attack scenario:** the rev3 baseline owner allowlist contains active key `owner-2026-08` with an all-zero public key. That fails closed, but it also makes every genuine bump impossible. P0 requires any key revision change to receive a new hash-bound design/review/owner authorization, while C6 declares the anchor verify-only and its implementation inventory does not authorize a provisioning edit or bind a private-key custody/rotation ceremony. The result can ship observably “healthy” code with no usable intervention lever, or invite an out-of-scope key replacement during activation.  
   **Required revision:** make real owner-key provisioning/rotation a named prerequisite with exact authorized files, custody path, allowlist revision/hash, negative tests, rollback/recovery behavior, and dashboard state that distinguishes placeholder/unprovisioned from operational.

5. **MEDIUM — The claimed single durable bump transaction has an unhandled crash window between epoch commit and replay receipt.**  
   **Location:** `C6-DESIGN-AND-AUTHORIZATION.md` §2.2 lines 174–187 and test requirements lines 275–290.  
   **Failure/attack scenario:** the design replaces and directory-fsyncs `epoch` before it records the replay/idempotency receipt. A crash in that interval leaves the new epoch durable but no receipt. Retrying the identical signed request then sees `expected_epoch != durable state` and cannot return the committed result; audit reconciliation also lacks the promised durable receipt. This is fail-safe for privilege but contradicts “single durable transaction,” breaks idempotent operator recovery, and creates an unobservable committed bump.  
   **Required revision:** define a recoverable journal/state-machine transaction (or one atomic authoritative record) whose recovery deterministically reconstructs the committed receipt, and add crash-injection vectors for every persistence boundary.

## Gate decision

These are binding defects, not advisory polish. Findings 1 and 2 prevent the design from proving the live scheduler seam and F3 stale-lease invariant; finding 3 prevents a deterministic freeze; finding 4 prevents demonstrated intervenability; and finding 5 leaves the authority transaction/recovery contract internally incomplete. Revision 3 is therefore **not freeze-eligible**. A corrected revision requires a fresh independent binding review before any freeze or single-use owner activation.

VERDICT: REQUEST_REVISION — define the trusted C2-SCI-to-runner carrier and provider-boundary linearization fence; re-anchor exact bytes; bind usable owner-key provisioning; and make bump commit/receipt recovery atomic
