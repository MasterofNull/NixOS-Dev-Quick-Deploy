# QPPR-A1 Amendment 3 implementation authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-a1-am3-20260719`
**Idempotency key:** `qa-provider-probe-reliability:a1:host-adoption:am3:20260719`
**Required implementer:** `claude-subagent-qppr-a1-am3-implementer` (balanced / Sonnet tier)
**Status:** **PREPARED_ONLY / NON-ACTIVATABLE — IMPLEMENTATION NOT AUTHORIZED**
**Single use:** consumed only after final prerequisite rebind and explicit owner activation

## 0. Revision notice (2026-07-19, this revision)

This authorization is revised in place. It was never activated, so revision is legitimate under
its own non-activatable status; its technical content (correction inventory, stop conditions, A2
block) is preserved unchanged except where this notice states otherwise.

1. **Implementer identity changed.** The originally named `codex-subagent-qppr-a1-am3-implementer`
   is replaced by `claude-subagent-qppr-a1-am3-implementer` at balanced (Sonnet) tier. Reason:
   Codex CLI is quota-exhausted until 2026-07-25 (evidence:
   `.agents/delegation/outputs/codex-20260718-204057-i0hlfyxxxxxx.log`). Per Rule 17
   (dispatch at the cheapest capable tier, deviations recorded), this slice is evaluated against
   the local-Qwen envelope and the fast (Haiku) tier before falling to balanced:
   - **Outside the local-Qwen envelope**: the local-agent capability envelope is measured as
     bounded single-command / single-edit only; this slice requires coordinated edits across
     multiple files in one candidate (see section 2 — four MODIFY paths, expanded from three; see
     deviation note below), which is multi-site work the envelope does not cover.
   - **Outside the fast (Haiku) tier**: the C1C-AM2 candidate rejection precedent
     (`C1C-AM2-CANDIDATE-REJECTION.md`) found a Haiku-tier implementer bound the wrong contract
     (process runtime instead of publication callback) on adjacent lifecycle-concurrency work in
     this same slice family. AM3's correction requires exclusive use of the accepted C1C
     `publication_barrier` synchronous acknowledgement interface with strict pre-redelivery
     completion/cancellation ordering — the same class of concurrency-contract precision the
     Haiku candidate was rejected for missing.
   - Balanced (Sonnet) tier is therefore the cheapest capable tier available for this slice under
     current constraints. This is a recorded deviation, not a preference.
