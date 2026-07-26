# C2 Amendment (first-party/built-in tool lease source) — Independent Confirmatory RE-REVIEW (Opus)

**Reviewer:** claude-opus-c2-amendment-rereviewer (independent — did NOT author the amendment;
author is fable-5; I am NOT codex, who ran the prior REQUEST_REVISION). Anti-gaming stance:
verify the rev2 text actually closes codex-1..4 and introduces no new fail-open — not that it
*claims* to. A REVISE→PASS is not rubber-stamped.
**Reviewed record:** `.agents/plans/aqos-foundation-c/C2-AMENDMENT-BUILTIN-TOOLS.md` (rev2).
**Prior review folded:** `C2-AMENDMENT-REVIEW-CODEX.md` (REQUEST_REVISION — codex-1 epoch/revoke,
codex-2 bidirectional equality, codex-3 bound risk metadata, codex-4 first-party DEV-key test).
**Grounded against:** frozen `C2-DESIGN-AND-AUTHORIZATION.md`; prior `C2-REVIEW-OPUS.md` +
`C2-REREVIEW-OPUS.md` (B1 chokepoint / B2 DEV-key fail-opens); `scripts/ai/lib/capability_lease.py`
(`verify` L272, `canonical_payload` L160, `resolve_key` L181, `epoch_stale` L228).

---

## VERDICT: REVISE

Three of codex's four findings (codex-2, codex-3, codex-4) are **genuinely closed** in rev2, and
the composed enforcement (bound metadata + manifest equality + strip + epoch + deny-closed + DEV-key
degrade) is subtractive with **no new additive admit path**. But **codex-1 is NOT fully closed at
the text level**: the amendment added the correct "revocation is not self-healing / deliberate
re-issue only" invariant yet **left the contradicting sentence in place** — the record still
literally instructs the implementer to re-issue the first-party lease *on epoch bump*, which is the
exact self-healing revocation codex-1 required the record to make unambiguous. A frozen, hash-bound,
implementer-facing design record must not contain a load-bearing contradiction on the
revocation-critical path. One-line fix; then re-freeze.

---

## codex-1 — Epoch reissuance vs revocation: **NOT CLOSED (residual internal contradiction)**

**Where:** `C2-AMENDMENT-BUILTIN-TOOLS.md:32` **versus** the rev2 invariant at **:39–44** and the
codex-1 fold at **:55–57**.

- **:32** (unchanged from rev1): "The first-party lease is issued at startup by the signer from the
  manifest **(long-TTL, re-issued on epoch bump)**."
- **:39–44** (rev2 invariant): "revocation is NOT self-healing … **First-party leases are NOT
  auto-reissued per-request** — reissuance is a deliberate act (startup, or an explicit re-issue
  after the operator clears the bump). So bumping the epoch actually REVOKES `run_command`
  fleet-wide until deliberate re-issue; **automatic … reissuance would defeat revocation and is
  forbidden**."

These directly contradict each other. "re-issued on epoch bump" makes the epoch-bump event the
*trigger* for reissuance — a fresh current-epoch lease is minted the moment the epoch bumps, so
`verify`'s `epoch_stale` check (`capability_lease.py:228/290`) passes again and `run_command` is
immediately re-admitted. That is precisely the revocation-self-heal codex-1 (codex B3) flagged and
demanded be eliminated, and it is exactly what the rev2 invariant forbids. The amendment fixed the
invariant but did not remove the sentence that states the forbidden behavior.

This is not stale phrasing to wave through: the record is a freeze candidate handed to the
cheapest-eligible implementer, and codex-1 explicitly required the "deliberate re-issue only" rule
to be **unambiguous**. As written, an implementer following :32 would wire reissue-on-bump and
reintroduce the fail-open; an implementer following :39–44 would not. The record cannot be frozen
with both statements live.

**Concrete fix (one line):** rewrite :32 to remove the "re-issued on epoch bump" trigger and align
with the invariant, e.g. — *"The first-party lease is issued at startup by the signer from the
manifest (long-TTL). It is re-issued ONLY by a deliberate operator-controlled step (startup, or an
explicit re-issue after the operator clears the bump) — NEVER automatically as a side effect of an
epoch bump; an epoch bump leaves the tool revoked until that deliberate re-issue (see invariant
below)."* No other change needed; the invariant (:39–44) and the codex-1 fold (:55–57) and the
acceptance test (:78–79) are already correct and stay. Then re-freeze.

*(Assessment of the acceptance test itself: :78–79 is adequate — it drives admit → bump → stale →
DROPPED → **not** auto-reissued on the next request, matching codex's requested end-to-end
lifecycle test. The gap is purely the un-deleted contradictory prose, not the test.)*

---

## codex-2 — Bidirectional manifest↔`_TOOL_BUNDLES` equality: **CLOSED**

**Where:** rev2 fold :59–61; acceptance :81–82.

rev2 requires **EXACT set equality** between `config/first-party-tools.json` and the live
`_TOOL_BUNDLES` set, with **both** directions fail-closed: a bundle tool missing from the manifest
(silent-deny) AND a manifest tool absent from the bundles (privilege EXPANSION) both fail the check.
Acceptance tests both directions. This closes the load-bearing threat codex B4 raised — an extra
manifest entry can no longer promote a non-bundle registered tool (selectable via explicit request
or `"*"`) into the first-party lease source, because any manifest name not in `union(_TOOL_BUNDLES)`
fails closed. The one-way ⊆ weakness is gone. Prevents both silent-deny and privilege-expansion.
**Closed.** (Two of codex's belt-and-suspenders sub-points are not spelled out — see NICE-TO-HAVE
N-a; neither is a fail-open given exact equality against the bundle set.)

