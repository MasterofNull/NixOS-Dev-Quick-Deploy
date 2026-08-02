# L3-P0-AM2 Current-HEAD Correction Authorization

Status: `PREPARED_ONLY — NOT ACTIVATABLE: NO-EDIT ANCHOR DRIFT`  
Authorization ID: `auth-local-inference-l3-p0-am2-20260801`  
Bound current HEAD: `502cacd6ca3081ea7a1fce5bb15ad17affa6b687`

## Supersession and exact chain

AM2 supersedes AM1, which was never activated and is stale solely because HEAD
advanced. The correction design remains byte-identical and semantically valid:
`L3-P0-AM1-CORRECTION-DESIGN-20260801.md` SHA-256 is
`de3dd023e47e535cd53af8e25b1d69e30657b83b90caa2de477c09e7cc9b7da1`.
It remains bound to original L3-P0 design
`9363c2aa9942d345cb58d3e9ee98162c15ca23226c248358229e110158405f23`
and independent PASS
`0282e12f7eff556c5d886269033b43070a3d2263d9e4e528a34d3d5300dd82dc`.

The original activated authority
`2d06c396cae2dfdbe2bbbb00d8879ae23df49b244e1cef623c1296b1aa85b47c`
is consumed/non-replayable. AM1 was never activated and grants no residual
authority. This record grants no activation because the source-freeze check
below failed.

## Current candidate state

| Path | Current SHA-256 / required operation |
|---|---|
| `scripts/ai/lib/local_inference_provenance.py` | `6e51dc28a63933c06081d536aeb99cbbb82218b5475dd91dbc737ca5ceee5ebc` EDIT |
| trusted-fact envelope schema | `862765c1ec9c7582909e18502870fd5d6f2ff5cd3fceacf885c840b69c712ca0` EDIT |
| producer-revision-set schema | `21c20f106cb1be9dbde698146d25bb88860aa46af86588286aeac266921a4c8b` EDIT |
| request-projection schema | `b950722aaf0bcdce7cac2b3c20cf0df4dd3990fc48980736b7fd2f0d240b0c6a` EDIT |
| resolved-plan schema | `17739d1be135a2082c5d19367ac0d9e757d5f4a77487f0157fb5a479dbd2db01` EDIT |
| observation-metadata schema | `2b881ae96b7c668b5ae25a9e196bcf6e0e672ea51db76746f05bbfd8834db9ba` EDIT |
| observation schema | `9160cec938f9891202ec4a7d9f656d8f5666cbaed410190f9171b0b3d4b0d7c5` EDIT |
| unavailable schema | `ff74da02adb6351d34a8253d9f60916170d4182ecc423431b970f58aeb4be15b` EDIT |
| `scripts/testing/test-local-inference-l3-p0.py` | `ddfb3acdb3c14c6bfc7688fb3a72de2dd5584983cce01892e276bdb9b33be1b8` EDIT |
| `config/testing/local-inference-l3-p0-golden.json` | `5e82d17e32586d5b8353b0386a08d1dec5270c1e02895386464c87d5a35d6452` REMOVE |
| `scripts/testing/fixtures/local-inference-l3-p0-golden.json` | absent; NEW replacement required |

## Required source-freeze anchors

| No-edit path | Expected/current SHA-256 | State |
|---|---|---|
| `scripts/ai/lib/local_inference_transport.py` | `e42fb5480385f791a8cd43bb94802499eddb5ef335ef0228d749a828d7130405` | exact |
| `scripts/testing/test-local-inference-l2b.py` | `79425baf3c58cf764c75a32fc597755618ac69377032d52d99d41295c69b4e82` | exact |
| `dashboard/backend/api/routes/aistack.py` | `5e736402eb51bf7522902fd4803cd9dac099ce197ec15df4bfec6ec5a1e6d2fd` | exact |
| `assets/dashboard.js` | `ea88c43e2509fd9d5a1c1dbf408c87a48538cd96a33fee2c42ad79f1c347c0be` | exact |
| `scripts/testing/harness_qa/phases/phase0.py` | expected `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1`; current `58904375ba961b2adade5f60f713c63dda69eae61c0da90d8be353dbf8065bc3` | **DRIFT — STOP** |

## Future activation contract, after re-pin and review

A replacement authorization may be activated only by a fresh owner sentence
explicitly authorizing removal/relocation of the unauthorized untracked fixture,
granting a source-freeze/commit-owner lease, and naming a distinct implementer
and independent flagship reviewer. The successor must preserve the complete
AM1 contract: exact fact types; digest-only values/value digests; producer
revision-set enforcement; NFC deterministic canonical JSON; recursive closed
schemas and schema validation; complete digest-bound observation fields;
internal-only unavailable construction; and exhaustive forbidden-capability,
digest, and metadata tests. First successful write or exact candidate report is
single-use consumption; drift, overlap, test failure, or an extra path stops and
requires another numbered authorization.

No staging, commit, runtime, provider, network, deployment, service, API,
dashboard, Phase-0, Nix, persistence, telemetry, L2B, `delegate-to-local`, or
aq-chat action is authorized. This document performs none.

`RECORD: AM2 confirms correction-design validity but is blocked on Phase-0 anchor drift; no activation.`
