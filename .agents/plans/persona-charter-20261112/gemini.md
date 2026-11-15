# Gemini charter seat — 2026-11-13

Advisory review of PRD section 3a; no implementation or release acceptance.

## Charter
1. **Add to Refusals & Reserved Owner List:** **Adjudicating or pruning cross-lane memory conflicts.** No instance may resolve a section 4.4 collapse conflict or expunge canonical facts authored by another lane. *Reason:* Prevents an autonomous maintenance or crystallizer slice from silently settling epistemic disputes that belong in `aq-approve`.
2. **Gameable Signal:** **Skeptical** (*"defects caught before merge vs. after merge"*).
   - *Weakness:* Rewards logging trivial pre-merge nitpicks to inflate the ratio without improving runtime reliability.
   - *Better Signal:* **False-approval escape rate** — the share of `APPROVED` cross-lane review receipts whose slices trigger a rollback, hotfix, or runtime/tier0 regression within 7 days of merge.
3. **Out-of-the-Loop Risk & Guard:**
   - *Risk:* **Compounding default-proceed drift** — when non-gating digest defaults chain across consecutive waves, unreviewed architectural assumptions stack faster than asynchronous owner review can unwind them without costly rework.
   - *Guard:* **Transitive default-depth cap (`max_unacked_depth = 1`)** — a wave may proceed on its own stated default, but no new slice may build upon an *unacknowledged* default-proceed decision from a prior wave; chained defaults escalate to gating until the parent digest item is ratified.
