# C6a Design Rev2 — Independent Binding Re-Review (Focused)

**Subject:** branch `factory/c6a-design-v2` commit `fbf5608d`, file
`.agents/plans/aqos-foundation-c/C6a-DESIGN-AND-AUTHORIZATION.md`
**Baseline:** `main` `f1f409ef`
**Role:** independent binding reviewer (read-only re-review of a focused revision)

**Disposition: FREEZE-ELIGIBLE**

---

## Requested diff digest

```
command git diff f1f409ef..factory/c6a-design-v2 | sha256sum
a963311d1b1cad685cdc6bb20dbd85433e404baaf760777e7427ad0bb266303d
```
Matches the required digest exactly. No subject-drift.

---

## Per-fix closure

### F1 — §5.2 recovery argument reframed off timing — **CLOSED**

Verified against `factory/c6a-design-v2:...C6a-DESIGN-AND-AUTHORIZATION.md` §5.2 (lines 356–416 of the
extracted file):

- The prior recovery-timing claim ("no crash-plus-restart... completes in under 250 ms") is explicitly
  named and rejected (`§5.2`, "That timing claim is **not safe to hang correctness on**... a warm
  restart... can plausibly complete in well under 250 ms").
- Correctness is now grounded solely in `recover_launch_ledger()` **unconditionally** sweeping every
  surviving `issued`-without-`consumed` record to terminal `expired`, "before any socket accepts,"
  independent of elapsed time.
- A **BINDING build requirement** is added: the expiry transition "MUST NOT be conditioned on
  re-checking `issued_at + deadline_ms`, current wall-clock time, or any other elapsed-time
  computation" — a build that guards the sweep behind an elapsed-time recheck "does not satisfy this
  design."
- The ≤250 ms deadline is explicitly demoted to "a live-path freshness bound... not a recovery-safety
  assumption," and stated to play "no role in why recovery is safe."
- **Downstream consume-denial rename verified consistent, not contradictory.** Post-sweep, the record's
  `issued/<nonce>` no longer exists (it is `O_EXCL`-created into `expired/<nonce>` then `unlink`ed).
  §3.2 step 2's verifier order ("`issued/<nonce>` exists — else `DENY_LAUNCH_UNKNOWN` (no such token, or
  already reaped)") is checked **before** step 4 (expiry). A post-sweep `consume_launch` therefore hits
  step 2 first and denies `DENY_LAUNCH_UNKNOWN`, exactly as rev2 claims — the state machine's own
  ordering (verifier steps 1–5, §3.2) makes this the correct denial, not `DENY_LAUNCH_EXPIRED`. No
  contradiction elsewhere: the §3.3 state diagram's `expired` terminal state is reached via two
  independent paths (live-path deadline-elapse *or* crash-survived unconditional sweep) that land on the
  same terminal state without conflicting.
- No residual load-bearing timing claim found anywhere else in the document (`grep` for the retired
  phrasing — "no crash-plus-restart," "necessarily in the past," "completes in under 250" — only occurs
  inside the passage that names and rejects the old claim; §9 item 6 restates the same
  unconditional/freshness-bound framing coherently).

### F2 — §5.3 C6d composition freeze-time check — **CLOSED**

§5.3 (lines 426–444) adds a clearly labeled "**BINDING freeze-time verification requirement**" stating
the freeze "MUST NOT accept this on design prose alone" and must verify, against C6d's **landed**
`__main__` (not this design's description), that C6a's insertion is purely additive:
- exactly one sibling call (`recover_launch_ledger()`) inside the single `epoch.lock` hold, strictly
  after `recover()` returns and strictly before `serve_multi()` binds/`listen()`s either socket;
- no alteration to C6d's `recover()` body, journal, the two uniqueness indexes
  (by-request-id/by-idempotency-key), `Type=notify`, or the readiness gate;
- no alteration to `apply_bump`/`build_env_handler` signatures.

This exactly matches the requested fix. It is also restated in §9 freeze criterion 6 (lines 580–590),
so it is load-bearing at the freeze gate, not merely descriptive.

### F3 / F4 — §2.3 uid-only correction + C6b forward-condition — **CLOSED**

- **F3:** §2.3's opening MUST statement is corrected to "verifying the connecting peer's **uid** is the
  TEG principal," with an explicit parenthetical: "(Wording corrected to **uid-only** — the mechanism
  in item 2 below has never compared gid; consistent with C6-S §7.8's own uid-only formulation of this
  MUST.)" Item 2 is likewise corrected ("Verifies **uid** is the TEG principal... The check is
  **uid-only** (there is no gid comparison anywhere in this mechanism...)"). Freeze criterion §9 item 4
  matches ("uid-only... no gid comparison"). The one remaining `gid` token in the document (line 152,
  `peer_creds` is `(pid, uid, gid)`) is a factual description of the tuple `get_peer_credentials()`
  returns, not a claim that gid is compared — consistent, not contradictory.
- **F4:** a new item 5 in §2.3 (lines 173–181) states the BINDING forward-condition: "the TEG uid MUST
  be distinct from the authority-user uid," with the reopened-self-launch consequence spelled out if
  violated, and "C6b's freeze must verify `AQ_REVOCATION_LAUNCH_TEG_UID != <aq-revocation-epoch-authority
  uid>` before that value is provisioned live." Restated in §9 item 4 (lines 573–577) as a
  forward-condition C6b inherits. Both present and binding.

### F6 — §1 ledger tmpfiles anchor `:126`→`:125` — **CLOSED**

§1 now cites `:125` for the existing `ledger/` tmpfiles rule. Verified against HEAD:
`command git show f1f409ef:nix/modules/services/revocation-epoch-authority.nix` — the
`"d ${cfg.statePath}/ledger 0700 ..."` rule is at line **125** (confirmed via `grep -n`). The design's
other citations in the same row (`statePath` default at `:84`, `Environment` block at `:146-152`,
hardening flags at `:159`/`:161`/`:166`) were independently spot-checked against the same HEAD file and
all match exactly.

### F5 — untouched, as expected

No diff hunk touches the per-token vs. per-binding single-use framing; confirmed absent from the
rev1→rev2 diff.

---

## Regression check

`command git diff --stat factory/c6a-design..factory/c6a-design-v2` → **133 insertions(+), 45
deletions(-)**, matching the digest given in the task exactly. Full diff reviewed line-by-line: every
hunk falls inside frontmatter (`revision: 1`→`2`), §1 row 3 (anchor only), §2.3, §5.2, §5.3, §6/§9
restatement lines, and the closing RECORD/Revision-2-changelog block. No hunk touches §3 (token fields,
verifier, atomic consume, exactly-once proof), §4 (same-`epoch.lock` total-ordering proof), §7
(exclusions), or §8 (Service-Coverage inventory) — the single-use consume mechanism, exactly-once proof,
same-epoch.lock ordering, and topology are all textually unchanged and therefore intact. `PREPARED_ONLY`
marker preserved (closing RECORD line: "PREPARED_ONLY revision 2... No implementation, freeze,
activation, epoch bump, provider traffic, deployment, restart, network authority, or flag flip is
granted"). §1 anchors otherwise unchanged (not re-verified individually per task scope, since prior
review already did so and this revision touches only the one cited anchor). §9 freeze criteria updated
coherently with §2.3/§5.3 (items 4 and 6 restated to match, no orphaned or contradictory criterion
found).

---

## Findings

None. No new HIGH/MEDIUM/LOW findings raised in this focused re-review.

---

**VERDICT: FREEZE-ELIGIBLE**
