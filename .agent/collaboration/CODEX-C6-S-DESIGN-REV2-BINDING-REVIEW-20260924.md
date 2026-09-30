# Binding Re-Review — C6-S Design revision 2 (focused verification of three required fixes)

- **Subject:** `factory/c6s-design-v2` @ `51f349026913c5e9a45fc70514683376ec98319d`
- **File under review:** `.agents/plans/aqos-foundation-c/C6-S-DESIGN-AND-AUTHORIZATION.md`
- **Baseline:** main `f1f409ef97f73fb6ae152a297ba0c0367e30bf22`
- **Role:** INDEPENDENT binding reviewer, focused re-review of a prior REQUEST_REVISION (did not author either revision)
- **Disposition:** **FREEZE-ELIGIBLE**

## Reproduced diff digest

```
command git diff f1f409ef..factory/c6s-design-v2 | sha256sum
=> 9a43e8ab5cb402d2fe412a7a82128ed166676e1b1923ff99ba868c3aeb082bd4   [MATCHES requested digest]
```
`git diff --stat f1f409ef..factory/c6s-design-v2` confirms exactly one file changed (446 insertions, 0 deletions vs. baseline where the file does not yet exist) — no subject drift, no source-file drift.

`git diff --numstat factory/c6s-design..factory/c6s-design-v2` for the design doc: **90 insertions / 34 deletions**, matching the requested +90/−34.

## Per-fix closure

### Fix 1 (MEDIUM, security core) — exclusivity wording + binding forward-condition — **CLOSED**

- §2.3 (`v2:180-190`) replaces the imprecise v1 sentence ("the only consumer ever added to that group is the TEG") with a precise membership statement: the launch group's ever-added members are exactly **(a) the authority-user** — chgrp/server role, `:182-185`, cross-referenced to §2.2 item 3 — and **(b) the TEG** — sole intended launch consumer, `:186`. ALA/C2-SCI/owner are named as excluded because they hold only `aq-revocation-epoch-clients` (`:186-190`).
- §2.1's group-membership column (`v2:119`) already states both principals: "authority-user (chgrp only), **TEG** (joins in C6b) — and NO one else, ever" — consistent with the §2.3 correction.
- Checked §4's closure table (`v2:264`, unedited by this revision) for the residual phrase flagged in the request: it reads "...group whose only ever-added **consumer** is the TEG (C6b)." This is **not** a contradiction: the revision establishes "consumer" as a term of art (distinct from "member") throughout — §2.3 line 186 ("the TEG ... the **sole intended launch consumer**") and the RECORD footer line 433 ("TEG (C6b, sole intended launch consumer)") use it the same way. Since the authority-user is explicitly a non-consumer (chgrp/server role only, `:184-185`), "only ever-added consumer is the TEG" is true under the doc's own corrected definition. No instance of the false "only *member* added is the TEG" claim remains anywhere I searched (`grep -in "only.*TEG\|TEG.*only\|only ever-added"` across the full doc).
- RECORD footer (`v2:432-434`) is fully corrected and unambiguous: "...group whose only ever-added **members** are the authority-user (chgrp/server role, never a client) and the TEG (C6b, sole intended launch consumer)" — lists both principals under "members," the exact fix required.
- **Binding forward-condition**: §7 adds item 8 (`v2:398-407`) — explicitly framed as "not a criterion C6-S itself must satisfy... but a condition this freeze imposes on the next slice." It requires C6a's design to **cite this freeze** and **MUST implement an operation-specific `SO_PEERCRED` peer check verifying the connecting peer's uid/gid is the TEG principal** before honoring `authorize_launch`, and states a design that omits this "does not satisfy this freeze's forward-condition and must be revised before it may build on C6-S." This is genuinely binding (MUST language, explicit non-satisfaction consequence), not advisory. §2.3 (`v2:192-208`) and §4 row 3 (`v2:266`) both cross-reference it consistently.
- On "does it actually close the latent server-self-launch surface": correctly, it does **not** close anything within C6-S itself — there is no reachable op to close (deny-all stub, `v1:66`/`v2:66` unchanged), so there is nothing to fix at this slice. What it does is convert an advisory recommendation into an enforceable gate on C6a's own binding review, which is the right mechanism given the surface only becomes live once C6a attaches a reachable op. This matches exactly what the prior review's Finding 1.2 required.
- Minor structural note (non-blocking): item 8 sits under the header "Freeze criteria (**all must hold**)" while its own text disclaims that it isn't a self-criterion — the disclaimer is inline and unambiguous, so no reader is misled, but the placement is slightly awkward. Not a fresh finding; no revision needed.

### Fix 2 (LOW) — transport edit surface pinned — **CLOSED**

