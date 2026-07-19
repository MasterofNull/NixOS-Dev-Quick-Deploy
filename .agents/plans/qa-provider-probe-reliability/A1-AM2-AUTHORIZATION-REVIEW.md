# QPPR-A1 Amendment 2 — independent authorization review

**Reviewed:** 2026-07-19
**Reviewer identity:** `codex-subagent-qppr-a1-am2-auth-review`
**Reviewer role:** independent flagship architecture, security, SRE, QA, and authorization lane
**Implementation authority:** none
**Overall verdict:** **REQUEST_REVISION**

## Exact reviewed subjects

| Subject | Expected SHA-256 | Observed SHA-256 | Verdict |
|---|---|---|---|
| `A1-AM2-DESIGN-AMENDMENT.md` | `2d6d7e490b70d307ff6c3d5daf1d89c0ab85bba8cc331e8f8491be1aacb309f9` | `2d6d7e490b70d307ff6c3d5daf1d89c0ab85bba8cc331e8f8491be1aacb309f9` | **REQUEST_REVISION** |
| `A1-AM2-IMPLEMENTATION-AUTHORIZATION.md` | `9382f727ce3a243fbdd3462a512fddd7cff0a516b63c4a0482410b1c7449cd0d` | `9382f727ce3a243fbdd3462a512fddd7cff0a516b63c4a0482410b1c7449cd0d` | **REQUEST_REVISION** |

The reviewer made no edit to either subject or to any implementation candidate.

### Normalized-subject binding — resolved

The corrected authorization binds the exact normalized design SHA-256
`2d6d7e490b70d307ff6c3d5daf1d89c0ab85bba8cc331e8f8491be1aacb309f9` in its exact-subject
table. The prior stale reference to the pre-normalization design hash is absent. This closes the
byte-binding defect without changing either substantive blocker below.

## Exact predecessor and candidate verification

The A1-AM1 independent revision record is exact at
`d9d44bc37b3a3415d2a2805b115a01bfe808276cdf8ceab8b33f84a935bdaff9`.
The adoption design, rebind amendment, final rebind review, A1-AM1 authorization, accepted schema,
policy, process owner, and focused C1A/C1B tests all match the hashes bound by the amendment.

The complete current eight-file A1 candidate is unchanged:

| Path | Observed SHA-256 | AM2 disposition |
|---|---|---|
| `scripts/testing/qa-provider-probe.py` | `755b730d6d7446d76f21933d2e273ca4ed7f8f65a808672e532caab007b5d0ab` | modify |
| `scripts/testing/smoke-flagship-cli-surfaces.sh` | `98a1c8f2a9b67895f7e42d9ae176d65b706128d92b93033c1094c2b6d23bcdfb` | frozen |
| `scripts/testing/harness_qa/phases/phase0.py` | `b01edf1308c6433c6fae1316a75b7d4251b77df9afa5d8e4fb41b99c5ca63999` | frozen |
| `scripts/testing/harness_qa/core/result.py` | `4c72e8aa658a67a5168fb9817a21a247c596ac29aa55b7fd776d5f18f0320776` | modify |
| `scripts/testing/harness_qa/core/context.py` | `ef2993079c1ffed301e9b9cc41014944706f37ca4e3879fb7605223af314e6ea` | frozen |
| `scripts/testing/harness_qa/main.py` | `2137974e61f991cf363ae0dbca1511f3d801728d01f43b5af974050e4df9f4c0` | frozen |
| `scripts/testing/harness_qa/reporters/json_out.py` | `7d62ff15da20e969384a858c67d8e0dea1b34423e941f205f780d66d65a11f29` | frozen |
| `scripts/testing/test-qa-provider-probe-adoption.py` | `f7e286dfa23ef3b22eea713e1ec4b9b350c3e5e4b29ba4a0098d9d4f0eb7123c` | modify |

No candidate drift or fourth AM2 product path was observed.

## Per-defect adjudication

### 1. Terminal projection before redelivery — blocking

The three-file ceiling cannot implement the stated deterministic guarantee against the accepted
process-owner interface. `process_lifecycle.py:1051-1057` starts the publication callback in a
**daemon** thread and waits only until its independently computed remainder expires. It neither
passes that absolute deadline to the callback nor requires a completion/cancellation
acknowledgement. At `process_lifecycle.py:1063-1065`, signal restoration/redelivery proceeds even
when that worker is still alive.

