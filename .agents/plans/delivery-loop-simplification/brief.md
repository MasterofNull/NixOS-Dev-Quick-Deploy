Expert design round: simplify the agentic delivery and update loop WITHOUT weakening what it proves.

You are an independent expert. Give your own analysis; do not defer to the proposal. Output: findings, a recommended design, risks, and a frozen-MVP slice list with acceptance tests. Plain language. Cite file paths. Max 800 words. This is design only: make no code changes.

Evidence (PRs #685-#702, 2026-11-04/05):
1. Review receipts are commits on the PR branch, so each receipt changes the head and restarts full CI (about 1 h with the closure scan). The review-disposition check reads the PR body from the frozen event payload, so a push and a body edit in the same second can leave a false red.
2. tier0 --pre-commit, the pre-push hook (ci-merge-parity + run-ci-checks) and CI repeat the same checks. Local copies have short timeouts (60 s harness suite, 30 s phase0 subprocess) and flaked under load, blocking receipt-only commits.
3. Merges are hand-sequenced. Main moving under a reviewed head caused conflicts in config/ci-checks.json and scripts/testing/run-test-group.py, stale reviews, and a shrink of one PR's net change.
4. Landing logic lived in orchestrator scratch scripts in /tmp, was rebuilt several times, and was lost to a power cut.
5. Owner rebuild path is manual: flake refresh PR, a custom checkout sync script, aq-deploy-current, a ledger copy. Owner directives: rebuild only for NixOS-config changes; every rebuild includes all current updates; flake update runs right before the rebuild and lands via PR.
6. Owner checkout doubled as live state (P1.10 moved the writers to state dirs; goes live at the next rebuild).
Things the gates caught that must stay caught: forged/self-review (2026-10-27 audit: 48 self-acceptances), masked CI jobs, 560 tests never run in CI, an unlockable flake input, a stale review after main moved, tests mutating live state, always-pass gates.

Draft proposal to attack, not to accept:
A. `aq-land <worktree>` in the repo: sync, independent review of the exact head, PR, receipt. Receipts become a commit status or check bound to the reviewed tree, not a commit.
B. Move slow and live checks out of tier0 --pre-commit to CI; keep fast, deterministic local checks.
C. GitHub merge queue so main-moved staleness and sequencing disappear.
D. `aq-update`: scheduled lock-only PR with deterministic checks, then one owner command for sync + rebuild + validate (recovery item P1.9).

Questions:
1. Can a status/check receipt be forged more easily than a committed file, given all lanes share the owner's gh credential? What binding (tree hash? signed attestation? separate identity?) keeps review non-forgeable, and what detection pairs with it?
2. Does a merge queue fit a solo-owner repo with one required check, and how does it interact with review bound to a head when the queue builds a merged tree?
3. Which tier0 checks must stay local to stop bad commits early, and which belong only in CI? Name the criteria.
4. What is the smallest MVP that removes most of the friction? What should NOT be built?
5. Failure modes: lane down, CI outage, power loss mid-landing, owner offline. What happens in each?
6. What must be measured to prove this is actually simpler and no weaker (e.g. time from reviewed to merged, false-red count, defects caught by each gate)?

Repo context: AGENTS.md, .agents/plans/system-integrity-recovery/DESIGN.md, scripts/governance/check-review-disposition.py, scripts/ai/aq-review-receipt, scripts/governance/tier0-validation-gate.sh, .githooks/pre-push, scripts/maintenance/aq-deploy-current, .agents/delegation/outputs/landing/land.sh, config/ci-checks.json.
