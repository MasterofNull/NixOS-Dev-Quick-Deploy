# QPPR-A1 Amendment 2 — terminal join and evidence closure

**Status:** PREPARED_ONLY / DESIGN AMENDMENT / IMPLEMENTATION UNAUTHORIZED
**Prepared:** 2026-07-19
**Parent:** `A1-A2-ADOPTION-DESIGN-PACKET.md`
**Trigger:** independent A1-AM1 `REQUEST_REVISION`

## 1. Exact problem statement and authority

The owner-activated A1-AM1 candidate preserved its eight-file ceiling and passed its offline,
syntax, regression, and Tier-0 checks, but independent acceptance at SHA-256
`d9d44bc37b3a3415d2a2805b115a01bfe808276cdf8ceab8b33f84a935bdaff9` found five blocking
contract defects:

1. terminal publication could occur after signal restoration/redelivery because result submission
   and the reader-owned write were not synchronously joined;
2. the join did not validate the complete closed terminal result, expected profile, or terminal
   sequence;
3. canonical mode fabricated an invocation UUID when the reserved QA identity was absent;
4. an initially group/world-writable lock was changed to mode `0600` before admission validation;
5. `CheckResult.to_dict()` passed arbitrary `details` through the immutable evidence boundary.

This amendment freezes the smallest correction: exactly three of the existing eight candidate
paths. The other five candidate paths remain byte-frozen. It preserves every passed A1 contract,
does not activate A1, and does not unblock A2 until an independently accepted A1-AM2 commit exists.

## 2. Exact bound evidence