The amendment instead requires the aggregate main thread to cancel an incomplete join, close its
observer input, and join the reader/ticker before redelivery. While `run_owned_process` owns the
signal path, the aggregate main thread is blocked inside that function and cannot execute this
boundary before redelivery. A callback-local timeout is not sufficient: the lifecycle remainder
may already be zero, the worker may not be scheduled before redelivery, and the accepted interface
has no way to prove that a daemon callback cannot continue afterward. Deterministic barrier tests
would reproduce this gap without relying on wall-clock timing.

This must be resolved by a separately reviewed lifecycle-interface prerequisite (for example, a
bounded synchronous callback or an explicit deadline plus completed/cancelled acknowledgement that
the lifecycle owner waits for before redelivery), followed by a new A1 rebind. Merely changing the
three authorized files cannot provide the frozen invariant while preserving the accepted C1 owner.

### 2. Closed terminal validation — sufficient after the prerequisite

The amendment correctly requires the accepted closed result schema, UUID and provider/profile
binding, monotonic terminal sequence, result/failure relation, timing bounds, action/disposition
enums, and digest shape. The runner and focused-test paths are sufficient to implement and prove
this validation without changing the accepted schema or policy. This does not cure finding 1.

### 3. Reserved canonical identity — sufficient

`qa-provider-probe.py` can reject absent or invalid canonical identity before lock admission,
provider resolution, process ownership, heartbeat, or evidence side effects. Compatibility mode
can retain non-authoritative UUID creation without canonical writes. The authorized focused test
can prove zero action with spies.

### 4. Initial lock safety — sufficient

Removing pre-validation `fchmod`, validating the descriptor and named inode immediately after
`openat`, and accepting only a newly created mode-0600 inode or a pre-existing already-safe inode
fits within `qa-provider-probe.py`. The specified inode/mode/bytes regression is adequate and
preserves the stable persistent lock.

### 5. Exact four-record evidence serializer — sufficient

`CheckResult.to_dict()` is the sole harness JSON/evidence boundary currently receiving structured
provider details. `result.py` and the adoption test can enforce exactly four independently closed,
policy-ordered `codex,qwen,claude,pi` records, exact profile binding, one UUID, terminal state, and
the valid result/failure relation while continuing to accept `details=None`. The negative matrix
correctly includes missing, extra, reordered, duplicate, sensitive, malformed, and cross-wired
inputs.

## Authorization-plane finding — blocking

The authorization does not bind an exact required implementer identity. It says only that the
owner will later name “one named bounded implementer” (`A1-AM2-IMPLEMENTATION-AUTHORIZATION.md:41,
71-74`). Consequently the reviewed bytes permit activation for any identity and do not provide an
exact role-to-subject binding for the intended implementation lane. The revised authorization must
name the required implementer identity explicitly (for example,
`codex-subagent-qppr-a1-am2-implementer`) and require the owner activation to repeat that exact
identity. Any different implementer must require a new reviewed authorization hash.

## Gates that remain sound

- The exact predecessor and frozen-five hashes are bound and mismatch is a hard stop.
- The product ceiling is explicit; canonical session, intent, resume, pulse, handoff, and registry
  operations remain control-plane evidence outside the staged candidate.
- Tests remain deterministic, fixture-only, bounded, and offline; real provider, network, Phase-0
  live, heartbeat/evidence activation, API, browser, deployment, and A2 work remain excluded.
- Implementer staging, commit, delegation, deletion, and self-acceptance are prohibited.
- Independent exact-eight-file acceptance and orchestrator-only governance/staging/commit remain
  mandatory.
- A2 remains blocked until accepted A1-AM2 commit, final adjacency rebind, independent review, and
  distinct owner activation.

No implementation, provider/network action, Phase-0 run, heartbeat/evidence write, API/browser
action, deployment, staging, commit, or destructive operation was performed by this review.

VERDICT: REQUEST_REVISION — normalized design `2d6d7e490b70d307ff6c3d5daf1d89c0ab85bba8cc331e8f8491be1aacb309f9` cannot guarantee callback completion or cancellation before redelivery within its three-file ceiling, and corrected authorization `9382f727ce3a243fbdd3462a512fddd7cff0a516b63c4a0482410b1c7449cd0d` does not bind the exact required implementer identity
