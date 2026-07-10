# AQ-OS Refoundation Cycle 0 — Evidence Manifest

**Manifest status:** provisional, human-readable Cycle 0 planning evidence  
**Recorded:** 2026-07-10T04:39:10Z  
**Repository commit at initial observation:** `717f5d7ed0e09a0324f055613da05956763c66e8`  
**Environment:** shared, dirty worktree with concurrent agents; NixOS local host  
**Integrity rule:** SHA-256 of exact raw file bytes. These hashes prove integrity, not authorship.

## Planning subjects

| Subject | SHA-256 | Status |
|---|---|---|
| `.agent/PROJECT-AQOS-CYCLE0-TRUTH-PRD.md` | `852bae9a91c6e74aa11aec56c0d26a6b053bad51ae33a62e8f0d765eb2dbdce4` | draft / request revision |
| `CONSOLIDATED-PLAN.md` | `e7e498e86b45e874047f7555ee93b57d8629d0d282ec64543a5725c1c78ec634` | draft / request revision |
| `STATE-CONTRACT.md` | `d38ef59abc6eb037684969d77ae3e1c2f515facf5b3f92a7e9be1c4737f62052` | proposed owner policy / request revision |
| `EVIDENCE-ALGEBRA.md` | `389311e1e6d949560751c03061af9c0e411047f714a7004b1b3cd0e86cd1b266` | proposed thresholds / request revision |
| `CURRENT-AUTHORITY-INVENTORY.md` | `97d4b5a5ee5bab16cf2fbdbc0f04ec754ba24546dbb0a33c8ad1ab2fa15d4a4c` | source-verified current-state inventory |
| `C0.2-SURFACE-INVENTORY.md` | `f195233fe80ebad07f3480fef27f61bb5ac9cb2b358b83818bf3169f378062ae` | frozen discovery snapshot |
| `THREAT-REGISTER.md` | `4c0a340f38f00cbe6fb2e20d834ce6b0a5442f2483d0c43639611c3ef80867c4` | draft / request revision |
| `DECISION-LOG.md` | `d2e48f54514254403c48788dd66f5bf10c5a89aec02749f511f718706304cb87` | draft / request revision |
| `REFERENCE-AND-MIGRATION-COMPARISON.md` | `d28d027c821a900845e9866a610a7f3d63fcd538f7bf7185950a97b0a90f54b5` | source-backed hypothesis |
| `EVIDENCE-MANIFEST.json` | `ca1b0935838ae8037c099fc642b3a6d13fbb193bad15fa6c6c383092eaae3248` | machine-readable provisional evidence |

Any later edit invalidates the corresponding hash and requires fresh review. `PACKAGE-ROOT.json` binds
these subjects plus this human manifest; reviews must target that descriptor's external SHA-256.

## Evidence records

