# Independent Governance Review — C0.3 Settlement and Tracker AM3

Status: `REVIEW_COMPLETE — NO ACTIVATION GRANTED`  
Reviewer: `Codex independent flagship governance reviewer`  
Review timestamp: `2026-08-01 UTC`  
Reviewed `HEAD`: `17f899bf838973c755ab7a3e6095ec04a2e74220`

## Scope and authority boundary

This is an independent, read-only review of the four submitted records. It does
not activate C0.3 settlement or AM3, authorize a write, staging, commit,
deployment, provider/network action, runtime probe, ref mutation, or closure.
The working tree was shared and dirty; no subject file, index, ref, or runtime
state was changed by this review.

## Submitted-byte verification

| Record | SHA-256 | Verdict |
|---|---|---|
| `C0.3-BATCH-INTEGRATION-INCIDENT-20260801.md` | `c4e4301725b768b6c6a72a6391be99376cdba9501f071c448b9e81c5d74e7f9d` | `PASS` |
| `C0.3-POST-BATCH-SETTLEMENT-DESIGN-20260801.md` | `e7a51ec0fd33f5cb11aca2ee7886e35592b70662b7f6670592bc2735f648f78f` | `PASS — PREPARED_ONLY` |
| `DESIGN-PACKET-AM3-20260801.md` | `2b9c0424f3a9f5ab9774cf5c8868003e76ab0c155c2a7fe15bdb10b57a87ecd6` | `PASS — PREPARED_ONLY` |
| `IMPLEMENTATION-AUTHORIZATION-AM3-20260801.md` | `9f6fbec9b9487f1330ea90d8cf777b5fe2974766f1416c2a6a741418e1640080` | `PASS — PREPARED_ONLY / NOT ACTIVATED` |

The AM3 design hash named by the authorization is the exact submitted design
hash above. Its bound base `17f899bf838973c755ab7a3e6095ec04a2e74220`
equals the reviewed `HEAD`; the C0.3 settlement design base
`ec6fc69b80be4a213e8ad5d23fc1320cf3f2f2af` is an ancestor of it.

## C0.3 incident record — PASS

The incident accurately identifies the integration boundary as commit
`aa0d1a41afa9fc57fb88acc4817bb81734b39a0e`, with sole parent
`734333d0332b06ca9dc62d7c2c6de4b0de318070` and 140 changed paths. Its
historical consumption record resolves to Git blob
`205d412272bf7de3463f17c8da47577669bcdebb`; the extracted historical bytes
hash to `e48ef35574a480c52ef116dbfaf006edb7764fe4ee24a4580541f6814a3cfe09`.

Protected evidence also reconciles exactly:

| Protected ref | Tag object | Peeled commit | Tag-content SHA-256 | Current-HEAD ancestry |
|---|---|---|---|---|
| `aqos-evidence/c0.3/integration-c9fe3974` | `7d1e2b709728e96016781098e39fb2b9903e9dc3` | `c9fe3974753395ed343fed9e922c9c2ea695129b` | `5cbf73ba0359217c21159fd6e70971a3551aea7446b2875af24e9011353d8c50` | non-ancestor |
| `aqos-evidence/c0.3/reviewed-head-d918a21a` | `73e0226a0c8ce94fd2a702eef747e9e3fadeb075` | `d918a21a24081d1329efb0e85d4b3695627b4617` | `163f4b4732ed670ccb5dc7d27a4f6eecbbbfa13711f91578c9d2579bd9b2a85c` | non-ancestor |

That supports the incident's central conclusion: preserved bytes do not create
settlement, and C0.3 remains unsettled. The stated additive-only recovery
boundary is appropriate.

## C0.3 post-batch settlement design — PASS, not executable now

The design preserves the historical record and protected refs, explicitly
retires old Stage-2 authority, requires a new current-HEAD-bound single-use
authority, exact independent byte review before staging, a one-new-file ceiling,
and later post-commit verification as a separate slice. It also makes tracker
live-green evidence, protected-tag integrity, continued non-ancestry, clean
index, and exact staging hard stops. Those controls correctly prevent a
retrospective claim that the prior unauthorized batch settled C0.3.

This verdict reviews the design only. It is not the required future exact-byte
PASS on a settlement record, does not satisfy its tracker live-green dependency,
and does not permit owner activation or Cycle 0 closure.

## AM3 design packet — PASS, not executable now

The packet accurately freezes the five current predecessor files and hashes:

| File | Verified SHA-256 |
|---|---|
| `config/refactor-milestones.json` | `42e9780e639f593b15c7b7a1bc22a13e5bffbad87051909add6ae0f84def3cbe` |
| `assets/aqos-progress-tracker.html` | `afb4630d790eeba75b839e36da7b1feee270935597bcc8d9a22127f1d8b6d0fa` |
| `scripts/testing/test-dashboard-program-progress.py` | `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7` |
| `scripts/testing/harness_qa/phases/phase0.py` | `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1` |
| `scripts/ai/lib/refactor_status.py` | `edc6ee248b0f09d6552a064a040b9545b279f8772889c64d5c7989297641599b` |

The design remedies the observed projector defect: current code counts only
case-normalized `high` for `open_high_issues`; AM3 explicitly requires
case-normalized `Critical|High` while separately surfacing unknown or missing
severity as malformed evidence. It also preserves the C0.3 critical defect,
prevents false C3b-live and C2/C5-deployed claims, and keeps live acceptance
separate from offline candidate validation.

## AM3 implementation authorization — PASS, not activated

The authorization binds the verified AM3 design and the five-file vector,
requires an exact HEAD/design/source recheck, empty index, and absence of an
overlapping writer before any write. Its single-use consumption semantics,
limited ceiling, required negative/offline validation, stop-on-drift rules, and
prohibition on staging or commit by the implementer are sufficient for a
prepared authorization. It correctly excludes runtime, provider, network, Nix,
deployment, live dashboard/HTTP, and `aq-qa` authority; those remain later,
separately authorized gates.

## Required next gates

1. Owner activation must be a new explicit action using the exact reviewed AM3
   authorization, only after rechecking all pinned values and overlap state.
2. AM3 requires independent candidate review and the listed offline evidence;
   no live/deploy claim follows from this review.
3. C0.3 settlement remains blocked until tracker live-green evidence and a fresh
   settlement-specific authority, accepted one-file record, and separate
   post-commit verification all exist.

`RECORD: Independent review PASS on submitted prepared designs/authorization; no implementation or settlement authority granted.`
