# QPPR-A1 Amendment 3 roadmap-recovery implementation authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-a1-am3-roadmap-recovery-20260719`  
**Idempotency key:** `qa-provider-probe-reliability:a1:am3:roadmap-recovery:20260719`  
**Required implementer:** `codex-subagent-qppr-a1-am3-implementer`  
**Status:** **PREPARED_ONLY / NON-ACTIVATABLE — IMPLEMENTATION NOT AUTHORIZED**  
**Single use:** consumed only after C1C acceptance/commit, final exact rebind, and owner activation

## 1. Exact conditional subjects

| Subject | SHA-256 |
|---|---|
| roadmap verifier recovery | `0d16fa8e96413e6368aa0dfb4331f5dbfa79e652187eb9d4a98405c33ab0c1a4` |
| A1-AM3 prerequisite rebind | `41ca28a2d0d4960ec6849d93cc013912ecaa545dfe0b6b645f76a14cc7c5f0b2` |
| prior A1-AM3 authorization | `63f28c168b0b2a6547d72b00df9122cc8ef5c6e02443a78b5b5d271b5920f621` |
| C1C design | `2a04262e0b278eeaeff271475f003e13883615aff906a132a9ee2e8c2f470974` |
| C1C authorization | `c9460d0b7468defb0807ca4d51ff2ae615e6d0764b9b836fe0c58bdade237c23` |
| mandatory Tier-0 verifier predecessor | `c8602060565decdeef229042d2e15bf4b875f78f5a71eb4422cfcc3dd074a9d9` |

This authorization supersedes the prior three-file A1-AM3 ceiling but remains non-activatable until
an independently reviewed final amendment binds exact accepted C1C commit, acceptance, process-owner
and lifecycle-test hashes. No owner statement may waive that missing binding.

## 2. Exact future four-file ceiling

Only required implementer `codex-subagent-qppr-a1-am3-implementer` may eventually modify the four
paths and exact predecessors in recovery section 3. The other five A1 candidate paths must remain at
their frozen hashes. Any fifth correction path, substitution, drift, or different implementer is a
hard stop.

The grant is limited to the five existing AM2 corrections through accepted C1C plus the exact static
verifier correction in recovery section 4. The verifier must require the canonical compatibility
exec, prohibit the retired inline loop/second lifecycle owner, and independently require Phase-0
`0.6.1` direct adoption. Removing or weakening coverage is prohibited.

## 3. Validation and exclusions

Offline deterministic tests must prove canonical form passes and missing exec, missing Phase-0 call,
or reintroduced legacy loop fail. The full roadmap verifier must pass without executing providers.
The A1 adoption/C1/C1B/C1C suites, syntax checks, and mandatory Tier-0 must also pass under the final
candidate. No test may resolve/invoke a real provider or access network, heartbeat/evidence authority,
live Phase 0, API/browser, service, deployment, or traffic.

The implementer may not delegate, stage, commit, deploy, delete, or self-accept. Workflow session,
skill, intent, resume, pulse, handoff, and task-registry artifacts remain non-product control-plane
evidence outside the four-file ceiling; they cannot carry code or be staged with A1.

## 4. Activation sequence and A2 block

1. independently review, activate, implement, accept, and commit C1C;
2. prepare an exact post-C1C A1-AM3 amendment binding final prerequisite and all nine static/candidate
   hashes;
3. obtain independent flagship `PASS` over that amendment and the resulting authorization bytes;
4. owner activates the exact resulting hash, repeating required implementer
   `codex-subagent-qppr-a1-am3-implementer` and a <=24-hour window; and
5. independently accept the complete A1/verifier candidate before orchestrator commit.

Stop on any sequence bypass, identity mismatch, C1C drift, verifier weakening, provider/live/network
action, new dependency/env/port/store/route/card, Nix/service/deploy/traffic/rollback, or every stop
in the recovery design. A2 remains blocked until accepted committed A1-AM3 and its own exact adjacency
rebind and activation.

`RECORD: PREPARED_ONLY / NON-ACTIVATABLE. A1-AM3, A2, and every live action remain unauthorized.`
