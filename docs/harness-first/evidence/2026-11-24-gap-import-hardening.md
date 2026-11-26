# Gap import hardening — 2026-11-24

`GAP-IMPORT-JUNK-TO-REMOTE` originated in `ai-gap-import.service`'s import path. The gap selector ranked raw queries, so greetings and health probes could reach the generator. The importer always used Gemini and interpolated untrusted input into Python source, AIDB document paths, and the gap cleanup SQL.

The selector filters noise before ranking, deduplicates by maximum occurrence count, and passes the configured path and limits as Python arguments. A junk-only log exits successfully and reports skipped gaps on stderr. A batch whose imports all fail exits with status 1. Under Rule 17, the default `auto` lane tries local generation first and warns on Gemini fallback. Explicit lane selection fails closed.

The importer serializes the AIDB payload as JSON and derives a single path component from the title. A sanitized or truncated title receives a topic hash suffix to distinguish inputs that normalize to the same slug. Gap cleanup escapes each backslash, percent sign, and underscore in the first 40 characters of the topic, including the underscore in `query_gaps` when that string appears in the topic. The resulting pattern is supplied through a `psql` variable. The importer supplies fixed SQL via `--file -` because `psql --command` bypasses variable interpolation. Both the CI path trigger and the test list include `test-aq-gap-import.py`, which the existing `tests-aq` command dispatches. The `tests-aq.paths` triggers also include both production scripts, `scripts/ai/aq-gap-import` and `scripts/ai/aq-knowledge-import.sh`, so changes to either select that test group.

## Round 2 review fixes — 2026-11-26

Addressed the three findings from independent Gemini review `gemini-20261126-035622-840p5z` against `13baa8c11`. The selector rejects empty token lists and checks technical markers against punctuation-trimmed `norm`, preventing trailing sentence periods and emoticons from admitting noise. Regression coverage rejects `can you please.`, `what is it.`, `...`, `/`, `???`, and `hi :)` without delegate calls, while preserving `systemd.tmpfiles.rules`, `what is lib.mkForce`, `NixOS flake overlay priority`, `--clear-gaps`, and `/etc/nixos/configuration.nix` through the import path.

Gap cleanup now counts nonblank returned rows with the existing `python3` dependency instead of adding `awk`. Tests cover truly empty output, whitespace-only output (both report `Cleared 0 matching gap entries`), and two IDs separated by blank lines with no final newline. Both production scripts now trigger `tests-aq` in changed-path CI selection.

## Verification

The following checks were rerun for Round 2 on 2026-11-26; service dependencies remain stubbed in the Python suite.

| Check | Result |
| --- | --- |
| `bash -n` on each import script | Exit 0, no output |
| `shellcheck scripts/ai/aq-gap-import scripts/ai/aq-knowledge-import.sh` | Exit 0, no output |
| `python3 -m py_compile scripts/testing/test-aq-gap-import.py` | Exit 0, no output |
| `ruff check --no-cache scripts/testing/test-aq-gap-import.py` | `All checks passed!` |
| `basedpyright scripts/testing/test-aq-gap-import.py` | `0 errors, 0 warnings, 0 notes` |
| `python3 scripts/testing/test-aq-gap-import.py` | `Ran 13 tests in 5.568s` · `OK` |
| `bash scripts/governance/tier0.d/check-ci-test-coverage.sh` | `[tier0.d/check-ci-test-coverage] PASS (813 tests: 721 declared, 92 exempt)` |

The prior round’s disposable PostgreSQL instance confirmed that `--command` failed at the unsubstituted variable and `--file -` matched only the row containing the literal pattern.

```text
psql --command: ERROR: syntax error at or near ":"
psql --file -: deleted 17; retained 18 and 19
```

## Rule 15 activation attestation

| Dimension | Evidence or deferral as of 2026-11-24 |
| --- | --- |
| Integrated | The scripts implement the existing gap-import entry points and the test is registered in `tests-aq`. Integration into the deployed revision is deferred to the orchestrator. |
| Turned on | Service activation is deferred to the owner’s deployment. |
| Validated end to end | The isolated service entry points passed the stubbed import tests and the SQL passed against disposable PostgreSQL. A live run with deployed delegates and AIDB is deferred to the orchestrator after activation. |
| Observable | The tests verify skip reporting, fallback warnings, and a nonzero exit for failed generation. Service journal verification is deferred until activation. |
| Intervenable | `GAP_IMPORT_LANE` selects `auto`, `local`, or `gemini`. Lane-specific timeout variables control generation time. Explicit lane failures propagate as nonzero exits. |
| PM-tracked live | The orchestrator owns the deferred tracker and activation updates. |

## Rollback

Use the normal owner-approved deployment process to redeploy the prior approved revision. Keep gap import paused if reverting the change, since the prior revision restores unconditional Gemini routing and unsafe input handling.
