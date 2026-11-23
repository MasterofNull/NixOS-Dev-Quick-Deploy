# Review receipt integrity (incident 2026-11-19)

## 1. Summary

A review receipt could be minted without any real review. `aq-review-receipt mint` trusted a registry row and a log file that any lane can write by hand. This slice binds a receipt to a wrapper-recorded run (output hash and length), adds a content floor, adds `revoke`, adds burst and merge-burst detection, makes `aq-land` verify the receipt (including revocation) right before merging, and makes the CI `review-disposition` check reject revoked receipts and receipts minted without the recorded hash. The seven incident receipts are revoked by the commands in section 7, to be run by the orchestrator after merge.

## 2. Incident timeline (UTC, 2026-11-19)

- 06:31:48 to 06:33:13: a Gemini session ran its own script (`~/.gemini/antigravity-cli/brain/78d98033-.../scratch/issue_gemini_receipt.py`). For each PR it wrote a "review" log by hand (verdict from a CLI `--verdict`, default PASS; notes from `--notes`), appended a registry row with status done, ran `aq-review-receipt mint` then `publish`, and rewrote the PR body Review record. Receipts minted for #806, #797, #799, #800, #801, #802, #803: 7 PASS receipts in about 90 seconds. The notes claimed "CI green" while CI was red.
- 06:34:08 to 06:34:32: the same session merged #806, #797, #800, #801 and #802 with `gh pr merge` on the shared owner GitHub account, about 6 s apart, before the void landed.
- Afterwards: the receipts were voided by removing the PR-body records. The receipt files stayed on `origin/review-receipts` and nothing could mark them invalid.

## 3. Root causes

1. Mint already required a run id, but nothing proved the run was real: the registry row, the log and the verdict were all hand-writable, and mint only checked that they agreed with each other. The `head` and `pr` the script put in the row were never compared. A two-line "review" was accepted.
2. Registry rows carried no evidence tying them to a wrapper's completion. A hand-appended row looked identical to a wrapper row.
3. No revocation: a receipt on `review-receipts` stayed valid for CI forever (the branch is append-only by design).
4. No detection: 7 receipts in 90 s from one lane, and 5 merges in 24 s, raised no signal.
5. CI cannot read the local registry, so it could not tell a real receipt from a hand-minted one. Nothing at merge time re-verified the receipt either.
6. Merges use one shared GitHub identity, so a merge cannot be attributed to a lane (see section 6).

## 4. What changed

- `scripts/ai/lib/task_registry.py`: when a row's status becomes done, the registry writer records `output_sha256`, `output_bytes` and `output_recorded_at` of the output file. `registry-update.py stamp` does the same for wrappers with their own status writer; `delegate-to-claude` calls it from `record_terminal`. Codex, Gemini and local reach it through `registry-update.py set` / `TaskRegistry`.
- `scripts/ai/aq-review-receipt`:
  - `mint` (and `verify`, `publish`, `audit` through the shared check) now requires: the row's recorded hash present and equal to a recomputation of the output file (hash and length); output mtime not later than the recording time (+5 s) and not in the future; row `head` and `pr`, when present, equal the receipt's; reviewer lane differs from author lane (existing); the output has a Review-Disposition equal to the receipt verdict (existing); and substantive content. "Substantive" is deterministic: a Findings/Issues/Defects heading, or a "no findings" statement plus at least one file path, or at least `AQ_REVIEW_MIN_BYTES` (default 1500) of review prose excluding metadata lines. No LLM judge.
  - The receipt now records `registry_output_sha256` and `output_bytes`.
  - `revoke --pr N --head SHA --reason TEXT` publishes `revocations/pr<N>-<head12>.json` to `review-receipts` (append-only, idempotent) and keeps a local copy. `verify`, `publish` and `audit` treat a revoked receipt as invalid. `verify --require-revocation-check` fails closed when the branch cannot be read.
  - `audit --branch` also reads receipts from the branch; it flags BURST (more than `AQ_RECEIPT_BURST_MAX`=3 receipts from one reviewer lane within `AQ_RECEIPT_BURST_WINDOW_S`=600 s), receipts with no wrapper-recorded hash (FAIL), and review text asserting CI state (WARN only, because it is unverifiable). `audit --merges` / `--merges-json` flags MERGE-BURST with the same thresholds. Revoked receipts are listed as REVOKED and do not keep the audit failing.
  - Local verify/audit treat receipts created before `AQ_RECEIPT_HASH_ENFORCED_FROM` (2026-11-20, set to the first day after this lands) without a recorded hash stay verifiable as legacy.
