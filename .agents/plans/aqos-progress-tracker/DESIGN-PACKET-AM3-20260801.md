# AQ-OS Progress Tracker AM3 — Truthful Current-State Re-pin

Status: `PREPARED_ONLY — INDEPENDENT REVIEW REQUIRED`  
Prepared: 2026-08-01 UTC  
Base HEAD: `17f899bf838973c755ab7a3e6095ec04a2e74220`  
Supersedes: AM2 for implementation mechanics; AM2 is non-replayable.

## Objective

Restore the user-facing tracker, its manifest, projector semantics, focused
tests, and Phase-0 gate to one truthful projection. The July snapshot marker
must become `PROJECTED_CURRENT_STATE`; static tests passing against stale bytes
is a defect, not acceptance.

## Exact five-file future implementation ceiling

| Path | Current SHA-256 | Allowed change |
|---|---|---|
| `config/refactor-milestones.json` | `42e9780e639f593b15c7b7a1bc22a13e5bffbad87051909add6ae0f84def3cbe` | Current track/status/evidence manifest and source hashes. |
| `assets/aqos-progress-tracker.html` | `afb4630d790eeba75b839e36da7b1feee270935597bcc8d9a22127f1d8b6d0fa` | Human projection generated from the same manifest truth. |
| `scripts/testing/test-dashboard-program-progress.py` | `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7` | Replace July snapshot assertions with normalized current-state and negative-vector assertions. |
| `scripts/testing/harness_qa/phases/phase0.py` | `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1` | Change only check 0.10.40 tracker expectations; preserve 0.10.41–0.10.44 byte semantics. |
| `scripts/ai/lib/refactor_status.py` | `edc6ee248b0f09d6552a064a040b9545b279f8772889c64d5c7989297641599b` | Count `Critical` and `High` as high-or-worse; bounded case-normalized enum only. |

No sixth path or substitution is allowed. Dashboard/backend/frontend, health
spider, Foundation C documents, C0.3 records, provider routes, and deployment
configuration are read-only evidence.

## Truth requirements

- Use 19 program tracks unless machine derivation proves a different topology.
- Active: B1, Foundation C, AAF, LEC, and Track S. Blocked: Track V. Do not
  promote revised Foundation C slices into new top-level tracks.
- Pending owner decisions: `0`; authority rows: `10`.
- C2 and C5 are committed and configured live in switchboard, but their newer
  dashboard/health-spider Service Coverage is not live-deployed. Represent that
  distinction explicitly.
- C3b runner/adapter is built but dormant after rollback: runner service/socket
  inactive and adapter `0`. Never label it LIVE.
- C0.3 is `implementation accepted + owner adjudicated; physical convergence
  pending; consumption settlement disputed`. It is not cleanly closed.
- Foundation C C3a-2/C4/C6/runner revisions remain PREPARED_ONLY and unaccepted
  until exact binding review; committed draft bytes do not clear the gate.
- LEC is active, not blocked, because Slice 2b acceptance resolved PASS while
  later adoption remains.
- Remove stale closed findings for F2.5 dormancy, the pre-C2 first-party lease
  gap, and the old LEC REQUEST_REVISION. Preserve task-registry reliability,
  live-deployment drift, runner rollback, Foundation C re-review, and the
  Critical C0.3 settlement defect.

## Projector and validation contract

`open_high_issues` means severity at least High: exactly the closed enum
`Critical|High` after case normalization. Unknown/missing severities do not
silently become High and must be separately visible as malformed evidence.

Focused tests must reject: stale snapshot marker; source-hash mismatch; counts
copied from the old projector; Critical omitted from high-or-worse; unknown
severity promoted; C3b falsely LIVE; C0.3 falsely closed; C2/C5 dashboard
coverage falsely deployed; Phase-0 0.10.41–0.10.44 drift; and normalized
manifest/HTML mismatch.

Candidate validation is offline first: JSON parse, projector unit tests, focused
tracker suite, Phase-0 static test, source-hash reconciliation, and Tier-0. Live
acceptance is later and must prove dashboard HTTP 200, exact deployed asset hash,
visible current state, and the integration `aq-qa` result. A 404, stale Nix-store
asset, blank field, or sandbox-observer failure is not live-green.

## Authority

This packet grants no implementation, staging, commit, deploy, restart, or live
probe authority. After independent PASS, a separately hash-bound single-use
owner activation may authorize one bounded implementer. Any HEAD/target/source
hash drift requires a new re-pin.

`RECORD: PREPARED_ONLY AM3 design; tracker and C0.3 live gate remain open.`
