# L3-P0-AM3 Current-HEAD Correction Authorization

Status: `PREPARED_ONLY — ACTIVATION-READY; NOT ACTIVATED`  
Authorization ID: `auth-local-inference-l3-p0-am3-20260801`  
Bound HEAD: `99621ace21f1c60d7908ce82d8928f5001081592`

## Exact chain and supersession

AM3 binds correction design SHA-256
`de3dd023e47e535cd53af8e25b1d69e30657b83b90caa2de477c09e7cc9b7da1`,
original design `9363c2aa9942d345cb58d3e9ee98162c15ca23226c248358229e110158405f23`,
and independent PASS `0282e12f7eff556c5d886269033b43070a3d2263d9e4e528a34d3d5300dd82dc`.
The correction design remains semantically and byte valid. The original activated
authorization is consumed/non-replayable. These prepared predecessors were never
activated and are superseded for HEAD drift only:

- `.agents/plans/local-inference-l3/L3-P0-AM1-IMPLEMENTATION-AUTHORIZATION-20260801.md`
  — SHA-256 `00f21aa455b41461c1eedc0a3ef669488588e6c77dbcad3475ec4a1763c44b62`;
- `.agents/plans/local-inference-l3/L3-P0-AM2-IMPLEMENTATION-AUTHORIZATION-20260801.md`
  — SHA-256 `a285a6015563b7d7cac2eac853b931540044712fa71945c0f3a39ea527535841`.

## Exact candidate ceiling

The only future writes/removal are these nine edits, the one NEW fixture, and
one explicit erroneous-fixture removal:

| Path | Current SHA-256 / operation |
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
| `scripts/testing/fixtures/local-inference-l3-p0-golden.json` | absent; NEW |
| `config/testing/local-inference-l3-p0-golden.json` | `5e82d17e32586d5b8353b0386a08d1dec5270c1e02895386464c87d5a35d6452` REMOVE/RELOCATE |

All five no-edit anchors rehash exactly: transport
`e42fb5480385f791a8cd43bb94802499eddb5ef335ef0228d749a828d7130405`;
L2B test `79425baf3c58cf764c75a32fc597755618ac69377032d52d99d41295c69b4e82`;
Aistack route `5e736402eb51bf7522902fd4803cd9dac099ce197ec15df4bfec6ec5a1e6d2fd`;
dashboard `ea88c43e2509fd9d5a1c1dbf408c87a48538cd96a33fee2c42ad79f1c347c0be`;
and Phase-0 `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1`.

## Required fresh owner activation

Activation must explicitly state: “I authorize removal/relocation of the
unauthorized untracked `config/testing/local-inference-l3-p0-golden.json` into
the authorized fixture path, and grant the named implementer an exclusive
source/worktree/commit-owner lease for this exact AM3 ceiling, bounded to no
more than 30 minutes after first write.” The lease must cover every EDIT, NEW,
REMOVE/RELOCATE, and NO-EDIT path above plus repository index and commit
mutation; prohibit concurrent test, Tier-0, Git, formatter, agent, or other
writer activity; and remain observable through the post-validation hash capture.
Preflight and post-validation must prove an empty staged index, no overlap, the
bound HEAD, and every bound hash. It must name a distinct implementer and
independent flagship reviewer. The implementer may not stage or commit; a
separately named commit owner may do so only after independent PASS.

The correction must enforce digest-only values/value digests; the required
producer revision set; NFC deterministic canonical JSON; recursive closed schema
validation; complete digest-bound observations; internal-only unavailable
construction; and exhaustive forbidden-capability/digest/metadata tests. It is
offline only. First successful write or exact candidate report consumes the
grant. Drift, overlap, an eleventh path, removal without the quoted authority,
or a failing test is a stop requiring another authorization.

No live/runtime/provider/network/deployment, staging, commit, API, dashboard,
Phase-0, Nix, service, persistence, telemetry, L2B, `delegate-to-local`, or
aq-chat action is authorized by this record.

`RECORD: PREPARED_ONLY AM3 is current-HEAD activation-ready; no activation occurs here.`