| ID | Class | Source/command | Observed | SHA-256 | Claim supported | Freshness and limitations |
|---|---|---|---|---|---|---|
| E-001 | `verified_live` | `scripts/ai/aq-collab-round collect --round aqos-refoundation-cycle0` | manifest transition 2026-07-10T04:22:51Z | round manifest `90061e1256e862a347912c203911bd4459fb28d1dee45f59631b975a591a89c1` | Collector produced `CONSENSUS_LOCKED` from empty persisted contributions and null aggregate evidence; command stdout recorded `ABSTAIN: 3` in the human aggregate | Dirty shared worktree; manifest proves invalid state, while the tally remains human-recorded until immutable stdout exists |
| E-002 | `verified_source` | `scripts/ai/lib/round_aggregate.py` | 2026-07-10 | `87dfe7da3d037113219f4136d35e7771b2fbf8dd46326b7f6f3c87e4f9972da5` | Lock depends on no conflicts plus lane-status quorum, not accepting substantive contributions | Source may change under concurrent work; rehash before implementation |
| E-003 | `verified_source` | `scripts/ai/lib/round_state.py` | 2026-07-10 | `77dd39d47e407594fe2aa0ef46abb50130f830ba0a05bde883713b76ac1ab832` | One `CONSENSUS_LOCKED` state currently precedes assignment and does not separate direction/plan/authorization | Same limitation as E-002 |
| E-004 | `verified_source` | `.agent/analysis/2026-07-09-full-system-analysis.md` | 2026-07-09 | `b65975b3842b7bd81a9f6a9c0f067dd9b14c1c45310d802e3a7ccebd85c149d5` | Broad system health coexists with scorer, backlog, scheduling, observability and authority gaps | Point-in-time analysis; individual live metrics require refresh |
| E-005 | `research_required` | historical `latest-qa-results.json` digest; bytes not preserved | observed 2026-07-10T04:27:48.706Z | historical digest `de73034131a29ebbdd441a5a673ddb958c55c32f6a50005ffec39b23479656d0` | A transient snapshot reported 162 pass / 0 fail / 10 skip | Condition `MISSING`: mutable file changed and old bytes were not retained, so the total cannot be independently reviewed and supports no certification |
| E-006 | `verified_live` | local lane heartbeat sidecar | 2026-07-10T04:40:56Z | `9e439ea74941178ae0db1a9f3999396d6141d4d57af4dc900a7af3664f994cc6` | Original local reviewer was still process-alive/waiting immediately before terminal failure | Point-in-time liveness proves neither completion nor agreement |
| E-007 | `verified_live` | headless Codex output file | created 2026-07-10T04:03:55Z | `1aa26269eb1cc57f86b235a03cda53c004edb5b1e9fc99d4da4f00843293d721` | Original lane produced only the stdin-read marker and no substantive proposal | Exit status comes from registry monitoring; recovered proposal is same-family only |
| E-008 | `research_required` | Antigravity inbox request | request file hash only | `acbc4584bb927da5af7d53ad80b4ddd06405dbb1347a9d5a2a64ab30b4080270` | Request was issued; no durable returned output was discovered | The request hash cannot prove provider receipt or absence; contributes zero approval weight |
| E-009 | `verified_source` | provisional aggregate before new package | 2026-07-10 | `e704c22b1c4fcb032d44177d45d0e9d6ffdd6eba874bd655a96d54e54860a71a` | Human artifact says request revision while machine says locked | Aggregate will need a new hash after reconciliation |
| E-010 | `verified_live` | local lane terminal progress sidecar | 2026-07-10T04:41:09.490591Z | `506387153f1833302427d92ba55cabc6249295ff7bd5e44b11190b7fb78e92da` | Local lane failed after 2,233.4 seconds and four tool calls with empty result because switchboard connection was refused | Subsequent switchboard health succeeded, so failure is transient-path evidence, not current service-down evidence |

## Evidence condition assessment

| Claim | Condition | Assessment | Gate | Reason |
|---|---|---|---|---|
| Direction is ready for review | `VALID` | `WARN` | `DEGRADED` | Same-family expert convergence is substantive but not model-diverse quorum |
| Plan is ratified | `MISSING` | `UNKNOWN` | `BLOCKED` | Pending lanes and no reviews of exact PRD/plan hashes |
| Implementation is authorized | `UNAUTHORIZED` | `UNKNOWN` | `BLOCKED` | No explicit owner authorization and machine state is invalid |
| Phase-0 integration is broadly available | `VALID` with provenance limitation | `WARN` | `DEGRADED` | Current snapshot is green but immutable run provenance is absent |
| Effectiveness/trust is certified | `CONFLICTING` | `UNKNOWN` | `BLOCKED` | Report/dashboard semantics and live evidence gaps disagree |

## Provenance limitations

- Internal architecture, trust and execution workstreams were parallel Codex-family agents. They are
  expert synthesis inputs, not independent model-family votes.
- Claude slot artifact is a Codex-orchestrator proxy. It contributes no separate model diversity.
- The worktree contains concurrent user/agent changes, and the observed commit moved during the broader
  session. No evidence here claims a clean-tree reproduction.
- Live command stdout was not captured into immutable CAS artifacts. Claims supported only by sidecars
  are bounded accordingly; unsupported absence and the overwritten QA total are `research_required`.
- No external research claim is treated as verified in this manifest. Cycle 1 dependency choices need
  their own primary-source and live resource evidence.

`GATE: BLOCKED — planning package is ready for independent review, but plan ratification and
implementation authorization have no valid evidence.`
