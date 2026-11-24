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

### Gemini review Round 2

- `_high_entropy_blob` now calls `_has_high_entropy_window(b)` in place of the
  whole-blob entropy check. This catches credentials after low-entropy
  slash-less prefixes and credentials spanning segments shorter than 12
  characters after a low-entropy parent directory. The plain-hex short-circuit
  and the slash-less hyphenated-hex fallback still apply.
- `_bad_alnum_span` removes the unreachable `is_single_hex` branch. Both callers
  exclude plain-hex segments before adding them to the alphanumeric run.
- The collector regressions check a slash-less JSON field, a verified
  single-segment filename, and two verified paths with short credential
  segments joined by slashes. One uses hyphens and the other uses `+` and `=`.

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
Ran 32 tests in 2.863s

OK
```

The sweep compared the Round 2 candidate with `origin/main` (`f09150349`) over
every path returned by `git ls-files -z` in the worktree, including this tracked
note. For each path `p` it evaluated
`bool(scan(json.dumps({"files": [{"path": p}]}, sort_keys=True), ...))`
with the full scanner from each revision. Bare scans used no allowlist.
Verified scans supplied `allowed_paths={p}`.

```text
total=7918 base_bare=4371 head_bare=4495
base_verified=474 head_verified=432
new_flags_vs_base_bare=3
newly_flagged_vs_base_verified=374
cleared_vs_base_verified=416
```

The three paths flagged by `head_verified` and absent from `base_bare` are
mixed-case CamelCase font filenames:

- `ai-stack/agents/skills/canvas-design/canvas-fonts/NationalPark-Bold.ttf`
- `ai-stack/agents/skills/canvas-design/canvas-fonts/Outfit-Bold.ttf`
- `ai-stack/agents/skills/canvas-design/canvas-fonts/WorkSans-Italic.ttf`

Like sibling fonts, all three already failed `_path_like` before Round 2.
The low-entropy parent prefix had diluted their whole-blob entropy below the
threshold. The window check now flags each path even when it is verified.

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
