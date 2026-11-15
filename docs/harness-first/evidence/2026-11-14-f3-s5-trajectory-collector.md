# F3 S5: offline verified-trajectory collector

Date: 2026-11-14
Task ID: HF-20261114-S5

## Objective
- Build slice S5 of the frozen F3 MVP (`.agents/plans/frugal-sota-leadership-20261113/F3-FREEZE.md`, sha256 of the rev-2 draft `1675bbc1...`): `scripts/data/collect-verified-trajectories.py`, an offline CLI that turns outcome receipts into verified-trajectory rows.
- Delivered: collector; `is_eligible` helper in `scripts/ai/lib/outcome_receipt.py` (additive, no schema change); four raw counters in `aq-scoreboard`; `scripts/testing/test-collect-trajectories.py` covering acceptance (a)-(i); `.gitignore` entries; plan-dir docs (freeze copy, Gemini review, prototypes, tracker items). `aq-land` is not modified; S6 is not in scope.
- Re-cited against origin/main f5b304d8b (#782): `aq-land:679-691` (`record_outcome`, `tier0=None` at :688), `outcome_receipt.py` `scan`/`_redact`/`_append`, `delegation_dir.py:20-30`.

## Workflow/Session IDs
- Workflow ID: none (bounded slice from the freeze section 2)
- Session ID: Simurg@claude/sonnet; orchestrator Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
- Delegated by the orchestrator to a Sonnet 5.5 implementer (Rule 17). Independent review is by another lane; the implementer does not self-review, merge, or open the PR.
- Reviews of the plan: Codex PLAN_READY_WITH_FOLLOWUPS (`codex-20261114-172254-y10co7`), local Qwen PLAN_READY_WITH_FOLLOWUPS (`local-20261114-094351-5czah4`); both followups satisfied (S4b = #782, fixtures archived). Gemini (pillar author) is out until 2026-11-20; its advisory review is queued.

## Commands Executed
```bash
python3 scripts/testing/test-collect-trajectories.py
python3 scripts/testing/test-outcome-receipt.py
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
# baseline run, temp output dir, offline producers: real gh + git against the main checkout
AQ_DELEGATION_DIR=<scratch>/f3out python3 scripts/data/collect-verified-trajectories.py --receipts-dir <live .agents/delegation> --repo <main checkout> --pr 777 ... --pr 782
AQ_DELEGATION_DIR=<scratch>/f3out python3 scripts/data/collect-verified-trajectories.py --receipts-dir <scratch>/f3syn --repo <main checkout>
python3 scripts/ai/aq-scoreboard --dir <scratch>/f3out
```
Kill switch: `AQ_TRAJECTORY_COLLECT=0`. Privacy: row serialised, `_redact`, then `found += scan(redacted)`; any finding or `redactor_unavailable` goes to `trajectories.quarantine.jsonl` (identifiers only when the redactor is unavailable or the range is unreachable). Files are never chmodded: a pre-existing main or quarantine file with any group/other bit makes the collector exit 2 before writing.

## Validation Evidence
- Tests: 11 tests, all pass, covering (a) 0600 row incl. RC-then-PASS `rejected_rounds=2`, (b) Bearer and `/run/secrets` path quarantined and absent from main, (c) AWS-style key removed by `_redact` (scan clean) still quarantined via `found`, (d) redactor missing gives a payload-free quarantine row, (e) 0644 main and 0644 quarantine each refuse (exit 2, mode unchanged), (f) self-reviewed and `ci=None` rows skipped, (g) second run adds 0 rows, (h) kill switch writes nothing, (i) unreachable range quarantines `range_unreachable` once, is not duplicated, and is collected after the range becomes reachable; plus gh-missing counts as pending and `aq-scoreboard --json` returns ints for the four counters. Pasted output is in the commit hand-off report.
- First measured baseline (collector run once, offline, into a temp dir, not the live one):
  - Live receipts file `.agents/delegation/outcome-receipts.jsonl`: 0 rows (the S4b fixture row is archived; no real landing has been receipted since). Run over PRs #777-#782: `{"collected":0,"quarantined":0,"not_eligible":0,"pending":0,"already_done":0}`. Real eligible supply today is 0.
  - To exercise the real producers anyway, a second run used SYNTHETIC receipts built from the real PR metadata of the six merged PRs #777-#782 (all marked author claude, reviewer gemini, PASS, ci pass; these are not real receipts and are not evidence of review): `{"collected":1,"quarantined":5,"not_eligible":0,"pending":0,"already_done":0}`. `gh pr view` and `git diff --numstat <base>...<head>` resolved for all six (no `range_unreachable`). Row: PR #778, 2 files, +5/-5, merge_sha present, file mode 0600. `aq-scoreboard`: `trajectories_collected=1, trajectories_quarantined=5, receipts_not_eligible=0, receipts_pending=0`.
  - Finding: the 5 quarantines are all reason `entropy`, a false positive. `outcome_receipt.scan` flags any 32+ char `[A-Za-z0-9+/_=-]` run with Shannon entropy above 4.0, and long repo paths match (e.g. `docs/harness-first/evidence/2026-11-14-telemetry-test-isolation` 4.19, `scripts/testing/fixtures/local-inference-l2b-payload-golden` 4.21). Fail-closed is safe, but on this sample 5 of 6 real PRs would be lost, so the supply of verified trajectories is far below the eligible-receipt count. The producer is the scanner heuristic, which is outside S5's owned scope (`outcome_receipt.py` is "additive helper only"); S5 does not work around it. A follow-up should treat path-shaped tokens separately (for example split on `/` before the entropy check) with its own test.

## Rollback Plan
- `git revert <sha>`. Trigger: collector or scoreboard failures. Output files: `mv .agents/delegation/trajectories*.jsonl .agents/archive/<date>-trajectories/` (Rule 12). Kill switch: `AQ_TRAJECTORY_COLLECT=0` stops collection without a revert.
- Reference prototypes in the plan dir are excluded from `ruff`, `pyrightconfig.json` and `check-python-types.py` (`.agents/plans/*/prototypes`), the same way archive dirs are; they are not wired.

## Residual Risk
- Entropy false positives (above) cut yield; no yield forecast is made.
- Activation (Rule 15) is not done: the freeze requires one real run after a real landing with counters visible in `aq-scoreboard`. No real receipts exist yet; status stays BUILT until then. No timer is installed (collector trigger stays manual, freeze open question 3).
- `git fetch origin refs/pull/<n>/head` assumes a remote named `origin`; otherwise the row quarantines as `range_unreachable` and retries.
- Rows contain paths and line counts only; no diff bodies or rejected-attempt text.

## Hint Feedback
- No aq-hints used; the work was fully specified by the freeze.
