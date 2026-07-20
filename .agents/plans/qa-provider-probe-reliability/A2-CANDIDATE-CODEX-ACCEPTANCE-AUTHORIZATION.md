# QPPR A2 candidate — codex acceptance authorization

**Status:** PREPARED_ONLY / QUEUED FOR CODEX — activatable by codex on its 2026-07-25 quota return
**Prepared:** 2026-07-20, Fable 5 orchestrator (spot-review only; not binding acceptance)
**Required reviewer:** codex (binding independent acceptance); a session distinct from the Sonnet
implementer and all prior A2 reviewers/preparers.
**Operating model:** staged-for-codex (`.agent/collaboration/CODEX-REVIEW-QUEUE.md` entry 1). Owner
confirmed 2026-07-20 to keep binding acceptance queued for codex rather than antigravity (the
delegate-to-antigravity Gemini lane is down; the no-key IDE-inbox lane has an unresolved attribution
gap). Candidate staged, uncommitted; only after codex `PASS` does the orchestrator Tier-0 and commit.

## Frozen candidate subject (staged, uncommitted)

| Op | Path | SHA-256 |
|---|---|---|
| MODIFY | `dashboard/backend/api/services/qa_runner.py` | `8e49fa8296ed882a71a94b185f814085a44d16879dab804521ad026e6326cbb7` |
| MODIFY | `dashboard/backend/api/routes/aistack.py` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` |
| MODIFY | `dashboard.html` | `af9d8c81e30f63321f01efd189416a6d4786489932485f889d82484e8f84beae` |
| MODIFY | `assets/dashboard.js` | `dcc17d8d1477d3a5f40f6ca5a8fd390cf1bcce3cca0fbd8151d1226ade709a29` |
| NEW | `scripts/testing/test-dashboard-qa-provider-probe.py` | `fe749576fd3abfcbbba17cf2625174a13ecf210b9436acba89f2ff7efb91e254` |

Predecessors (five ceiling, per `A2-ADJACENCY-REBIND-R2.md` §2): `abc105fc…`, `8ae69185…`,
`801a50b2…`, `4e3b44cb…`, test absent. Activation authority = `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md`
(`76b22fb5…`, flagship-PASS rebind `A2-ADJACENCY-REBIND-R2.md` `1156b3fd…`).

## Acceptance criteria for codex

1. Five hashes match exactly; only these five in the A2 candidate set (the 3 delegate-to-codex
   quota-slice files staged alongside are a separate queue entry — do not conflate).
2. **Runtime-surface adjacency re-verified at acceptance time:** `git log 3396f9df..HEAD` and
   `git diff --stat` over that range touch none of the five A2 targets or the A1 heartbeat runtime
   surface (per `A2-ADJACENCY-REBIND-R2.md` §1); governance/doc commits exempt. Any drift = hard stop.
3. Design §4.1/§4.2 implemented in the bytes: `qa_runner.py` pure bounded reader bound only to
   `.agent/qa/provider-probe-active.json` + `qa.provider-probe-active.v1` (O_NOFOLLOW, ≤16KB pre-parse
   cap, non-regular/malformed/unbound/future-dated → `availability=unavailable`; stale >5000ms still
   surfaces last-known per §4.2), never importing `qa-provider-probe.py`; `aistack.py`
   `projection_only=true` early-return on phase 0 before cache/background/evidence/execution (verify
   `_AQ_QA_CACHE`/`_AQ_QA_RUNNING` untouched, no-op on other phases); exactly six accessible rows on
   the existing QA Phase 0 Status card, no new card/route/control; `dashboard.js` single-flight
   AbortController poller, 1s-active/2s-idle, visibility+lens gated, `setText`-only (no innerHTML).
4. Projection is never pass/fail authority; immutable QA result remains authority.
5. **Adjudicate two disclosed judgment calls / deviations:**
   (a) `host_execution` derivation — the design enumerates its four values but not the exact formula;
   the implementer used `dashboard_confined_skip` when `AQ_QA_DASHBOARD_SAFE` truthy (existing var,
   none new) → `terminal` when `lifecycle_state=="terminal"` → else `active`. Check against any other
   A2 sibling doc for a pinned formula.
   (b) governance-ordering deviation — the implementer skipped the pre-edit `aq-event resume` +
   `pending-update add`, ran them post-hoc, and self-disclosed. Bytes are hash-frozen; weigh integrity
   impact (same class as the A1-AM3 rev1 deviation, accepted there).
6. Fresh validation: `python3 scripts/testing/test-dashboard-qa-provider-probe.py` (expect all 18,
   offline — no live provider/network/browser), `py_compile` the two backend files + test,
   `git diff --check` on the four MODIFY, secret-scan; plus the existing dashboard QA regression
   suites (`test-dashboard-qa-singleflight.py`, `test-dashboard-qa-runner-runtime-env.py`,
   `test-dashboard-compat-routes.py`) — no regression.
7. No prohibited action: no sixth file, no new route/card/store/dependency/env var, no live
   provider/network/API/browser, no QA/cache/evidence mutation, no unbounded/symlink read, no
   Nix/service/deploy; nothing staged beyond the five (+ the separate quota entry).

On codex `PASS`, orchestrator runs Tier-0, and commits the five-file candidate + the A2 governance
chain (R1/R2 rebind, both reviews, this authorization) together, re-verifying runtime-surface
adjacency at that time. A `REQUEST_REVISION` returns A2 to a bounded revision cycle with fresh hashes.

`RECORD: PREPARED_ONLY / QUEUED FOR CODEX. Binding acceptance and commit remain unauthorized until
codex reviews on return; A2 live-vetting (real provider/API/browser/deploy) remains separately gated.`
