# AQ-OS Refoundation Cycle 0 — Evidence Manifest

**Manifest status:** provisional, human-readable Cycle 0 planning evidence  
**Recorded:** 2026-07-10T04:39:10Z; recovery amendment 2026-07-11  
**Repository commit at initial observation:** `717f5d7ed0e09a0324f055613da05956763c66e8`  
**Environment:** shared, dirty worktree with concurrent agents; NixOS local host  
**Integrity rule:** SHA-256 of exact raw file bytes. These hashes prove integrity, not authorship.

## Planning subjects

| Subject | SHA-256 | Status |
|---|---|---|
| `.agent/PROJECT-AQOS-CYCLE0-TRUTH-PRD.md` | `c73d09eb3ae20ea529b9acc22bdca147545bcfd1c2a7c470a622a12f654cf36a` | draft / request revision |
| `CONSOLIDATED-PLAN.md` | `0167fe3fcebc60fa2b2674eb1ae5cbb6255adf2ded209060730ce7e7b044e568` | recovery amendment / request revision |
| `STATE-CONTRACT.md` | `f3500892f1528f411b60af1d5c5fddf91095b548af27d330d2697e74c4f7af22` | proposed owner policy / request revision |
| `EVIDENCE-ALGEBRA.md` | `389311e1e6d949560751c03061af9c0e411047f714a7004b1b3cd0e86cd1b266` | proposed thresholds / request revision |
| `CURRENT-AUTHORITY-INVENTORY.md` | `97d4b5a5ee5bab16cf2fbdbc0f04ec754ba24546dbb0a33c8ad1ab2fa15d4a4c` | source-verified current-state inventory |
| `C0.2-SURFACE-INVENTORY.md` | `cdd75303f74c662bc82df4900197f0b3f913dbd2c0594d68cf2ff3a90adb7dc7` | amended recovery snapshot / request revision |
| `THREAT-REGISTER.md` | `025fd33a3335632ecca7c3dc0716d840b01f65e3304e41ba490347abe39c1e35` | recovery threat added / request revision |
| `DECISION-LOG.md` | `a26683426316e6b02d1d9478167b12e8225091ca9de51a1650616af5821dbf8c` | recovery decision added / request revision |
| `REFERENCE-AND-MIGRATION-COMPARISON.md` | `d28d027c821a900845e9866a610a7f3d63fcd538f7bf7185950a97b0a90f54b5` | source-backed hypothesis |
| `EVIDENCE-MANIFEST.json` | `21fe91846e6205b967e201f1948d47aac5ac1fcf00f440d8a66dd917297d958d` | machine-readable recovery evidence |

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
| E-011 | `verified_source` | `REVIEW-FABLE5.md` | 2026-07-10 | `dda610d6dbeea3ac96ed2cf8eb236df8ea03a826f5c28595dbef4b0663e8b89b` | Independent Anthropic review returned `APPROVE_WITH_CHANGES` on predecessor/review-pin bytes | Findings are valuable; review does not target the new root and carries zero current approval weight |
| E-012 | `verified_source` | `antigravity-findings-review.md` | 2026-07-10 | `eca6e691f644a17d9e7c2a4c1e43c7aa650090d5b465d2773a601c0244e6e962` | Independent Gemini review returned `APPROVE_WITH_CHANGES` on root `2b905b24…` | Under `STATE-CONTRACT.md`, conditional review never approves; amendments require fresh `APPROVE` of the new root |
| E-013 | `verified_recovery` | `.agents/archive/c02-recovery-20260711/telemetry-symlink.metadata.json` | 2026-07-11 | `b6efd58a15e88629dbeed29a74ca1fb75a70f9260fc6b1a57cf11fd9b18c38ea` | Unauthorized telemetry symlink metadata was captured inertly, the live link removed, and the tracked repo projection restored without modifying deployed telemetry | Link-object archive scan could not complete because the scanner dereferences external targets; limitation is recorded in the companion README |

## Evidence condition assessment

| Claim | Condition | Assessment | Gate | Reason |
|---|---|---|---|---|
| Direction is ready for review | `VALID` | `WARN` | `DEGRADED` | Same-family expert convergence is substantive but not model-diverse quorum |
| Plan is ratified | `MISSING` | `UNKNOWN` | `BLOCKED` | Pending lanes and no reviews of exact PRD/plan hashes |
| Implementation is authorized | `UNAUTHORIZED` | `UNKNOWN` | `BLOCKED` | Prior C0.2 authorization is suspended; amended package requires a new root, fresh reviews and new owner authorization |
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

`GATE: BLOCKED — recovery amendment is ready to freeze, but fresh exact-root reviews and a new C0.2
implementation authorization are required.`