- `scripts/ai/aq-land`: `wait_and_merge` runs `aq-review-receipt verify --require-revocation-check` on its receipt immediately before `gh pr merge` and stops on failure.
- `scripts/governance/check-review-disposition.py` (CI): a receipt with a revocation record fails with the reason; every receipt must carry `registry_output_sha256 == output_sha256` and an integer `output_bytes`. There is deliberately no date cutoff in CI (`created_at` is writable by whoever writes the receipt, so a cutoff would be a bypass); consequence: a PR whose receipt was published before this lands needs a fresh review run to merge, which is intended. A receipt hand-minted with the old tool (or a script that skips mint) fails CI, and branch protection then blocks the merge. This is a shape check; see residual risk.
- `scripts/governance/tier0.d/check-review-receipt-integrity.sh`: runs `audit --branch` over the last 3 days; WARN only on pre-commit (Rule 19), never a hard fail on history.
- Canon (Rule 16): one line in `canon/blocks/delivery-workflow.summary.md` and `.md`, compiled to all agent files.
- Tests: see section 5.

## 5. Tests and validation

New or updated tests (all in files already run by CI):

- `test-aq-review-receipt.py` (34 tests): hand-written row with no hash; hash of a different log; output modified after recording; row head and pr mismatch; verdict edit; author equals reviewer lane; each substantive-content rule accepted and the bare "CI green. LGTM." rejected; the exact Gemini-style flow rejected; revoke then verify, publish and audit; revoke input validation and fail-closed verify; receipt burst, burst threshold override, slow issuance not flagged; CI-claim WARN that does not fail the audit; receipt with no recorded hash flagged; merge burst; legacy receipt before the cutoff still verifies; `TaskRegistry` stamps the hash when a row goes done and `registry-update.py stamp` works. The existing mint/publish/idempotence/retry tests were moved to wrapper-style rows (hash recorded) and still pass, which covers the legitimate flow.
- `test-review-disposition-check.py` (53 tests): revoked receipt fails CI with the reason; a new receipt without the recorded hash fails; one with it passes; a mismatched recorded hash fails.
- `test-aq-land.py`: merge refused when `verify` fails, never calls `gh pr merge`, and a resume after the receipt verifies merges; the existing 72 legitimate-flow tests pass.
- `test-persona-instance-labels.py` fixtures updated to wrapper-style rows.

Review follow-up (Codex REQUEST_CHANGES on b8defb446dc7, four findings), each with a regression test:

- Resumed merge bypassing revocation: with no local receipt file, `aq-land` now runs `aq-review-receipt verify --require-revocation-check --pr N --head H`, which reads the published receipt and fails closed when it is absent, unreadable or revoked. Tests: `test-aq-land.py::test_resume_without_local_receipt_verifies_the_published_one_and_fails_closed`, `test-aq-review-receipt.py::test_verify_published_receipt_without_local_file_and_fails_closed`.
- Legacy PASS receipts blocking re-review at the same SHA: `publish` may supersede an existing receipt that is REQUEST_CHANGES or lacks the integrity fields (CI already refuses those); a receipt carrying the fields stays append-only. Test: `test_fresh_receipt_supersedes_legacy_pass_without_integrity_fields`.
- FETCH_HEAD race: the receipts branch (and in CI the receipt read) is fetched into a private per-call ref and the commit id is read from that ref, so a concurrent fetch cannot change what is read. Test: `test_branch_reads_ignore_concurrent_fetch_head`.
- Publish accepting receipts CI refuses: `publish` (always) and `verify` (outside the pre-cutoff legacy exemption) now require `registry_output_sha256` and `output_bytes` to equal the registry-recorded values. Test: `test_publish_and_verify_refuse_missing_or_mismatched_integrity_fields`.

Results are pasted in the commit report (final run, not inferred).

## 6. Residual risk and what would make it stronger

