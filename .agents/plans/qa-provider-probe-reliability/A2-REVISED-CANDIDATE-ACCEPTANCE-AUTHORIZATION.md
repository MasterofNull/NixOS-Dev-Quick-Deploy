# QPPR A2 REVISED candidate — acceptance authorization

**Status:** PREPARED_ONLY — fresh Claude-flagship binding acceptance (owner acceptance-lane-directive
2026-07-20). Prepared 2026-07-20, Fable 5 orchestrator (spot-review only; not binding).
**Required reviewer:** fresh Claude flagship, distinct from the Sonnet implementer AND from the first
A2 acceptance reviewer (`claude-subagent-qppr-a2-acceptance-reviewer`, whose REQUEST_REVISION is
retained lineage) and from the A2 rebind reviewers.

## Basis

The original A2 candidate acceptance (`A2-CANDIDATE-ACCEPTANCE.md`) returned REQUEST_REVISION on
criterion 3 only (poller cadence: idle/stale polled at 1s vs design §4.2's 2s); criteria 1,2,4,5,6,7
PASSED. The bounded revision (auth `A2-CANDIDATE-REVISION-AUTHORIZATION.md`
`904201808848526600a2ccd131fe07f2baf782951d8073aef4f4792c551aca25`) fixed exactly that.

## Frozen revised candidate (staged, uncommitted)

| Op | Path | SHA-256 |
|---|---|---|
| MODIFY | `assets/dashboard.js` | `ab2418478f62e068b665570902b77f0dab596edae84c178a648ead14f9e283b7` |
| MODIFY | `scripts/testing/test-dashboard-qa-provider-probe.py` | `ce89a3cc5878e5c3cede353f35f7a5bdb1485bc6d3a936560a45d07f0ec8bde6` |
| FROZEN | `dashboard/backend/api/services/qa_runner.py` | `8e49fa8296ed882a71a94b185f814085a44d16879dab804521ad026e6326cbb7` |
| FROZEN | `dashboard/backend/api/routes/aistack.py` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` |
| FROZEN | `dashboard.html` | `af9d8c81e30f63321f01efd189416a6d4786489932485f889d82484e8f84beae` |

## Acceptance criteria

1. All five hashes match exactly; the three FROZEN files are byte-identical to the first accepted
   review (unchanged by this revision); only the two MODIFY files changed.
2. **The §4.2 fix is correct in the bytes:** the `dashboard.js` poller polls 1s ONLY when
   `availability==="current"` AND `lifecycle_state` ∉ {idle,terminal,unavailable}, and 2s for idle,
   terminal, stale, and unavailable — exactly per design §4.2 (packet line 256). Single-flight
   AbortController(750ms), visibility+lens gating, and setText-only rendering unchanged.
3. **The R3 test genuinely closes the coverage gap:** the new cadence test executes the real
   `_qaProbeRenderState` function (extracted from dashboard.js, run under node) against fixtures and
   asserts actual cadence per state — not merely the `"? 1000 : 2000"` substring — and would fail
   against the old buggy predicate.
4. **Adjudicate the node test dependency:** the R3 test hard-requires `node`. Confirm `node` is a
   genuinely declared/guaranteed package in the environments where this test runs (Tier-0/CI), OR
   that the test skips gracefully when node is absent rather than hard-failing. A test that silently
   fails or errors where node is unavailable is a portability defect — flag it if so.
5. The rest of the originally-accepted behavior is unaffected (backend reader/route/card frozen;
   projection never authority).
6. Re-run fresh: `python3 scripts/testing/test-dashboard-qa-provider-probe.py` (all pass, offline),
   py_compile the test, git diff --check on the two MODIFY paths, secret-scan, and the three existing
   dashboard QA regression suites — no regression. Re-verify runtime-surface adjacency
   (`git log 3396f9df..HEAD` touches no A2 target / A1 runtime surface; governance/doc commits exempt).
7. No prohibited action; nothing staged beyond the A2 five (the delegate-codex quota files staged
   alongside are a separate slice — do not conflate).

On PASS, the orchestrator runs Tier-0 and commits the A2 five-file slice + its full governance chain,
re-verifying adjacency at commit. A REQUEST_REVISION returns to a bounded cycle with fresh hashes.

`RECORD: PREPARED_ONLY. Binding acceptance by fresh Claude flagship; commit only after PASS.`
