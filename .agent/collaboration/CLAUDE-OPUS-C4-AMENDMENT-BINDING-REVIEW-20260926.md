# [AMEND-C4] Amendment — Independent Binding Review (Claude Opus 4.8)

- **Date:** 2026-09-26
- **Reviewer:** Claude Opus 4.8 (INDEPENDENT binding lane)
- **Lane substitution (Rule 18):** Codex was the assigned binding reviewer but hit its usage
  limit. Per Rule 18 (agent-agnostic roles — route to the next eligible lane, record the
  substitution, never block) this review is issued by the Claude flagship lane as the substitute
  binding reviewer. **Codex confirmatory review remains QUEUED** for its return (advisory unless it
  surfaces a real defect → bounded follow-up). Substitution recorded here.
- **Baseline:** `origin/main` @ `4fa4e0f3b89ce0e0eee86e1f59ffa932ce11c2ef`
- **Prior status of subject:** `PREPARED_ONLY — NOT accepted`. An earlier Claude ACCEPT was
  written but never committed → not authoritative; this committed record supersedes it.

## Subject (byte-bound)

`.agents/plans/aqos-foundation-c/C4-DESIGN-AND-AUTHORIZATION.md` — the **§0.A AMENDMENT [AMEND-C4]**
block (landed PROPOSED via commit `2e733335` / PR #341).

```
subject: .agents/plans/aqos-foundation-c/C4-DESIGN-AND-AUTHORIZATION.md @ origin/main
sha256:  421cc2a272f32817fa24777c1ed181189da2482a5cb02245f0f60f2db99ce392
command: git show origin/main:.agents/plans/aqos-foundation-c/C4-DESIGN-AND-AUTHORIZATION.md | sha256sum
```

Worktree copy verified byte-identical to `origin/main` (same sha256) at review time.

## Verification of the referenced merged slices

All three prerequisite slices exist on `origin/main` and their **implementations are merged and not
reverted**:

- **C6d** — impl PR #344 (`22c0c19b feat(c6d): implement deterministic journal recovery…`,
  `4c6db070 fix(c6d): persist + reconcile audit_pending…`). Design `C6d-DESIGN-AND-AUTHORIZATION.md`
  (recover-before-listen barrier; durable, recoverable revocation epoch).