| Subject | SHA-256 or Git object |
|---|---|
| QPPR PRD | `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d` |
| D0 design packet | `041951b9afbb6173e15cc176329f3ae228930199fb67799ad1fb59b32980394f` |
| D0 design review | `9ca904808a903f98398ec9c98113a7f039ef9bb11b4076bfbe4c8a1a133310fb` |
| A1/A2 adoption design | `44b600bfb3a22e05205c0babb9a72e1ed02c6f84afd71127a5a71afb99c79f18` |
| A1/A2 rebind amendment | `51200b64ff2f859e1ba225fc238ede8fd81aa403c9ac2a9efc97000bb51477dc` |
| final rebind review | `eeb77e63fe429a2e521d315c806dfb6d0c51d63f5386961df8b4ee8983cb0662` |
| A1-AM1 authorization | `5f992de921103870572cd765178e1a358e308a4ed7061efbb471fbfe499ad322` |
| A1-AM1 acceptance / revision record | `d9d44bc37b3a3415d2a2805b115a01bfe808276cdf8ceab8b33f84a935bdaff9` |
| accepted C1A commit | `52b0a0716ea2e008c2ca1b137c689482e2995543` |
| C1A acceptance | `73808146d65e877a15e0396f8e8adb5b726b986f7a01baccf5a5aa14b21d1987` |
| corrected C1B-AM1 commit | `f54cd8c8257a43dd8666209648d4976c323dfbff` |
| C1B-AM1 acceptance | `1373f508e80311c657e303ea8896616ac3aa943d923e3ccd6d0fd421b270c868` |
| accepted result/heartbeat schema | `1acaa61d4b3fe2737a513112c49578bf5b596c04f4916f4e4647e8e7516b7ac4` |
| accepted policy | `2cbe6e350f35cd9e0831186df31f9631a10c1e838fb0246fc1f56828abb4a6af` |
| accepted process owner | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` |
| accepted C1A focused test | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` |
| accepted C1B focused test | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` |

Any mismatch is a hard stop.

## 3. Frozen current eight-file candidate

| # | Path | Current candidate SHA-256 | AM2 disposition |
|---:|---|---|---|
| 1 | `scripts/testing/qa-provider-probe.py` | `755b730d6d7446d76f21933d2e273ca4ed7f8f65a808672e532caab007b5d0ab` | **MODIFY** |
| 2 | `scripts/testing/smoke-flagship-cli-surfaces.sh` | `98a1c8f2a9b67895f7e42d9ae176d65b706128d92b93033c1094c2b6d23bcdfb` | freeze |
| 3 | `scripts/testing/harness_qa/phases/phase0.py` | `b01edf1308c6433c6fae1316a75b7d4251b77df9afa5d8e4fb41b99c5ca63999` | freeze |
| 4 | `scripts/testing/harness_qa/core/result.py` | `4c72e8aa658a67a5168fb9817a21a247c596ac29aa55b7fd776d5f18f0320776` | **MODIFY** |
| 5 | `scripts/testing/harness_qa/core/context.py` | `ef2993079c1ffed301e9b9cc41014944706f37ca4e3879fb7605223af314e6ea` | freeze |
| 6 | `scripts/testing/harness_qa/main.py` | `2137974e61f991cf363ae0dbca1511f3d801728d01f43b5af974050e4df9f4c0` | freeze |
| 7 | `scripts/testing/harness_qa/reporters/json_out.py` | `7d62ff15da20e969384a858c67d8e0dea1b34423e941f205f780d66d65a11f29` | freeze |
| 8 | `scripts/testing/test-qa-provider-probe-adoption.py` | `f7e286dfa23ef3b22eea713e1ec4b9b350c3e5e4b29ba4a0098d9d4f0eb7123c` | **MODIFY** |

The minimum AM2 implementation inventory is therefore exactly three paths. No fourth candidate
path is needed: `phase0.py` already supplies the reserved invocation to canonical execution and
the sole `CheckResult.to_dict()` boundary can independently reject malformed details. If correction
requires changing any frozen path, stop and prepare a new reviewed amendment.

## 4. Required correction contract

### 4.1 Synchronous one-shot terminal projection join

`qa-provider-probe.py` must replace the event-plus-daemon-write behavior with one closed join owned
by the aggregate process. Its independently submitted inputs are:

- one C1B observer event whose schema, strict monotonic sequence, state, and terminal position have
  been validated; and
- one complete C1 terminal result validated against the accepted closed result schema and bound to
  the exact invocation, provider, expected policy profile, terminal lifecycle state, result/failure
  relation, and that join's expected terminal sequence.

The state machine is exactly
`OPEN -> HAVE_EVENT|HAVE_RESULT -> COMMITTING -> COMMITTED`, with
`OPEN|HAVE_EVENT|HAVE_RESULT -> CANCELLED`. Each slot is compare-and-set once. An identical duplicate
is idempotent; a conflicting duplicate cancels without writing. Only the join's `COMMITTING` owner
writes the terminal heartbeat, once, under the existing writer lock. Submission paths never write
independently.

The ordinary return path and C1 bounded publication callback must both synchronously drive the same
`try_commit`. The callback may wait only inside C1's existing bounded publication remainder and
must return only after the join is `COMMITTED` or synchronously `CANCELLED`. Before default signal
redelivery, custom/ignored handler return, ordinary provider continuation, aggregate teardown, or
lock release, the main thread must cancel an incomplete join, close its observer input, and join the
reader/ticker. No daemon or background continuation may remain capable of writing. Dropped/invalid
observer input yields no fabricated terminal heartbeat and cannot extend C1's SLO.

### 4.2 Closed terminal validation

The accepted `qa.provider-probe-result.v1` schema is authoritative. Validation must reject missing
or extra fields, non-UUID invocation, wrong provider/profile, wrong lifecycle state, invalid timing
or bounds, unknown result/failure/action/disposition values, inconsistent pass/failure relation,
malformed digest, or a terminal event/sequence mismatch. Failure-class projection is derived only
from a fully valid result. Parser failure, schema failure, cross-wiring, or ordering failure cancels
the join and emits no terminal projection.

### 4.3 Reserved canonical identity

`run_provider_probe(canonical=True)` must fail closed before lock admission, provider resolution,
process ownership, heartbeat, or evidence work when `qa_invocation_id` is absent or invalid. Only
standalone compatibility mode may mint a non-authoritative UUID, and that mode writes no canonical
heartbeat or immutable evidence.

### 4.4 Initial lock safety

After `openat(...O_NOFOLLOW)` and before any `chmod`, write, truncate, lock, or other mutation,
validate both the descriptor and directory-relative named inode as regular, single-link,
effective-user-owned, same-device/same-inode, and not group/world writable. An existing unsafe inode
is rejected without changing its bytes, mode, owner, link count, or identity. A newly created inode
may be verified as mode `0600`; unconditional normalization of an existing inode is prohibited.

### 4.5 Sole closed details serializer

`CheckResult.to_dict()` remains the only JSON/evidence serializer. When `details` is present it must
accept only exactly four independent closed `qa.provider-probe-result.v1` records in accepted policy
order `codex,qwen,claude,pi`, with the exact corresponding profile IDs, one shared valid invocation
UUID, terminal lifecycle, and valid result/failure relation. It rejects arbitrary dictionaries,
unknown/sensitive fields, extra/missing/reordered/duplicate records, malformed fields, and
cross-invocation/profile/provider records. `None` remains valid for checks without structured probe
evidence. No raw output, prompt, credential, argv, executable, environment, PID, path, or exception
payload crosses this boundary.

## 5. Exact adversarial acceptance additions

All new tests stay in `scripts/testing/test-qa-provider-probe-adoption.py` and remain offline with
fixture executables and spies only. They must prove:

1. ordinary and default/custom/ignored SIGTERM/SIGINT paths, both input orders, identical duplicate
   submissions, and conflicting races produce exactly one valid terminal write or zero on conflict;
2. the terminal write completes before redelivery/handler return/ordinary continuation, the reader
   and ticker are joined, and a post-boundary write spy observes exactly zero attempts;
3. wrong schema/profile/provider/invocation/terminal sequence, extra/missing field, unknown failure
   class, and inconsistent pass/failure pairs cancel without a terminal heartbeat;
4. canonical missing/invalid invocation performs zero lock/provider/spawn/write actions;
5. a pre-existing effective-user-owned `0666` lock is rejected and retains its exact original mode,
   inode, and bytes;
6. the serializer accepts the exact four valid records and rejects extra, missing, reordered,
   duplicate, malformed, sensitive, cross-invocation, cross-provider, and cross-profile details;
7. all twelve previously passing A1 adoption tests, the accepted C1A/C1B suites, syntax checks, and
   Tier-0 remain passing without real provider or network execution.

Tests must use bounded joins and deterministic barriers; no timing-only assertion may serve as the
proof of pre-redelivery completion or absence of late writes.

## 6. Governance plane and candidate ceiling

The three-path ceiling governs implementation product bytes. Mandatory workflow operations remain
compatible but are not candidate product files: the orchestrator may use canonical commands to
create/update the session scratchpad, `.agent/collaboration/PENDING.json`, `RESUME.json`,
`PULSE.log`, and `HANDOFF.md`, plus the existing delegation/task registry records required for
traceability. These control-plane records must not contain implementation code, must not be staged
or committed with AM2, and do not authorize a candidate-path expansion. Skill selection/loading and
read-only status/hash commands likewise do not consume the candidate ceiling. The implementer may
not use this allowance to edit governance policy, plans, authorizations, reviews, or registries by
hand.

## 7. Stops, review, activation, and A2 block

Stop on any fourth candidate path, current-hash mismatch, foreign overlap, schema/policy/process-
owner change, schema relaxation, second writer, asynchronous late writer, fabricated canonical
identity, mutation-before-lock-validation, open evidence serialization, real provider/network/API/
browser action, new dependency/env/port/store/route/card, retry/fallback, Nix/service/deploy action,
staging, commit, deletion, or self-review.

An independent flagship architecture/security/SRE/QA reviewer must issue a final `PASS` over this
amendment and its exact authorization. The owner must then activate the exact authorization SHA-256,
name one implementer, and set an activation window no longer than 24 hours. Any changed byte requires
new hash binding and independent review. A1 remains unaccepted and uncommittable until an independent
exact-candidate acceptance passes. A2 remains blocked, non-activatable, and subject to its final
post-A1 adjacency rebind.

`RECORD: PREPARED_ONLY. QPPR-A1-AM2 implementation, A2, provider/API/browser execution, deployment,
traffic, cutover, rollback, and every live action remain unauthorized.`
