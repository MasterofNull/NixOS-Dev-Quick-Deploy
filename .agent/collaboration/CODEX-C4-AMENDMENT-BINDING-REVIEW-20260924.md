---
title: "Independent Binding Review — [AMEND-C4] C6-lever prerequisite narrowing"
subject_branch: "factory/c4-amendment"
subject_commit: "2e733335b22a93df9d7b3c58068421c58273ab4e"
baseline: "main f1f409ef97f73fb6ae152a297ba0c0367e30bf22"
reviewer_role: "INDEPENDENT binding reviewer (did NOT author the amendment; adversarial read)"
review_date: "2026-09-25"
diff_digest_verified: "6bf05453bfad0cb9df9157e1e0f7f137ae17c0ea182a76fc1fe86c61cf3be330"
disposition: "ACCEPT (amendment may be promoted at C4 freeze)"
---

# Independent Binding Review — [AMEND-C4]

**Subject:** `factory/c4-amendment` @ `2e733335b22a93df9d7b3c58068421c58273ab4e`
**Baseline:** main `f1f409ef`
**Role:** INDEPENDENT binding reviewer — I did not author this amendment; reviewed adversarially, READ-ONLY.
**Disposition: ACCEPT (amendment may be promoted at C4 freeze).**

## Reproduced diff digest
`command git diff f1f409ef..factory/c4-amendment | sha256sum`
= `6bf05453bfad0cb9df9157e1e0f7f137ae17c0ea182a76fc1fe86c61cf3be330` — **MATCHES** the requested digest. No subject drift. Two files, +161/-4: `C4-DESIGN-AND-AUTHORIZATION.md` (+117/-4) and `C4-ACTIVATION-READINESS-20260806.md` (+48).

## Assessment

The amendment narrows C4's freeze prerequisite from the generic "C6 accepted+activated intervention lever" (whose full-lever referent — durable epoch authority + F2.5 scheduler gate + `authorize_launch` — lived in `C6-DESIGN-AND-AUTHORIZATION.md`) down to **"an operational, owner-authorized, signed epoch-bump path = C6d + C6c + C6-S,"** and binds C4's own epoch-recheck/channel-teardown (§4:140-144) as the revocability enforcement. I verified every citation against HEAD `f1f409ef`, confirmed the three lever slices actually constitute a signed epoch-bump path, confirmed the C6a exclusion, and stress-tested the revocation chain for a gap where widened egress could remain open after a bump. The narrowing is **logically sound** and the conservative PENDING posture is faithfully implemented.

**Ground-truth verification (all PASS):**
- Original ratified sentences quoted by the amendment exist verbatim at HEAD: `predecessors:12` ("C6: accepted, activated intervention lever is mandatory before C4 flag-on"); §4:143 ("C6's accepted intervention lever is a required activation prerequisite…"); §8:218 ("reviewed/activated intervention evidence must be replaced…"); §9:276 ("accepted/activated C6 intervention lever"); readiness §1 row2, §3, §4 step1.
- The C4 teardown behavior the amendment binds genuinely exists at HEAD, §4 **line 140**: "The broker closes active channels, invalidates/makes unavailable their UDS endpoints, and requests affected-cell termination on epoch bump, grant expiry, policy/catalog loss, cell death, peer mismatch, flag-off, or rollback." Quoted accurately.
- **Discrepancy note (A.1) is accurate.** `grep -iE 'f2\.5|authorize_launch|scheduler gate'` over BOTH C4 docs at HEAD returns **nothing** — the C4 text never literally names the F2.5 gate or `authorize_launch`; it uses the generic "C6 intervention lever." The decomposition §7.1's claim that C4 "defines the lever as … plus the live F2.5 scheduler gate" refers to the referent inherited from `C6-DESIGN:86-90,221-236`, not to wording present in C4. The amendment amends the *referent*, not absent text — a fair, verified representation.
- The three lever slices confirm the "signed epoch-bump path" claim: **C6d** (`factory/c6d-design-v2`) = durable, crash-safe, recover-before-listen revocation-epoch authority; **C6c** (`factory/c6c-design-v3`) = a callable `submit --signed --socket` verb delivering a pre-signed `{"bump":…}` to the RUNNING authority over the C6-S control socket with no host private key and no owner-UID 0700 write (the authority already accepts `{"bump":…}` and applies it under `epoch.lock`); **C6-S** (`factory/c6s-design-v2`) = the frozen two-socket topology + control-socket owner-bump path both consume. Together these are an operational owner-authorized signed epoch-bump path.
- **C6a exclusion is correct.** `factory/c6a-design-v2` §0 states C6a is "NOT part of the operator kill-lever … its only consumer is the TEG (C6b)"; its op is reachable only over the launch socket, which has no admissible client until C6b provisions the TEG UID, and the TEG SO_PEERCRED check fails closed until then. `authorize_launch` is a launch fence, not a revocation mechanism — it cannot close an already-open C4 UDS channel.
- **rev5 Finding 5** (`CODEX-C6-REV5-BINDING-REVIEW-20260924.md:31-33`) reads exactly as cited ("a URL/environment value is a routing target, not an OS network boundary"); the amendment's A.5 reaffirmation is faithful.

