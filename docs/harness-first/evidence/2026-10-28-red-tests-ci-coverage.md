# P0.5 red tests + CI test-coverage gate (2026-10-28)

Plan: `.agents/plans/system-integrity-recovery` P0.5. Branch `fix/red-tests-and-ci-coverage` from origin/main 47132b14.

## Part 1 - four red tests

| Test | Root cause | Product or test | Fix |
|---|---|---|---|
| test-delegate-dir-env-override.py | Asserted the literal `DELEGATION_DIR="${AQ_DELEGATION_DIR:-$REPO_ROOT/.agents/delegation}"`. Delegates still honor `AQ_DELEGATION_DIR`; the default became `$(resolve_delegation_dir "$SCRIPT_DIR")` (shared main-worktree dir) in 36c97f94 / 7c747581 (#642). | Test stale (behavior intended, override intact in delegate-to-codex/claude/local/gemini) | Regex now matches the resolve_delegation_dir form |
| test-delegate-codex-quota-precheck.sh | Test hardcoded `$REPO_ROOT/.agents/delegation` but the product now resolves the shared main-worktree dir and (7c747581) enforces a rolling 24h token budget from that dir's outputs; live ledger was 258041/250000 so every dispatch exited 3 before reaching the stub. Also touched live registry/cooldown. | Test stale | Test sets a private `AQ_DELEGATION_DIR` under its mktemp dir; 15/15 pass, no live state touched |
| test-delegate-codex-shared-writable.py | (a) asserted `"worktrees" not in argv` but the checkout itself lives under `.agents/delegation/worktrees/`; (b) `--shared --mode edit` rejection was masked by the live budget gate (exit 3 message) | Test environment-coupled; product correct (`-C` is exactly REPO_ROOT) | Assert `-C == REPO_ROOT` and check "worktrees" only after removing REPO_ROOT; private AQ_DELEGATION_DIR; GIT_* stripped |
| test-aq-collab-round-dispatch-contract.py | `_dispatch_process` now launches via `subprocess.Popen(..., start_new_session=True)` + `communicate(timeout=300)` (launch-budget change); tests mocked `subprocess.run`, so the real shims were exercised/not mocked | Test stale | Mock `Popen`/`communicate`; temp-git-repo test strips GIT_* |

## Part 2 - gate

- `scripts/governance/tier0.d/check-ci-test-coverage.sh`: every `scripts/testing/test-*.{py,sh}` must be in a check `cmd`, a check's `tests` list, or `test_exempt` (with reason); also fails on reasonless, stale (missing file) and duplicate (also declared) exemptions.
- `scripts/testing/run-test-group.py <id>`: runs a check's `tests` (120 s each, 4 parallel, GIT_* and PYTHONPATH stripped, private AQ_DELEGATION_DIR). PYTHONPATH is stripped because operator shells point it at the main checkout, which shadowed this tree's modules (test-routing-profile-registry failed ambient, passed clean).
- `scripts/testing/test-ci-test-coverage-gate.py` (check `ci-test-coverage-gate`): proves fail on undeclared / reasonless / stale / double-listed, pass on declared / exempted / group-listed.

## Population run (740 undeclared tests)

Each test ran once with a 120 s timeout, GIT_* stripped, stdin closed, in a no-network user namespace (loopback up), 8-way parallel; non-network failures re-run unsandboxed; passes re-run twice more (plain parallel, then serial with a tracked-file pollution check).

Result: 604 declared (14 groups + the gate test) / 145 exempt, of 749 tests.

Exempt breakdown: fails on main 110 (missing files/modules, stale assertions), host-only 26 (live service or loopback/uid dependent), mutates tracked repo state 3, slow 3 (>45 s or >120 s), unstable 3.

Group runtimes (run-ci-checks --all): total ~7 min serial groups; each group's `paths` are its member tests, so `--changed` runs only touched tests.

## Not done / caveats

- No `.github/workflows` step runs the `tests-*` groups yet (CI invokes checks per `--only <id>`; the declared tests were verified on this host, not on an ubuntu runner). Wiring a CI step needs a runner trial first - follow-up.
- The 145 exemptions are triage debt tracked in `.agent/memory/issues-backlog.md` (TEST-COVERAGE).
- Three tests mutate tracked files when run in-tree and are exempt until isolated (test-aq-loop-review-repair-guard, test-dashboard-advanced-runtime-summary, test-radar-ingest).