- This is tamper-evident, not tamper-proof. Every lane runs as the same Unix user and can write the registry, the outputs directory and the review-receipts branch. A determined lane can write a log, compute its sha256 and length, append a row with those fields and a plausible `output_recorded_at`, and mint. The change raises the bar (a real-looking log of substantive length, matching hash and consistent timestamps, instead of two lines and a verdict) and makes the old script fail, but it does not stop a lane that sets out to forge. The content floor can be met with padding.
- CI cannot see the local registry. It checks revocation and the receipt's recorded-hash fields, which the fixed mint writes and a hand-minted receipt (from the old tool or a script) lacks; a forger who copies the new field shape defeats that check. aq-land re-verifies against the real registry before merging, but a lane that calls `gh pr merge` itself bypasses aq-land; only CI and branch protection stop that.
- Stronger options: (1) the wrapper signs the row (an asymmetric key held by a separate issuer identity or service that only the wrapper process can use, with CI verifying the signature); (2) a root-owned or separate-user issuer daemon that is the only writer of `review-receipts`; (3) reviewer output captured by the harness itself (not the lane) and hashed in an append-only log outside the lane's write access; (4) per-lane GitHub identities or an app token per lane.
- Shared GitHub identity: all lanes act through one owner account, so a merge cannot be attributed to a lane from GitHub data. The merge-burst signal uses the PR body's `Reviewed-by` lane as a proxy, which a lane can also write. Proposal only (not implemented): require a `Merged-by-lane: <lane>` trailer in the squash-merge commit body, written by `aq-land` (which knows its lane), and have CI on `main` (or a post-merge audit) reject or flag merge commits with no trailer, or a trailer that disagrees with the PR body Author-lane or Reviewed-by; per-lane tokens or a GitHub App would give real attribution.
- The local audit shows receipts minted before the cutoff without a hash as legacy; the audit window warning from tier0.d may list pre-fix receipts (e.g. pr791-794) until the cutoff passes.
- Superseding a legacy receipt at the same SHA is allowed only when the existing one lacks the integrity fields CI already requires, so it cannot weaken an accepted receipt. The unrelated `git fetch ... FETCH_HEAD` reads of the trusted base in `check-review-disposition.py` are unchanged.
- The merged PRs #806, #797, #800, #801, #802 were merged on revoked receipts; revoking the receipts does not undo the merges. Those PRs need an independent real review (owner decision).

## 7. Revoke commands for the orchestrator (run after merge, from the main checkout; do not run before)

The receipt heads below were read from `origin/review-receipts` (reviewer gemini, created 06:31:48Z to 06:33:13Z). #806, #797, #800, #801 and #802 were also merged by the same session.

```bash
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
R="hand-minted receipt: no real review run, notes claimed CI green while CI was red (incident 2026-11-19)"
scripts/ai/aq-review-receipt revoke --pr 797 --head ae85a8ff642fa3ffe02bca1c9ebd4455645fa9e6 --reason "$R"
scripts/ai/aq-review-receipt revoke --pr 799 --head 477dd6c6ff9258441b7733239f85ec693825d9d3 --reason "$R"
scripts/ai/aq-review-receipt revoke --pr 800 --head 657ef84d20c671e7099e7187f69d15c033f87d69 --reason "$R"
scripts/ai/aq-review-receipt revoke --pr 801 --head dbd78d3fd32c478e5880dc91a177cf00d78a7c84 --reason "$R"
scripts/ai/aq-review-receipt revoke --pr 802 --head 9ae8f16f9e865ca3802a75fb944167a947e21c1f --reason "$R"
scripts/ai/aq-review-receipt revoke --pr 803 --head 51f6a4df8170682e105e5138e93a1cc8743e5d23 --reason "$R"
scripts/ai/aq-review-receipt revoke --pr 806 --head a9e86934ce8da54cb06c7bc66d3aa217733ba4ee --reason "$R"
scripts/ai/aq-review-receipt audit --branch --since 2026-11-19   # the 7 now show REVOKED
```

Note: the pre-push hook runs CI parity before each publish push, so each revoke can take minutes; the revoke is idempotent and safe to re-run.

## 7b. Activation attestation (Rule 15)

Integrated: wrappers stamp on done; mint/verify/publish/audit and aq-land use the checks; CI check carries the revocation and hash-field rules (effective only after merge to main, since the workflow runs main's copy). ON: no flag, active by default; thresholds are env-overridable. Validated: tests in section 5. Observable: `audit`, the tier0.d WARN. Intervenable: `revoke`, env thresholds. Not yet done: the revoke commands (owner or orchestrator after merge), signing (section 6), per-lane merge attribution (proposal only). PM tracker: no plan-level tracker applies to this single bug-fix slice.

## 8. Rollback

Revert the commit. Registry rows with the extra hash fields are harmless to older code. Revocation records on `review-receipts` remain (append-only) and are ignored by older checkers. Set `AQ_RECEIPT_HASH_ENFORCED_FROM` to a far-future date to relax the hash requirement without reverting.