- §1 transport row (`v2:66`) states plainly: "`serve()` itself is NOT modified (pinned at binding review, Finding 2)... a NEW `serve_multi()` function... performs the *same* per-socket bind→chmod→chgrp→listen sequence twice and multiplexes `accept()`... This is **duplication of `serve()`'s loop body into a new function, not an extraction from or refactor of `serve()`** — `serve()` remains byte-for-byte unchanged." Control-socket byte-parity is explicitly asserted as a §7 freeze condition in the same row.
- §3 (`v2:225-236`, `v2:248-256`) restates the same facts consistently: `serve_multi()` is new/sibling, `serve()` untouched, byte-parity for the control socket holds regardless of which function serves it.
- Consistency with C6d's `__main__`-only claim: I read C6d's actual §1 row (`factory/c6d-design-v2:C6d-DESIGN-AND-AUTHORIZATION.md:51`) — C6d's own precondition for its `__main__`-only claim is specifically that `apply_bump`'s signature and the `transport:296` call site inside `build_env_handler` stay untouched. C6-S's §3 (`v2:251-256`) explicitly confirms it "does not touch `build_env_handler()`'s call site (`transport:296`) or `apply_bump`'s signature" — the actual thing C6d's claim depends on. The phrase "confined to `__main__` ... plus the addition of `serve_multi()` itself as a new, sibling function" is loosely worded (a genuinely new top-level function is not literally "confined to `__main__`"), but it explicitly discloses the addition in the same sentence, so it's transparent rather than misleading. Not a blocking finding.
- §3's closing paragraph agrees `serve()` is unmodified (`v2:253-254`), consistent with §1.

### Fix 3 (LOW) — reconciliation note — **CLOSED**

- §6 (`v2:332-344`) adds the exact reconciliation note requested: records that C6-S intentionally extends the parent decomposition's C6-S §2 file list with `dashboard/backend/api/routes/aistack.py` and `assets/dashboard.js`, gives the Rule-15 observability justification (ground truth: zero `revocation_epoch_authority` references in `aistack.py` at `f1f409ef`), cites the prior binding review's Finding 3 disposition (justified, minimal, correctly inventoried, not scope-creep), and notes the decomposition's own §2 coverage paragraph already anticipated this extension.

## Regression check — topology, group model, C6d composition

- **§1 anchor hashes unchanged** (v1→v2 diff touches only the "C6-S role" prose column, never the SHA-256 column): `revocation-epoch-authority.nix` `b539e5de…`, `revocation_epoch_transport.py` `066b30c3…`, `lease-signing-authority.nix` `2fb53e4c…`, `c2-scheduler-context-issuer.nix` `e14ce663…`, `default.nix` `7873bff5…` — identical to the values the prior review verified against `f1f409ef`. No source file changed anywhere in the branch (confirmed above: only the design doc differs from baseline), so these hashes remain valid without re-verification against HEAD.
- **PREPARED_ONLY marker preserved**: frontmatter `status` (`v2:4`) unchanged; RECORD footer (`v2:427`) reads "PREPARED_ONLY revision 2" (bumped correctly from "revision 1", `v2:5` frontmatter `revision: 2`).
- **Mechanism-B topology and group model undisturbed**: §2.1 two-socket table, §2.2 five-item membership-edit list, §5 exclusions, and the §7 freeze criteria 1–7 (topology, membership, ALA/C2-SCI/owner preservation, C6d composition, gate-OFF byte-parity, integration check, hash-binding) are byte-identical to v1 — none of the 34 deletions touched these; all deletions were confined to the three areas being corrected (§2.3's exclusivity paragraph, §3's transport-composition paragraph, §4's SO_PEERCRED table cell, §6's file-list footnote, plus the frontmatter/RECORD revision bump). No load-bearing content was removed.
- **C6d composition unchanged and still consistent**: recover-before-listen ordering, `Type=notify`, `sd_notify(READY=1)` gating, StateDirectory claims (§3 items 1, 3, 4) are untouched; only item 2's function-naming detail (`serve_multi()` vs. the earlier "bounded multi-listener helper") was sharpened, which is the Fix 2 correction itself, not a new change to the composition contract.
- **§6 integration-check inventory unaffected**: check id `0.10.52`, `trigger_paths` list, and the dual-harness wiring (`phase0.py` + `_aq-qa-bash`) are unchanged from v1.

No regressions found.

## Findings

None blocking. One non-blocking wording nit noted inline under Fix 1 (item-8 placement under a header stating "all must hold" while itself disclaiming that framing) and one under Fix 2 ("confined to `__main__` ... plus" phrasing is loose but not misleading). Neither requires a further revision.

## rev5 Finding 2 / decomposition Finding 1 closure — final status

Both remain **CLOSED** as the prior review found, with the Finding 1.2 forward-condition now genuinely binding (not merely recommended) and correctly scoped as a gate on C6a's own binding review rather than a claim of closure within C6-S itself, which has no reachable op to close.

VERDICT: FREEZE-ELIGIBLE