2. **Ceiling correction (deviation from this task's framing, disclosed).** The task instruction
   that produced this revision described "three MODIFY files." The actual current ceiling is
   **four** MODIFY files: `A1-AM3-ROADMAP-VERIFIER-RECOVERY.md` (independently reviewed in
   `C1C-A1-AM3-AUTHORIZATION-REVIEW.md`, required revision #4) expanded the original three-file
   AM3 ceiling to four by adding `scripts/testing/verify-flake-first-roadmap-completion.sh` to
   fix the 22/1 mandatory Tier-0 failure at "Flagship CLI smoke covers declared agent CLI
   surfaces." `A1-AM3-AM1-REPRODUCIBLE-REBIND.md` confirms this four-file boundary is the final
   A1 boundary. Section 2 below reflects four files, not three, because the review's required
   revision #4 explicitly mandates carrying the roadmap-recovery ceiling into the final rebind and
   no independently reviewed document narrows it back to three. This deviation is disclosed here
   rather than silently applied.
3. **Post-C1C reality bound.** C1C (`publication_barrier` synchronous acknowledgement interface)
   is independently accepted and committed: commit `1cca8c57`, acceptance record
   `C1C-AM3-CANDIDATE-ACCEPTANCE.md` (VERDICT: PASS), final
   `scripts/testing/harness_qa/core/process_lifecycle.py` =
   `c7407ea4d172abd2250c459dbe6fdd1bfd4fec959d834abaf553f5e903c32ae2`, final
   `scripts/testing/test-qa-provider-probe-lifecycle.py` =
   `d95479d0aa0961d4d5561e0239aa0c1547577190ca07208b460a04aeb579148b`. Full binding, including all
   nine governed A1/verifier path hashes and the decision-basis reconciliation, is recorded in
   `A1-AM3-FINAL-REBIND.md` (see section 4).

## 1. Exact conditional subjects

| Subject | SHA-256 |
|---|---|
| A1-AM3 prerequisite rebind | `41ca28a2d0d4960ec6849d93cc013912ecaa545dfe0b6b645f76a14cc7c5f0b2` |
| A1-AM3 roadmap verifier recovery | `0d16fa8e96413e6368aa0dfb4331f5dbfa79e652187eb9d4a98405c33ab0c1a4` |
| A1-AM3 roadmap-recovery authorization | `6590176eb70ec09296f87bad1a2d4c58220086aa21fe09cc4058d77c35d359ac` |
| A1-AM3.1 reproducible prerequisite rebind (`A1-AM3-AM1-REPRODUCIBLE-REBIND.md`) | `cf05ef961f64add459161971beea4ec372454c90d2b2c395999aa1444ab6a488` |
| C1C design | `2a04262e0b278eeaeff271475f003e13883615aff906a132a9ee2e8c2f470974` |
| C1C authorization | `c9460d0b7468defb0807ca4d51ff2ae615e6d0764b9b836fe0c58bdade237c23` |
| C1C-A1-AM3 authorization review | `15a1b110e2483d6be46aa8f46faf56fd27288ce4fbfc611fbea944dcb0c81e38` |
| A1-AM2 design (current bytes, per reproducible rebind) | `2d6d7e490b70d307ff6c3d5daf1d89c0ab85bba8cc331e8f8491be1aacb309f9` |
| A1-AM2 review (current bytes, per reproducible rebind) | `214a3a99fbadf9895311c7142e63fc4787e1b7fb3fe10c115fbfaac305cc89c6` |
| A1-AM1 revision record | `d9d44bc37b3a3415d2a2805b115a01bfe808276cdf8ceab8b33f84a935bdaff9` |
| C1C final commit | `1cca8c57` |
| C1C acceptance record (`C1C-AM3-CANDIDATE-ACCEPTANCE.md`) | `6b65ee2393f5d4806cab07c40d40d1e5903f24dbc43e27f0d75306d404e4d44e` |
| `process_lifecycle.py` (final) | `c7407ea4d172abd2250c459dbe6fdd1bfd4fec959d834abaf553f5e903c32ae2` |
| `test-qa-provider-probe-lifecycle.py` (final) | `d95479d0aa0961d4d5561e0239aa0c1547577190ca07208b460a04aeb579148b` |

This authorization previously had no C1C commit/acceptance/final hashes and was non-activatable
for that reason. That gap is now closed per section 0.3 above. It remains non-activatable until
`A1-AM3-FINAL-REBIND.md` exists, is independently flagship-reviewed with a `PASS` verdict over the
complete binding, and the owner activates the resulting exact authorization bytes (this document,
post-revision) naming the required implementer and a <=24-hour window. No owner statement may
waive or infer any part of that sequence.

## 2. Exact future four-file ceiling

Only after `A1-AM3-FINAL-REBIND.md` records independent flagship `PASS`, the required implementer
may modify exactly:

| # | Path | Current predecessor |
|---:|---|---|
| 1 | `scripts/testing/qa-provider-probe.py` | `755b730d6d7446d76f21933d2e273ca4ed7f8f65a808672e532caab007b5d0ab` |
| 2 | `scripts/testing/harness_qa/core/result.py` | `4c72e8aa658a67a5168fb9817a21a247c596ac29aa55b7fd776d5f18f0320776` |
| 3 | `scripts/testing/test-qa-provider-probe-adoption.py` | `f7e286dfa23ef3b22eea713e1ec4b9b350c3e5e4b29ba4a0098d9d4f0eb7123c` |
| 4 | `scripts/testing/verify-flake-first-roadmap-completion.sh` | `c8602060565decdeef229042d2e15bf4b875f78f5a71eb4422cfcc3dd074a9d9` |

The other five A1 candidate hashes in the rebind must remain exact:
`smoke-flagship-cli-surfaces.sh` (`98a1c8f2a9b67895f7e42d9ae176d65b706128d92b93033c1094c2b6d23bcdfb`),
`harness_qa/phases/phase0.py` (`b01edf1308c6433c6fae1316a75b7d4251b77df9afa5d8e4fb41b99c5ca63999`),
`harness_qa/core/context.py` (`ef2993079c1ffed301e9b9cc41014944706f37ca4e3879fb7605223af314e6ea`),
`harness_qa/main.py` (`2137974e61f991cf363ae0dbca1511f3d801728d01f43b5af974050e4df9f4c0`),
`harness_qa/reporters/json_out.py` (`7d62ff15da20e969384a858c67d8e0dea1b34423e941f205f780d66d65a11f29`).
Any drift, fifth path, or substitution requires a new reviewed authorization.

## 3. Future grant and mandatory stops

After all gates, only `claude-subagent-qppr-a1-am3-implementer` (balanced / Sonnet tier) may
implement the five AM2 correction requirements plus the roadmap-verifier correction (recovery
section 4) using the accepted C1C synchronous acknowledgement interface. The implementer must
never use the legacy daemon publication callback. Completion/cancellation acknowledgement must
precede redelivery/handler return/ordinary continuation and leave no callback, reader, ticker,
thread, task, or write capability afterward. The roadmap verifier correction must add only
deterministic static coverage (recovery section 4 items 1-5); it may not execute providers, weaken
existing coverage, or permit an alternation between legacy and canonical form.

All AM2 tests and stops remain, plus the roadmap-recovery's offline deterministic fixture proof
(canonical form passes; missing exec, missing Phase-0 call, or reintroduced legacy loop fail).
Additionally stop on: absent/unaccepted/uncommitted C1C, missing final rebind, identity mismatch,
callback deadline extension, legacy publication use, prerequisite path edit, any
post-acknowledgement continuation, a fifth correction path, or any weakening of the roadmap
verifier's coverage. No provider/live/network/heartbeat/evidence/Phase-0/API/browser/
deployment/traffic/rollback/A2 action is granted. The implementer may not delegate, stage, commit,
deploy, delete, or self-accept.

Workflow session/skill/intent/resume/pulse/handoff/task-registry records remain non-product
control-plane evidence outside the four-file ceiling; they may not carry code or be staged with A1.

## 4. Activation sequence

1. independently review and owner-activate C1C — **done** (commit `1cca8c57`,
   `C1C-AM3-CANDIDATE-ACCEPTANCE.md` VERDICT: PASS);
2. implement, independently accept, and commit exact C1C — **done**, same commit;
3. prepare and independently pass the exact final A1-AM3 rebind amendment
   (`A1-AM3-FINAL-REBIND.md`) — **prepared, PREPARED_ONLY, awaiting independent flagship review**;
4. only then may the owner activate the resulting exact A1-AM3 authorization bytes (this document,
   post-revision), naming required implementer `claude-subagent-qppr-a1-am3-implementer` (balanced
   / Sonnet tier) and a <=24-hour window, under the owner's recorded standing authorization; and
5. independently accept the complete exact four-file-modified, nine-path A1/verifier candidate
   before orchestrator commit.

Any different implementer or sequence requires new reviewed bytes. A2 stays blocked until A1-AM3
acceptance and commit, then receives a separate adjacency rebind and activation.

`RECORD: PREPARED_ONLY / NON-ACTIVATABLE. Missing independent flagship PASS over
A1-AM3-FINAL-REBIND.md and missing owner activation prohibit A1-AM3 activation; A2 and every live
action remain unauthorized.`
