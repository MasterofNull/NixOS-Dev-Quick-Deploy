# Foundation B1 L2B-B Recovery and Re-Freeze Amendment 1

**Prepared:** 2026-07-22T11:25:04Z

**Status:** `PREPARED_ONLY — SUSPENDED BY CONCURRENT OWNER REACTIVATION AND SUBJECT DRIFT`

**Recovery subject:** stale task `l2b-b-20260720`

**Prepared repository HEAD:** `142ad8b7ef83808430ee5df70812e9ae6d519c3c`

**Supersedes for future activation:** the expired activation of authorization
`468899d47fa107d87db10f3d45491d395472a46071116aa8fb9a66a142b651fe`

## 1. Recovery disposition

The prior L2B-B task is safely stale, not resumable:

- `.agent/collaboration/PENDING.json` records `l2b-b-20260720` as `running`, dispatched
  `2026-07-21T05:01:33.152672Z`, but no matching delegation-registry row, output log, live process,
  write/validation/completion pulse, or candidate report exists.
- Its owner activation window ended at `2026-07-21T20:15:00Z`.
- No implementation bytes landed. The three tracked implementation targets are clean at the
  prepared HEAD, and the two intended new implementation artifacts remain absent.
- The historical flagship review is an existing untracked governance record that predates the
  stale dispatch. It is not an implementation output and must not be labeled `NEW` or edited by an
  implementer.

The old task ID, activation window, and authorization hashes
`a9402e60408544c9b36d396ec2b322a3d3c75ab3f890cf25d21820b925b377b3`,
`b9055bb6a763189fd0b5fbc054ead4fc6a41d41ed117181039f0ce67d62f7cb8`, and
`468899d47fa107d87db10f3d45491d395472a46071116aa8fb9a66a142b651fe` are historical-only and
non-replayable. This amendment does not mark the stale projection closed; the orchestrator must do
that through the canonical pending writer before any new dispatch.

## 2. Exact prepared baseline

| Classification | Path | Prepared state / SHA-256 |
|---|---|---|
| MODIFY | `scripts/ai/lib/local_inference_transport.py` | `37e6d76ec73b00ffc7b759f94e34e10e85bfee5c676b8fbc15527cfaa5309bdc` |
| MODIFY | `scripts/testing/test-local-inference-l2b.py` | `2ceee6bbed15ab3722902309f08976c827c5685819bcc25e6eb7daa5587f029d` |
| MODIFY | `assets/dashboard.js` | `ab2418478f62e068b665570902b77f0dab596edae84c178a648ead14f9e283b7` |
| NEW | `config/schemas/local-inference-payload-v1.json` | absent |
| NEW | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | absent |
| FROZEN EXISTING GOVERNANCE INPUT — NO EDIT | `.agents/plans/local-inference-l2b-b/L2B-B-FLAGSHIP-REVIEW.md` | `2e41981f6bce0250a3bda14f599cf65e7c93301c022428528a07809ed589abda` |
| FROZEN HISTORICAL AUTHORIZATION — NO EDIT | `.agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION.md` | `468899d47fa107d87db10f3d45491d395472a46071116aa8fb9a66a142b651fe` |
| FROZEN RECOVERY REVIEW INPUT — NO EDIT | `.agents/plans/stream-auth-rereview/claude.md` | `c2de6df2124c381abb6791162b3951f59b045ec55e21d5e06b5394bd9c8ae6a0` |

The old authorization named base `66391367`; that base is retired. In particular,
`assets/dashboard.js` changed by 159 additions and 5 deletions between that base and the prepared
HEAD. Only the hashes in this section may seed a new grant.

## 3. Re-frozen implementation objective and boundary

The recovery slice is an exact five-file implementation candidate:

1. Add pure, deterministic normalization for local chat and completion payloads: Unicode NFC,
   deterministic object-key order, rejection of non-finite numeric values, and schema validation
   before any dispatch boundary.
2. Expand the existing offline L2B focused oracle from 8 to 14 deterministic checks covering chat,
   batch/completion, malformed input, canonicalization, schema rejection, and dashboard projection.
3. Add the payload schema and golden fixtures, and render the already-produced health state in the
   existing dashboard card without adding an endpoint, poller, listener, or authority.

Hard boundaries:

- pure transformation and static/offline tests only;
- no provider call, live inference, network, DNS, socket, credential, bearer-token, database,
  production subprocess, service, Nix, deployment, restart, traffic, or filesystem-topology action;
  only the authorization's exact offline validation processes may execute;
- no new route, listener, store, writer, queue, process owner, environment variable, port, URL,
  package dependency, or runtime model allocation;
- no edit outside the five implementation paths, including no edit to either governance record;
- no weakening of existing L2A/L2B-A validation or dashboard fail-closed behavior;
- no staging, commit, deployment, delegation, or self-acceptance by the implementer.

The 27 GB concurrency statement remains a preserved invariant, not permission to allocate or probe
VRAM. The candidate may validate already-present payload metadata but may not load a model or create
a new concurrency authority.

## 4. Governance corrections and required owner decisions

This amendment proposes the following explicit owner decisions:

1. Retire the expired `l2b-b-20260720` task and its activation as non-replayable.
2. Replace the old six-item mixed inventory with an exact five-file implementation ceiling; treat
   the existing flagship review only as frozen historical governance evidence.
3. Select `codex-subagent-l2b-b-am1-implementer` as the cheapest currently eligible lane: the local
   lanes cannot complete a five-file shell-validated coding slice, Gemini auto-edit cannot execute
   the required validation, and no authenticated headless Gemini-yolo lane is established. Codex
   has bounded patch and shell capability; Claude remains the higher-cost fallback.
4. Require a fresh independent exact-subject authorization review before activation and a fresh
   independent exact-candidate acceptance after implementation. Neither the stale flagship PASS nor
   the path-correction `REQUEST_REVISION` is reusable.

No decision above is effective merely because this prepared record exists. The owner must ratify the
exact authorization hash in a separate activation record after the required review PASS.

## 5. Post-preparation concurrent activation and automatic suspension

At `2026-07-22T11:29:15Z`, before AM1 received an independent review or owner activation, its exact
pre-write oracle failed. After the baseline was measured:

- PULSE line 346 / event `6b942fdad3e04f2eba8b84dec6eb8ec0` recorded a new owner activation of
  the historical `468899d4...` authorization for `claude-subagent-l2b-b-implementer`, window
  `2026-07-22T04:20:00Z` through `2026-07-23T04:20:00Z`.
- Event `f5160dfc90a3496fac96d6336fe58f1e` recorded that implementer as in progress.
- `scripts/ai/lib/local_inference_transport.py` drifted from AM1's frozen
  `37e6d76ec73b00ffc7b759f94e34e10e85bfee5c676b8fbc15527cfaa5309bdc` to observed foreign SHA-256
  `4b73855ef93ad2079fa3b4eeb201d2c32f2e969df0ca354cfddffa95577083d9` (`+187/-0`).

Those bytes were neither authored nor accepted by this recovery-package author and are not absorbed
as a new baseline. AM1 is automatically suspended and must never be activated or repaired in place.
The owner must decide whether the separately activated historical-auth candidate continues to its
own acceptance gate or is halted and quarantined. Only after that candidate has an explicit
disposition may a newly numbered AM2 remeasure the tree and seek fresh review.

`RECORD: PREPARED_ONLY/SUSPENDED recovery evidence; no implementation, staging, commit, provider,
live, or network authority is granted; AM1 is non-activatable after concurrent subject drift.`
