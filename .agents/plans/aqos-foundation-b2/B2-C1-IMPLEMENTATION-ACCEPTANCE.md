# Foundation B2-C1 Amendment 2 implementation acceptance review

**Review date:** 2026-07-18  
**Reviewer:** Codex sub-agent `/root/b2_c1_acceptance`  
**Role:** independent read-only architecture, security, privacy, SRE, and contract reviewer  
**Review type:** fresh exact eight-file Amendment 2 acceptance  
**Final verdict:** **PASS**

## Authority and exact subject

The governing authorization is
`db657588b7d256ad2c518958b2875cc1fa46eea6955421043930d9c62bdc5093`; its independent review is
`49e6d3b1ae7bd18d2a708401062e62c3258dcca1683d31ccc5a648b133b26b56`. Owner activation names
`codex-subagent-b2-c1-implementer` for `2026-07-18T10:48:05Z` through
`2026-07-19T10:48:05Z`. The read-only blueprint remains unchanged at
`12ba465a5ede653579ac52752558ed9068fe0bbfd407dbc44cb2b80b70c72374`.

| # | Path | SHA-256 | Result |
|---:|---|---|---|
| 1 | `config/schemas/workflow-shadow-contracts.schema.json` | `16152812b25c02455ebbef15fa83ff606634ca58155206c4610ed2292ddbbf35` | exact; PASS |
| 2 | `config/workflow-shadow-phase-tokens.json` | `5d63f844737037db9ea6d2e4a0b3e6488245e655a0058063db75feccaeb807ef` | exact; PASS |
| 3 | `scripts/ai/lib/workflow_shadow_contract.py` | `2523c66c8cc675c6470ec3e9c536ab0efdf78e0587c4c1b09ef9bea27e922266` | exact Amendment 2; PASS |
| 4 | `scripts/testing/fixtures/workflow-shadow-contract-v1-golden.json` | `c793ed7761fe31b6551c6bc3faf6926bbb95a7c3c2b080c2876779fc1a8f5d4b` | exact; PASS |
| 5 | `scripts/testing/test-workflow-shadow-contract.py` | `49436f6f202883d10f7e513af74bf0978067253c06b7aa06ba0983d349625af7` | exact Amendment 2; PASS |
| 6 | `scripts/testing/harness_qa/phases/phase0.py` | `fc43b959e2bbe6eb6753736df4818265616edace598d361fc93a5ddb929bf193` | exact; PASS |
| 7 | `scripts/ai/_aq-qa-bash` | `706f9e11a789c06090fdc43ce2c951cf274035062111af3e6f910f12b8d74704` | exact; PASS |
| 8 | `config/validation-check-registry.json` | `13e14031008becdc15c814428853244b94490853ed05e270dee8862e15900d02` | exact; PASS |

The implementation remains within the exact eight-file ceiling. No candidate byte was edited by this
reviewer.

## Amendment adjudication

Both prior revision findings are resolved:

1. Production library source contains none of the fourteen quoted raw blueprint identifiers. The
   test contains an explicit location guard derived from the reviewed registry inputs.
2. The library freezes the exact ordered fourteen-member opaque-token tuple. Registry validation now
   requires every entry to satisfy all of: closed shape, frozen source path/digest, fixed domain,
   fourteen-entry cardinality, identifier syntax, integer index equal to list position, unique
   ID/index/token, domain-token recomputation, and equality to the frozen opaque token at that index.

The prior substitution attack was rerun independently. Entry zero was replaced with
`arbitrary_phase`, its otherwise valid domain token was recomputed, and the frozen source assertion
was retained. Both `validate_phase_registry` and `lookup_phase` rejected with the privacy-safe
`phase_registry_collision` reason. The substituted value was not echoed.

## Contract and threat-model results

- Five independently versioned closed Draft-2020-12 variants: **PASS**.
- Unknown and cross-variant versions/fields: **rejected**.
- NFC UTF-8, sorted keys, no insignificant whitespace, integer-only canonical oracle, deterministic
  process-independent bytes/digests: **PASS**.
- Exact 2 KiB/2 KiB+1 event boundary and queue capacities 0/64/65: **PASS**.
- Exactly fourteen stable, collision-free, index-aligned opaque phase tokens bound to the frozen
  blueprint digest: **PASS**.
- Missing, duplicate, colliding, unknown, free-form, and correctly recomputed substituted phase
  registry values: **rejected**.
- Empty-object allowlist mapper, privacy canaries, raw/model phase absence from mapped outputs,
  health, canonical bytes, digests, and exception text: **PASS**.
- Seven total decisions—insert, advance, exact replay, gap, stale, collision, terminal conflict—plus
  monotonic revision, idempotence, terminal uniqueness, and no fabricated event/delivery emission:
  **PASS**.
- Import-side-effect-free, standard-library-only production module; no database, SQL, filesystem
  write, environment, network, subprocess, thread, task, worker, service, dashboard, deployment,
  traffic, cutover, cleanup, or rollback path: **PASS**.
- Fixture-only health reports exactly `authority=legacy_json_authoritative`, `aq_qa=ready`, and
  `web_dashboard=not_wired`: **PASS**.
- Python and Bash Phase-0 registrations both identify check `0.10.41`; validation registry entry is
  bounded to the focused offline command: **PASS**.

## Executed evidence

- `python3 scripts/testing/test-workflow-shadow-contract.py` — **PASS**, 7 groups.
- Independent opaque-sequence/recomputation/source/substitution/raw-location adversarial script —
  **PASS**.
- `python3 -m py_compile` for library, focused test, and Phase-0 — **PASS**.
- `bash -n scripts/ai/_aq-qa-bash` — **PASS**.
- JSON parse of schema, registry, fixture, validation registry, and blueprint — **PASS**.
- `jsonschema.Draft202012Validator.check_schema(...)` — **PASS**.
- Static prohibited import/I/O/process scan — **PASS**.
- `aq-qa 0 --machine` — **PASS**, exit 0.

## Serialized integration gate

After both parallel candidate lanes stopped mutating, the orchestrator ran
`scripts/governance/tier0-validation-gate.sh --pre-commit` against the combined candidate. Result:
**PASS — 23 passed, 0 failed, exit 0**. The reviewer then reverified all eight B2-C1 Amendment 2
hashes and the read-only blueprint hash; every byte remains identical to the exact subject above. No
candidate defect or outstanding acceptance gate remains known.

Legacy JSON remains authoritative. Nothing in this review activates a database, state writer,
runtime hook, service, dashboard, deployment, traffic, cutover, cleanup, rollback, or later slice.

`VERDICT: PASS — Amendment 2 resolves both phase-registry findings; all exact-hash candidate-local,
Phase-0, aq-qa, and serialized Tier-0 gates pass, and the eight-file pure-contract candidate is
accepted for orchestrator integration with legacy JSON remaining authoritative.`