## Findings

**Finding 1 — MEDIUM — "operational" is not explicitly bound to an ACTIVE owner public key (P-F4).**
`C4-DESIGN-AND-AUTHORIZATION.md:§0.A A.2/A.6` and readiness `§0.A`/`§4 step1` gate C4-freeze-eligibility on the lever being "operational." C6c's own front matter (`factory/c6c-design-v3`) is explicit that the DESIGN/BUILD lands **dormant** and that an ACTIVE owner key requires a **separate later act — P-F4** (owner offline keygen + monotonic public-allowlist advance rev-4→rev-5); until P-F4, "the lever is observably none(revoked-only)."
**Concrete scenario:** if a future builder reads "operational" as "C6c code path built," C4 egress could be activated while the owner allowlist is still `revoked`-only — the owner could produce an offline signature but the authority would reject it, so the owner has **no accepted bump to trigger C4's teardown**, and widened UDS egress would not be owner-revocable in practice. This is the one place the letter of the narrowed prerequisite could be satisfied while the soundness argument (C4 teardown reacts to an owner bump) is hollow.
**Why non-blocking:** the amendment consistently says "operational **AND** owner-authorized," A.6 separates acceptance from activation, and C6c binds P-F4 as the activation event — a careful reader gets it, and the C4 freeze re-anchors exact hashes/evidence. **Recommendation (bind at C4 freeze, not a promotion blocker):** the C4 freeze must record P-F4 evidence (an active owner public key present in the allowlist) as part of "operational," so the prerequisite cannot be gamed by a built-but-keyless lever (anti-gaming / Rule 19).

**Finding 2 — LOW (informational) — epoch-bump→teardown propagation latency is a C4-build concern, not opened by this amendment.**
The amendment binds "C4's own epoch-recheck + channel-teardown" as enforcement but (correctly, being design-only) does not specify how a bump at the C6d authority propagates to the C4 broker (poll vs. push) or the max window before an already-open long-lived channel is torn down. `C4-DESIGN §4:140` specifies active teardown "on epoch bump" (not merely lazy next-frame re-check), and §7 rollback + §6 Service-Coverage gate 3 (failed-teardown alert) + the "prove zero active channels within a frozen numeric teardown budget" requirement already bound this at C4 build. No gap the amendment introduces; flagged only so the C4 build validates the bump→teardown latency against that teardown budget.

## Explicit sub-verdicts

- **(a) Narrowed-prereq soundness: SOUND.** C6d+C6c+C6-S is a genuine operational owner-authorized signed epoch-bump path; C4's own §4:140-144 teardown, driven by that bump, is what revokes the widened egress. Neither the F2.5 scheduler gate (dispatch/backpressure, not revocation) nor `authorize_launch` (a TEG launch fence with no power over an open C4 UDS channel) is required to make C4 egress revocable. No revocation-path gap found (subject to Finding 1's P-F4 clarification).
- **(b) C6a exclusion: CORRECT.** `authorize_launch`'s only consumer is C6b/TEG; nothing in C4's teardown trigger set (epoch bump, expiry, policy loss, cell death, peer mismatch, flag-off, rollback) depends on it. Sharing `epoch.lock` machinery does not make it part of the kill-lever.
- **(c) Egress hard gate: PRESERVED.** A.5 reaffirms rev5 Finding 5 faithfully — no interim netns/nftables/proxy escape hatch is pre-authorized; C4 (`bwrap --unshare-net`, no AF_INET/AF_INET6, receiver-scoped UDS) remains the HARD pre-activation gate for TEG egress (C6e). Not relaxed.
- **(d) Sequencing: COHERENT.** Matches decomposition §8 (`C6d → C6-S → {C6a ∥ C6c} → [AMEND-C4] → C4 → C6b → C6e`); C4 freeze-eligible only after acceptance AND an operational lever; C6b→C6e stays after C4; rev5 §6 supersession valid only once accepted and only for TEG-egress activation, never for the kill-lever. No cycle — C4-freeze deps {C6d, C6-S, C6c, accepted [AMEND-C4]}, none of which depend on C4.
- **(e) PENDING posture + discrepancy note: ACCEPTABLE and ACCURATE.** Original ratified sentences are left verbatim; the new wording is added only as a §0.A block plus additive inline `[AMEND-C4 PENDING]` markers, so acceptance (this review) is what promotes it at freeze — unambiguous. The A.1 discrepancy note is verified true against HEAD: the C4 docs do not literally name the F2.5 gate/`authorize_launch`; the amendment narrows the inherited referent rather than striking absent wording.

VERDICT: ACCEPT (amendment may be promoted at C4 freeze)
