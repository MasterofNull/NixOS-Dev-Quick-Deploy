# S5 receipt entropy scanner hardening

## PR #788 baseline and follow-up

The S5 collector quarantined PR #788 after the receipt scanner flagged the path
`docs/harness-first/evidence/2026-11-15-deploy-validation.md`. The pre-#834
revisions `f5880650a` and `e68cfa5ee` both flag that path in a bare scan of
`{"files": [{"path": "…"}]}`. PR #834 (`3dd3956e0`) introduced a global
path-shaped exemption and cleared the sample in a bare scan. PR #828 integrated
that mainline at `6062e2b52` on its topic branch and landed as the squash commit
`1793d7cc4`. It restored the bare scan's entropy finding and allowed the sample
to pass when the caller supplied the exact path as verified diff metadata. The
two Python files at this slice's `origin/main` base (`f09150349`) match the
versions at `6062e2b52`.

The topic-branch hardening through `7a5697afd` and the Round 11 linear-time fix
remained unlanded. The following replay uses the reported PR #788 path in a
single-file JSON payload. `verified` supplies the exact path in `allowed_paths`.

```text
f5880650a bare=['entropy']
e68cfa5ee bare=['entropy']
3dd3956e0 bare=[]
6062e2b52 bare=['entropy'] verified=[]
candidate bare=['entropy'] verified=[]
```

## Scanner changes

- `_B64_SLASH` checks slash-spanning Base64-like runs. Its guard evaluates the
  combined non-hex segments against the 4.35-bit threshold.
- `_high_entropy_blob` checks components and contiguous runs independently so
  low-entropy parent directories cannot dilute a suspicious component's score.
- `_bad_alnum_span` uses an O(L) two-pointer scan over alphanumeric slash
  segments, where L is the run length.
- `_HEX_DELIM_RUN` consumes an entire hex run even when it contains no delimiter.
  `_iter_hyphen_hex` filters for hyphens and underscores after matching, avoiding
  the quadratic retry over plain hex prefixes. `_HEX.fullmatch` short-circuits
  plain hex blobs before further entropy checks.
- `_has_high_entropy_window` keeps a character `Counter` for each of the fixed
  32- and 36-character windows and updates it as the window slides, for O(N)
  scanning over N characters. The long-value regression checks a 16 KiB plain hex
  value in under 50 ms and all four fixtures in under 500 ms.

## Verification

```text
$ python3 -m py_compile scripts/ai/lib/outcome_receipt.py scripts/testing/test-collect-trajectories.py
exit=0 (no output)

$ basedpyright scripts/ai/lib/outcome_receipt.py scripts/testing/test-collect-trajectories.py
0 errors, 0 warnings, 0 notes

$ ruff check scripts/ai/lib/outcome_receipt.py scripts/testing/test-collect-trajectories.py
All checks passed!

$ python3 -m unittest scripts/testing/test-collect-trajectories.py scripts/testing/test-outcome-receipt.py
..........................WARN: outcome receipt for PR #6 quarantined (password_field)
....WARN: outcome receipt for PR #10 quarantined (password_field)
WARN: outcome receipt for PR #11 quarantined (pattern2)
WARN: outcome receipt for PR #12 quarantined (bearer_token)
WARN: outcome receipt for PR #13 quarantined (entropy)
..
----------------------------------------------------------------------
Ran 32 tests in 2.897s

OK
```

The sweep used every path from `git ls-files -z` before staging this note. For
each path `p` it evaluated `bool(scan(json.dumps({"files": [{"path": p}]},
sort_keys=True), ...))` with the full scanner from each revision. The bare scans
used no allowlist and the verified scans supplied `allowed_paths={p}`. `base`
counts bare `origin/main` flags and `new_flags` counts candidate verified flags
absent from that baseline.

```text
total=7917 base=4370 head_bare=4370 head_verified=429 new_flags=0
base_verified=474 newly_flagged_vs_base_verified=371 cleared_vs_base_verified=416
7a5697afd_verified=429 round11_verified_path_changes=0 bare_path_changes=0
```

The hardening at `7a5697afd` accounts for all 371 newly flagged and 416 cleared
paths in the verified-to-verified comparison. Round 11 leaves that flag set
unchanged. This sweep measures scanner decisions for individual tracked paths.

## Rule 15 activation attestation

- **Integrated.** The existing S5 collector entry point uses the receipt scanner.
  Collector integration tests exercise verified paths and quarantine decisions.
- **Observable.** The tests observed quarantine warnings and checked collected
  and quarantined counts. The staged change uses those existing signals.
- **Intervenable.** Roll back the follow-up through the normal reviewed workflow
  with `git revert <landed-commit>`.
- **Deferred on 2026-11-24.** The orchestrator owns landing, live activation,
  end-to-end validation with the deployed collector, confirmation of live
  observability, and live PM tracking. This isolated worktree provides the
  integration and path-sweep evidence for that handoff.
