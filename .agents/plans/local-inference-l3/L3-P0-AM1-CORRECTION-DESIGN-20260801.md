# L3-P0-AM1 Provenance-Shadow Correction Design

Status: `PREPARED_ONLY — CORRECTION DESIGN; NO ACTIVATION`  
Base HEAD: `17f899bf838973c755ab7a3e6095ec04a2e74220`  
Supersedes for remediation only: the consumed/non-replayable authorization
`2d06c396cae2dfdbe2bbbb00d8879ae23df49b244e1cef623c1296b1aa85b47c`.

## Scope

AM1 corrects the failed L3-P0 candidate without adopting any live inference
path. The correction ceiling is the nine valid candidate paths below plus one
authorized destructive relocation: remove the untracked, unauthorized
`config/testing/local-inference-l3-p0-golden.json` and create its replacement at
`scripts/testing/fixtures/local-inference-l3-p0-golden.json`. That removal is
not authorized by this document; it requires an owner activation that explicitly
names destructive cleanup/relocation authority.

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
| `config/testing/local-inference-l3-p0-golden.json` | `5e82d17e32586d5b8353b0386a08d1dec5270c1e02895386464c87d5a35d6452` REMOVE only under explicit destructive authority |
| `scripts/testing/fixtures/local-inference-l3-p0-golden.json` | NEW replacement fixture |

No other path, including L2B, `delegate-to-local`, aq-chat, API, dashboard,
Phase-0, Nix, services, persistence, telemetry, provider, network, or runtime
paths may change.

## Exact correction contract

1. Required trusted fact types are exactly `authenticated_principal`, `role`,
   `approval_or_lease`, `profile`, `eligibility`, `budget`, `path`, and `clock`.
   Every envelope uses a bounded category, named producer, nonempty immutable
   producer revision, opaque `evidence_ref`, `status`, and `value_digest`; it
   carries no raw `value` or raw capability-bearing data.
2. The producer-revision-set is a required resolved input, not an ignored schema.
   Every fact producer/revision must occur exactly once in the canonical set;
   duplicate, missing, stale, or unordered entries fail before a digest.
3. Canonical digest bytes are UTF-8 NFC-normalized JSON with recursively sorted
   object keys, no duplicate keys, shortest JSON separators, and no NaN/Infinity.
   The golden vectors must prove identical semantic input gives identical digest
   and each provenance, projection, metadata, and plan mutation changes the
   required digest.
4. Every schema is recursively closed (`additionalProperties: false` at every
   object boundary) and every success, unavailable result, plan, projection, and
   observation is schema-validated by the hermetic tests. Schemas must require
   complete fields rather than merely a subset.
5. Observation metadata is a closed, digest-bound input. The final observation
   contains all design fields: schema id, observation/request/trace refs,
   sequence/time, producer/revision, resolved-plan and legacy-observation
   digests, compatibility adapter, decision, typed error, divergence findings,
   provenance refs, and the three constant non-authority flags. Metadata affects
   the final observation digest but not the resolved-plan digest.
6. Unavailable construction is internal-only. No public arbitrary failure object
   or caller-controlled failure constructor exists; the resolver maps only its
   validated enum and expected fact type to the closed unavailable contract.
7. Tests exhaustively reject raw values; capability words/objects; raw task,
   route, grant, tool, CLI, environment, provider, endpoint, process, network,
   filesystem, clock-generation, and persistence dependencies; malformed digest
   references; duplicate/unsorted producer sets; non-NFC strings; unknown fields;
   missing observation fields; and unauthorized fixture location. Source-import
   checks and behavioral tests both enforce purity.

All outputs remain `shadow=true`, `non_authoritative=true`, and
`no_live_cutover=true`; no successful result grants authority or execution.

## Acceptance and hard stops

Before a first write, independently recheck every hash, HEAD, original design,
the failed-candidate state, absent replacement path, clean index, and no overlap.
Run only hermetic schema/contract tests, Python syntax, `git diff --check`, and
permitted static gates. Stop on any drift, extra path, inability to grant the
fixture removal explicitly, schema registration need, non-pure dependency, test
failure, or request for live/runtime/provider/network/deployment activity.

`RECORD: PREPARED_ONLY AM1 correction design; the prior authority is consumed and non-replayable.`
