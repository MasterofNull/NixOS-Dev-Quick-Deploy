# QPPR-C1C-AM1 authorization review

**Reviewer:** `codex-subagent-qppr-c1c-am1-final-reviewer`
**Role:** independent flagship architecture / security / SRE / QA reviewer
**Reviewed:** 2026-07-19
**Verdict:** REQUEST_REVISION

## Exact subjects

| Subject | Required SHA-256 | Observed SHA-256 | Result |
|---|---|---|---|
| C1C-AM1 fail-stop SRE amendment | `bced486ad8af5ced589b71a853ccdffe2927dd5288b650e0c2b48c7eaa924f3c` | `bced486ad8af5ced589b71a853ccdffe2927dd5288b650e0c2b48c7eaa924f3c` | exact |
| C1C-AM1 PREPARED_ONLY authorization | `d9b97c0ca7aee73e437b3bba280eec72c5adce2b567c3066af86109d1a81c702` | `d9b97c0ca7aee73e437b3bba280eec72c5adce2b567c3066af86109d1a81c702` | exact |
| A1-AM3 reproducible rebind | `cf05ef961f64add459161971beea4ec372454c90d2b2c395999aa1444ab6a488` | `cf05ef961f64add459161971beea4ec372454c90d2b2c395999aa1444ab6a488` | exact |
| A1-AM3 roadmap verifier recovery | `0d16fa8e96413e6368aa0dfb4331f5dbfa79e652187eb9d4a98405c33ab0c1a4` | `0d16fa8e96413e6368aa0dfb4331f5dbfa79e652187eb9d4a98405c33ab0c1a4` | exact |
| A1-AM3 roadmap recovery authorization | `6590176eb70ec09296f87bad1a2d4c58220086aa21fe09cc4058d77c35d359ac` | `6590176eb70ec09296f87bad1a2d4c58220086aa21fe09cc4058d77c35d359ac` | exact |

The exact process-owner, lifecycle-test, observer-test, roadmap-recovery, four future correction, and
five frozen candidate hashes named by these subjects match the current workspace bytes. The current
named A1-AM2 design and review also reproduce as
`2d6d7e490b70d307ff6c3d5daf1d89c0ab85bba8cc331e8f8491be1aacb309f9` and
`214a3a99fbadf9895311c7142e63fc4787e1b7fb3fe10c115fbfaac305cc89c6`.

## Architecture and SRE adjudication

The safety-first contract is sound in principle. A barrier returning `completed` or `cancelled` by
the absolute deadline must complete before restoration/redelivery and retain the accepted <=5-second
path. A callback that has not returned cannot be safely killed in-process; holding the lifecycle owner
before restoration, redelivery, lock release, ordinary return, and another provider start prevents
post-redelivery continuation. Explicitly declining any finite redelivery claim for that exceptional
path is honest and requires the named owner SRE ratification. Legacy publication remains unchanged.

One state/evidence detail must be corrected. While a callback never returns, the synchronous lifecycle
owner cannot execute the documented `RUNNING -> CONTRACT_VIOLATION_FAIL_STOP` transition at the
deadline or emit an owner-side fail-stop marker. It remains blocked in `RUNNING`; only an external
observer can infer an overrun from the absolute deadline. The amendment should either define that
external inference as the authoritative fail-stop classification and name its observable input, or
authorize a bounded observer mechanism. Deterministic evidence must separately cover a callback that
returns after the deadline and prove the owner then enters a permanent fail-stop without restoration,
redelivery, lock release, ordinary return, or later provider start. The isolated parent may terminate
only the test fixture after observing the bound state. This correction must not introduce a daemonized
publication continuation or claim a finite redelivery SLO.

## Authorization, commands, and downstream gates

The authorization now freezes exact focused lifecycle, observer regression, compile, hash, diff, and
security commands. It preserves the exact two-file ceiling, required implementer
`codex-subagent-qppr-c1c-am1-implementer`, independent acceptance, orchestrator-only governance/commit,
and all non-live exclusions.

The replacement authorization omits the prior single-use/idempotency controls and does not require an
activation window of at most 24 hours. Restore an exact idempotency key, define consumption by the first
complete exact two-file candidate report, and require owner activation of the reviewed hash with the
required identity and a <=24-hour window. Byte drift, identity drift, replay after consumption, or an
expired window must hard-stop.

The A1-AM3 rebind correctly makes the current AM2 requirements reproducible, retains the exact
roadmap-recovery four-file ceiling and five frozen paths, and remains NON-ACTIVATABLE pending owner SRE
ratification plus C1C-AM1 review, activation, acceptance, commit, and final byte-level rebind. A2 and all
provider/live actions remain blocked.

## Required revisions

1. Make fail-stop classification observable and internally consistent for a never-returning callback,
   and add deterministic late-return-after-deadline evidence.
2. Restore single-use, idempotency, exact-identity/hash, and <=24-hour activation-window controls.

VERDICT: REQUEST_REVISION — define an observable fail-stop classification and late-return proof, and restore single-use idempotent <=24-hour activation controls
