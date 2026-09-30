# C6d rev2 — Independent Binding Design Re-Review (focused)

Subject: `factory/c6d-design-v2` at `891b1eae225a562e62399cf8ebf7d1ce2c467b1f`
File under review: `.agents/plans/aqos-foundation-c/C6d-DESIGN-AND-AUTHORIZATION.md` (the only changed file)
Baseline: `f1f409ef97f73fb6ae152a297ba0c0367e30bf22` (main)
Role: **independent binding reviewer** — bounded re-review of exactly the three fixes required by the prior binding review (`CODEX-C6D-DESIGN-BINDING-REVIEW-20260924.md`). Did not re-open the design.

**Disposition: FREEZE-ELIGIBLE.** All three required fixes are CLOSED and verified against HEAD; no regression found in the a/b/c/d closures or the deterministic recovery core.

## Reproduced diff digest

`command git diff f1f409ef..factory/c6d-design-v2 | sha256sum`
`389e0080db04119414e1258f55a68ebf1ba3f8f572f65d10c21aecbb7efb7bfa  -` — **MATCHES** the requested digest exactly. Only the one file changed (435 insertions against the pre-C6d baseline). No subject drift.

`command git diff --stat factory/c6d-design..factory/c6d-design-v2` → `1 file changed, 80 insertions(+), 20 deletions(-)` — matches the task's stated +80/−20.

## Per-fix closure

**Fix 1 (MEDIUM, was blocking) — cross-identity conflict branch: CLOSED.**
- §3.1 step 2's "EITHER already exists" branch now reads the `entry_id` **stored in the pre-existing index** and hands off to `resolve(stored_entry_id, presented={request_id, idempotency_key})`, explicitly noting the incoming call's own composite `entry_id` is not assumed to equal `stored_entry_id`.
- §3.2 is renamed `resolve(entry_id, presented?)` and states it is now a **total function**: every `{journal-presence, phase, current, presented}` input maps to exactly one typed outcome, never raises. An **identity gate** runs before the phase table:
  - journal absent for `entry_id` → typed **retryable** deny (NOT `DENY_REPLAY`), releases the pre-existing index(es) — the live-path mirror of the existing §3.3 orphan-index sweep;
  - journal present + presented pair ≠ stored pair → typed **`DENY_IDENTITY_CONFLICT`** — doc explicitly states this branch never returns the existing receipt, never mutates the epoch, never releases the legitimate entry's indexes, never bumps;
  - journal present + (`presented` absent, i.e. `recover()`, or stored == presented) → falls through unchanged to the existing phase table (committed / intent+current==new / intent+current==old / intent+current∉{old,new}) — those four rows are byte-identical to rev1, confirmed via diff (no `-` lines inside the table body itself).
- Confirmed `recover()` (§3.3) calls `resolve(entry_id)` with **no** `presented` argument — doc states this twice ("`recover()` invoking `resolve()` never hits this row"; "Live path only (`recover()` passes no `presented`)"). Since §3.1–§3.3 run wholly serialized under the single exclusive `epoch.lock` (`_acquire_epoch_lock:549`, unchanged invariant at doc lines 143–145, "totally serialized... no concurrent writer"), an index-EEXIST-with-journal-absent observed on the live path can only be a genuine post-crash orphan from an earlier call whose lock was released by process death — never a legitimately in-flight concurrent call — so the new retryable-deny/release branch cannot race a live in-progress reservation. §5 gains vector **j** (live-path, no crash) exercising exactly this branch; vectors a–i are textually unchanged. §4's a/b/c/d closure table rows are unchanged (only a new paragraph appended after them, not altering the four entries).
- Net: `apply_bump`/`resolve()` are now provably total; the conflict branch never returns the original receipt, never bumps, never touches the legitimate entry's indexes; the epoch CAS still fires only on the fresh both-indexes-created path (doc states this explicitly). §3.3/the a–i matrix are untouched.

**Fix 2 (LOW) — §6 hardening citations: CLOSED.** Verified against `f1f409ef:nix/modules/services/revocation-epoch-authority.nix` directly:
- `NoNewPrivileges = true;` → line **159** (doc now cites `:159`) — match.
- `ProtectSystem = "strict";` → line **161** (doc now cites `:161`) — match.
- `RestrictAddressFamilies = ["AF_UNIX"];` → line **166** (doc now cites `:166`) — match.
All three off-by-one citations from rev1 are corrected exactly.

**Fix 3 (LOW) — transport edit precondition: CLOSED.** Verified against `f1f409ef:scripts/ai/lib/revocation_epoch_transport.py`:
- `def build_env_handler(...)` → line **246** (doc: "def :246") — match.
- `return re_lib.apply_bump(bump_doc, epoch_path, ledger, owner_keys_json)` → line **296**, inside `build_env_handler`, not `__main__` (doc: "handler call site is `revocation_epoch_transport.py:296` inside `build_env_handler`... not `__main__` (:301)") — match.
- `if __name__ == "__main__":` → line **301** — match.
§1 row 2 now states the `__main__`-only scope claim is conditional on `apply_bump`'s signature being preserved and the three new dirs being derived as siblings of `epoch_path` (no new params/env) — makes the precondition explicit as required.

## Regression check — a/b/c/d + recovery core

No regression. The 20 deleted lines in the rev1→rev2 diff are exclusively: (1) the old unconditional §1 transport-row sentence, replaced by the same sentence plus the precondition addendum; (2) the old §2.1 paragraph ending, extended with a forward-reference to the new §3.2 gate; (3) the old unconditional §3.1 step-2 handoff text, replaced with the stored-`entry_id` version; (4) the old §3.2 opening two lines, replaced by the expanded total-function framing; (5) the old §6 three off-by-one citations; (6) the old §8 closure-criteria item 4 wording, extended to mention vector j; (7) the old footer "revision 1" record line. None of these deletions remove load-bearing recovery text — each is a superset rewrite in place. The §3.2 phase-table rows (committed / intent+current==new / intent+current==old / intent+current∉{old,new}), §3.3's bipartite reconciliation algorithm, the §4 a/b/c/d closure table entries, and the §5 vectors a–i are all textually unchanged. PREPARED_ONLY marker, §1 file-hash anchors, and the "no implementation/freeze/activation/epoch bump" authorization scope are unchanged; frontmatter `revision:` bumped 1→2 as expected.

## Findings

None. No new HIGH/MEDIUM/LOW findings from this bounded re-review.

VERDICT: FREEZE-ELIGIBLE