---

## codex-3 — Cryptographically bound per-tool risk metadata: **CLOSED**

**Where:** rev2 fold :62–68; acceptance :84–86.

rev2 embeds each tool's risk classification (`write_capable`, `network_capable`, `trust_tier`,
`zero_trust` category, `constraints`) **inside the SIGNED canonical payload**, and the gate reads the
classification **from the VERIFIED lease, never from the on-disk manifest at admission**;
schema-validate; **fail closed on any manifest/lease mismatch**; **tampering tests for EVERY
privileged category** (network / write / exec / secret / delegate), not only
`run_command`/`write_file`. This is technically sound against the primitive: `canonical_payload`
(`capability_lease.py:160`) signs every lease field except `signature`, and `permissions.constraints`
(plus `trust_tier` and `zero_trust_behavior`) are part of that signed payload — so risk fields placed
there are HMAC-bound and tamper-evident via `verify`. Mutating the mutable on-disk manifest cannot
change admission because the gate consults the signed lease. Fail-closed-on-mismatch is stated;
per-category tampering tests are required. This matches codex H1's requested fix. **Closed.**

## codex-4 — First-party DEV-key regression test: **CLOSED**

**Where:** rev2 fold :69–71; acceptance :87–88.

An explicit acceptance test now requires: a cryptographically valid first-party lease created **with
the DEV key** → enforcement enters the **safe-read degrade**, admitting **nothing** under the DEV
key. This is the anti-gaming guard for the new issuance path (a DEV-key first-party lease that
*would* "admit" is still dropped), and it mirrors the B2 posture the prior Opus re-review confirmed
sound. Matches codex H2. **Closed.**

---

## New fail-open introduced by the revision? — NONE beyond the codex-1 residue

I looked for any combination that admits a first-party tool while it should be denied:

- **Stripped + first-party:** :35–38 keeps `zero_trust_behavior: strip` biting first-party tools —
  `run_command`/`write_file` DROPPED under strip; only safe-reads survive. No strip-exemption. ✓
- **Epoch bump + first-party:** subtractive by the invariant (:39–44) — **provided :32 is
  corrected**. Uncorrected, :32 is the one path where an epoch bump self-heals (the codex-1 residue
  above). This is the sole admit-when-should-deny risk in the record. ✗ until :32 fixed.
- **DEV-key + first-party:** :46–47 + codex-4 test — DEV-key first-party lease hits the S4 safe-read
  degrade, never verified/admitted under the public DEV key. ✓
- **Absent from `_TOOL_BUNDLES` / absent from both sources:** deny-closed (:48–49) + exact-equality
  fail-closed (codex-2). No admit. ✓
- **Bound metadata × equality × strip × epoch × deny-closed compose cleanly:** every leg is
  subtractive or a fail-closed precondition — the admitted set is `deny-closed base ∩ per-tool
  signed-lease proof`, with degrade *replacing* the set by a fixed safe-read allowlist. No additive
  leg exists, so no two restrictions compose into an admit. The only residual assumption (safe-read
  allowlist contains no privileged tool) is pinned by the strip/degrade acceptance tests. ✓

## Governance / posture — sound and unchanged

`§Next` (:90–95) keeps C2 **PREPARED_ONLY**, requires a confirmatory re-review (this doc),
**re-freeze with a new subject hash**, single-use **owner activation**, and **flag-default-OFF**;
the prior freeze `313b723b` is explicitly superseded; ceiling grows 4→5 (adds
`config/first-party-tools.json`) which is the reasonable minimum for a first-party lease source. All
correct — no change requested here. Fixing codex-1 does not alter this posture; it precedes the
re-freeze.

---

## NICE-TO-HAVE (non-blocking; do not gate on these)

- **N-a — codex-2 belt-and-suspenders.** rev2 pins exact equality against `union(_TOOL_BUNDLES)`
  (sufficient for the fail-open). For reviewer/implementer determinism, the record could also state
  explicitly (a) whether the virtual `lease_tools` control name is included/excluded from the
  equality set, (b) reject duplicate manifest entries, and (c) require each manifest entry's
  `actions == [tool]`. None is a fail-open given the exact-equality check; all are hardening.
- **N-b — codex-3 field placement.** The base `CapabilityLease` schema has no top-level
  `write_capable`/`network_capable` fields; the implementer must carry them inside the signed
  `permissions.constraints` (and use the existing signed `trust_tier` / `zero_trust_behavior`), then
  schema-validate. Worth one sentence in the record so the "SIGNED canonical payload" binding is
  unambiguous at build time, but the design-level invariant is already correct.

---

## Bottom line

**REVISE — one blocking residue.** codex-2, codex-3, codex-4 are genuinely closed and the revision
introduces no new fail-open in any composition I could construct. The single remaining gap is
codex-1: the amendment added the correct non-self-healing revocation invariant (:39–44) but left the
directly-contradicting "re-issued on epoch bump" sentence at **:32**, so the record still, on its
face, tells the implementer to self-heal a revocation — the exact ambiguity codex-1 required removed.
Fix :32 to state deliberate-re-issue-only (never triggered by the epoch bump), consistent with the
invariant; re-run the acceptance intent (already correct); then this amendment is safe to fold into
**C2 rev3** and **re-freeze** (new subject hash) for single-use owner activation. C2 stays
PREPARED_ONLY / flag-default-OFF / owner-gated throughout.