- **C6-S** — impl PR #345 (`6b289376 feat(c6-s): dedicated TEG-only launch socket + principal
  topology (mechanism B)`). Froze the two-socket topology + the control-socket owner-bump path.
- **C6c** — impl PR #347 (`3edaca3a feat(c6c): callable offline owner-key submission path over
  control socket (dormant)`). `submit --signed --socket` → `revocation_epoch_transport.send_request`
  → authority applies the verified bump under `epoch.lock` (no host private key, no owner-UID `0700`
  write; C6c design §mechanism + ground-truth citations `revocation_epoch.py:609-615`,
  `apply_bump` re-checks `status=="active"` every call at `:407`).

Note on tier: the three slice **design docs remain `PREPARED_ONLY`** and the lever is **dormant
(`none(revoked-only)`) until P-F4** (owner offline keygen + allowlist rev-4→rev-5 adding an active
key). This is consistent with the amendment, which makes the *operational* lever a **freeze
prerequisite** — it does not claim the lever is already operational.

## Per-item verdicts

### 1. Narrowed prerequisite = C6d + C6c + C6-S, with F2.5 gate + authorize_launch REMOVED — CONFIRMED
- Amendment A.2 (`C4-…md:60-73`) states the prerequisite **precisely** as C6d + C6c + C6-S and
  explicitly **REMOVES** the F2.5 scheduler gate and `authorize_launch` (C6a).
- The three merged slices genuinely constitute an operational owner-authorized signed epoch-bump
  path: C6d (durable/recoverable epoch authority) + C6-S (control-socket owner-bump topology) + C6c
  (callable owner-signed submission over that socket → `apply_bump` under `epoch.lock`).
- Corroborated by `C6-DECOMPOSITION-20260924.md:112` ("does **NOT** include **C6a**") and §7.2 item 3.
- **CONFIRMED.**

### 2. C4's own epoch-recheck + channel-teardown = the revocability enforcement — CONFIRMED (with citation defect → item R)
- The teardown behavior exists verbatim at **`C4-…md:237-241`**: *"The broker closes active
  channels, invalidates/makes unavailable their UDS endpoints, and requests affected-cell
  termination on epoch bump, grant expiry, policy/catalog loss, …"*
- Amendment A.4 (`C4-…md:83-91`) binds this explicitly: on an owner epoch bump via the C6d+C6c(+C6-S)
  lever, **C4's own teardown** is what revokes the widened egress — not `authorize_launch`, not the
  F2.5 gate. The logical bridge is sound: revocability lives in C4's teardown reacting to the bump.
- **Behavior CONFIRMED.** Defect: A.4 cites this text as "§4 (lines 140-144)"; in the committed
  bytes lines 140-144 are the **§1 profile table**, and the quoted text is at 237-241 (see item R).

### 3. C6a (authorize_launch) correctly EXCLUDED — CONFIRMED
- Amendment A.3 (`C4-…md:75-81`): C6a is NOT part of the C4 kill-lever; its only consumer is the TEG
  dispatch gateway (C6b); a launch-authorization op with no live consumer cannot revoke a C4 channel.
- Corroborated by `C6a-DESIGN-AND-AUTHORIZATION.md:16,33-34` ("its only consumer is the TEG (C6b)…
  C6a is NOT part of the C4 kill-lever") and `C6-DECOMPOSITION-20260924.md:112`.
- Nothing in C4's revocation path (§4 teardown / epoch recheck) depends on `authorize_launch`.
- **CONFIRMED.**

### 4. Egress stays a HARD pre-activation gate (no interim netns/nftables escape hatch) — CONFIRMED
- Amendment A.5 (`C4-…md:93-102`) reaffirms: no interim netns/nftables/proxy escape hatch is
  pre-authorized; any future interim egress boundary needs its own reviewed exact mechanism.
- C4 body keeps the hard gate: every cell retains `bwrap --unshare-net` (§0 `:128`), broker/gateways
  are `AF_UNIX`-only with no AF_INET/AF_INET6 (§5 `:250-257`), and no C4 component may resolve or
  connect AF_INET/AF_INET6 (§3 `:208-209`).
- **CONFIRMED.**

### 5. MEDIUM — is "operational" tied to an ACTIVE owner key (P-F4)? — CONFIRMED (adequately bound)
- The concern: a builder must not read "operational" and activate C4 egress while there is no
  accepted bump path (no active key) → non-revocable egress.
- **Bound at two layers.** (a) Amendment A.2 (`:62`) defines the prerequisite as *"an **operational,
  owner-authorized, signed** epoch-bump path"* — all three qualifiers exclude the zero-active-key
  state. (b) The named slice C6c makes it machine-observable: `C6c-…md:331` defines **`operational`**
  = allowlist readable AND ≥1 `status:"active"` owner key AND the verb present AND the authority
  `read-epoch` probe succeeds; the pre-P-F4 / revoked-only condition is the **distinct**
  `none(revoked-only)` state (`C6c-…md:342-344`). A builder therefore literally cannot observe
  "operational" with zero active keys.
- Defense-in-depth: C4 egress **activation** is separately owner-gated regardless of freeze
  eligibility (frontmatter `activation_authorization: "NONE"`; §7 `:307-312` single-use owner build
  activation + separate owner canary). Freeze-eligibility ≠ egress-on.
- **CONFIRMED — adequately bound.** Residual **advisory (freeze-time, non-blocking):** when the
  `[AMEND-C4 PENDING]` markers are superseded at freeze, the replacement text must preserve the full
  *"operational, owner-authorized, signed epoch-bump path"* qualifier (ideally citing C6c §6's
  `operational` definition) so the active-key binding survives into final C4 text and "operational"
  is never degraded to "authority unit merely enabled."

### R. Citation-integrity defect (the sole blocker) — OPEN
The amendment's own internal line-number cross-references point to **pre-insertion geometry**
(base_head `f1f409ef`, before the ~90-line §0.A block was prepended) and now resolve to unrelated
content in the byte-bound file (sha `421cc2a2`). The `[AMEND-C4 PENDING]` markers are self-
identifying by text, so this is mechanically recoverable — but `supersedes_on_acceptance` is the
**load-bearing instruction for which sentences get replaced at freeze acceptance**, and in an
enforcement-tier prerequisite a wrong anchor is a real trap.

Actual marker locations vs. cited (committed file):

| Cited in doc | Amendment says | Resolves NOW to | Correct location |
|---|---|---|---|
| frontmatter `supersedes_on_acceptance:26` predecessors | `predecessors:12` | line 12 (correct) | 12 ✓ |
| same, §4 | `§4:143-144` | §1 profile-table header/divider | §4 marker at **242-246** |
| same, §7 | `§7:191-198` | §2/§3 boundary text | §7 marker at **302-305** |
| same, §8 | `§8:217-219` | blank / §4 header | §8 marker at **327-330** |
| same, §9 | `§9:276` | §6 text | §9 marker at **387-389** |
| A.4 body `:85` | "§4 (lines 140-144)" | §1 profile table | teardown text at **237-241** |

**Fix (mechanical, no substantive change):** update the frontmatter `supersedes_on_acceptance`
anchors (§4/§7/§8/§9) and A.4's "§4 (lines 140-144)" / "§4:143-144" to the committed-file line
numbers above. Narrowing logic, C6a exclusion, hard-gate reaffirmation, and operational/active-key
binding all remain unchanged.

## Validation gates run

- `scripts/governance/tier0-validation-gate.sh --pre-commit` → **PASS** (exit 0). **Passed: 53,
  Failed: 0.** Included: check-canon-drift (in sync), check-pm-tracker (14 trackers valid), check-
  deleted-links (no deletions), check-config-contracts, check-sops-sync (13 required, 0 stale),
  check-shallow-repo (not shallow), check-suspend-resume-contract.
- Subject is a design/plan Markdown doc (no code diff) → gitleaks/semgrep/focused-CI code scans are
  N/A to the subject bytes; doc-metadata/structure covered by the tier0 doc/link/canon checks above.

## Summary

Substantive checks 1–5 are all CONFIRMED; the MEDIUM (item 5) is adequately bound by A.2's three-part
qualifier + C6c §6's machine-observable `operational` state + the separate owner activation gate. The
**only** blocker is a systematic stale internal line-citation defect (item R) in the enforcement-
critical `supersedes_on_acceptance` instruction and the A.4 body — a mechanical fix requiring no
change to the narrowing logic. Codex confirmatory review remains queued (substitution recorded).

VERDICT: REQUEST_REVISION — correct the stale internal line-citations (frontmatter `supersedes_on_acceptance` §4/§7/§8/§9 anchors and A.4's "§4 lines 140-144") to the committed-file geometry (§4 teardown 237-241; PENDING markers at 242-246 / 302-305 / 327-330 / 387-389). All five substantive checks (1-5) are CONFIRMED and the narrowing logic is sound; this is the sole blocker to promotion at C4 freeze.
