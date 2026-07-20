# QPPR A1-AM3 rev2 candidate acceptance — independent flagship review

**Reviewer identity:** `claude-subagent-qppr-a1-am3-rev2-acceptance-reviewer`
**Model:** Claude Fable 5 (`claude-fable-5`), flagship tier, fresh session — not the Sonnet
implementer, not the first acceptance reviewer session (its REQUEST_REVISION verdict
`A1-AM3-CANDIDATE-ACCEPTANCE.md`, recomputed `f5f7ef1e070074c67d9860e6fd367fe0344db2c777089c274d4e449f5f5b7db5`,
is retained lineage), not the Opus design/rebind reviewer, not the orchestrator
**Reviewed:** 2026-07-20 (UTC), inside activation window 2026-07-20T01:42:00Z → 2026-07-21T01:42:00Z
(session start recorded at 2026-07-20T01:42:59Z)
**Grant:** `auth-qa-provider-probe-reliability-a1-am3-rev2-acceptance-20260719`, authorization
document recomputed SHA-256
`5e2df0005af01d35218f74588696848fa9cfa1ade299a5e67ec0b5c59f1014c6` (exact match); owner
`[acceptance-activated]` PULSE entry (line 317, 2026-07-19T18:42:22-0700) names this hash, this
reviewer identity, and this window, derived from the `[owner] [standing-authorization]` entry
(line 294). Revision authorization recomputed
`224447ad1aa2a4af212c905248c82114c4e576d26e0945f080808dd6a5ad82ff` (exact match).
**Verdict:** **PASS** (terminal line at end)

## Recomputed subject hashes (all fresh, this session)

Two MODIFY (revised candidate):

| Path | Required | Recomputed | Result |
|---|---|---|---|
| `scripts/testing/qa-provider-probe.py` | `f8280792…041308` | `f8280792a9ffa23acbb333ed22922c26899fe794879290d715db784826041308` | exact |
| `scripts/testing/test-qa-provider-probe-adoption.py` | `f4ca8241…594781` | `f4ca8241583575bf3e079f15194168b98926df340cddf2465c3733e4d7594781` | exact |

Seven frozen:

| Path | Recomputed | Result |
|---|---|---|
| `scripts/testing/harness_qa/core/result.py` | `37821dcffa3ec98ddfc1cb82ed965d518b7f0bf0fa9088fb369be9cfe1b0d550` | exact |
| `scripts/testing/verify-flake-first-roadmap-completion.sh` | `4f5ce42ed1f6163d82c1b6c4c913cc4b2dc800e4723591a4ea302e8063529be4` | exact |
| `scripts/testing/smoke-flagship-cli-surfaces.sh` | `98a1c8f2a9b67895f7e42d9ae176d65b706128d92b93033c1094c2b6d23bcdfb` | exact |
| `scripts/testing/harness_qa/phases/phase0.py` | `b01edf1308c6433c6fae1316a75b7d4251b77df9afa5d8e4fb41b99c5ca63999` | exact |
| `scripts/testing/harness_qa/core/context.py` | `ef2993079c1ffed301e9b9cc41014944706f37ca4e3879fb7605223af314e6ea` | exact |
| `scripts/testing/harness_qa/main.py` | `2137974e61f991cf363ae0dbca1511f3d801728d01f43b5af974050e4df9f4c0` | exact |
| `scripts/testing/harness_qa/reporters/json_out.py` | `7d62ff15da20e969384a858c67d8e0dea1b34423e941f205f780d66d65a11f29` | exact |

C1C prerequisite (committed, verified unchanged): `harness_qa/core/process_lifecycle.py`
`c7407ea4d172abd2250c459dbe6fdd1bfd4fec959d834abaf553f5e903c32ae2`,
`test-qa-provider-probe-lifecycle.py`
`d95479d0aa0961d4d5561e0239aa0c1547577190ca07208b460a04aeb579148b` — both exact.

## Criterion 1 — nine hashes and revision-scope confinement: PASS (with one adjudicated limitation)

All nine governed hashes exact (tables above). Path-level confinement is proven outright: the
seven frozen paths are byte-exact at their required values, so every delta from the
revision-predecessor state lives in the two MODIFY paths (whose hashes moved
`38940640…`→`f8280792…` and `15dbe325…`→`f4ca8241…`).

**Adjudicated limitation — no literal predecessor diff possible.** The two predecessors were
untracked, uncommitted candidate bytes overwritten in place by the revision; no copy exists in
git (untracked), git stash, `.agent/archive/`, `.agents/`, or any session scratchpad (searched).
In-file scope was therefore verified structurally against the first verdict's byte-precise
predecessor descriptions: the defective structures it cited are gone (`submit_result` no longer
returns after only CAS-filling the slot; the unconditional post-`_join_terminal` canonical
heartbeat at predecessor lines 597-605 no longer exists), the replacement is exactly the
R-A1/R-A2 join machinery (`_finalize_join`, `committed`/`cancelled` flags, commit-gated write),
and the adoption suite grew 18→24 by exactly the six `SignalPathAdversarialTests` plus their
`_signal_fixture_main` subprocess entry point (R-A3). Every region the first acceptance PASSed
is present unchanged in structure and re-verified below: fail-stop block (now 602-626, same
25-line span the first reviewer reviewed at 563-587), `_valid_terminal_result` (4.2),
canonical-identity gate (4.3), `AggregateLock` (4.4), `RoadmapVerifierFixtureTests`, and all 18
prior tests. No out-of-scope rewrite detected. Confinement holds at the strongest level provable
from the retained evidence.

## Criterion 2 — R-A1 verified in the bytes against finding A: PASS

Finding A was: the publication callback returned after only filling the result slot, so the C1C
barrier recorded `completed` (sequence-2), released the lock, and redelivered — killing the
process (default disposition) with **zero** terminal write behind a recorded `completed`, and
writing post-handler-return for custom/ignored. Each element is closed in the bytes:

- **The callback now drives the join.** `ObserverConsumer.submit_result`
  (`qa-provider-probe.py:398-432`) calls `_finalize_join` before returning on **every** path:
  valid record (line 428, with the CAS'd result), invalid/conflicting record (line 418, with
  `result=None`, forcing CANCELLED). It never returns with the join undecided.
- **`_finalize_join` (468-526) is the one closed join, idempotent and correctly placed.**
  First-caller-decides via the `committed`/`cancelled` flags (488-491): a second call for the
  same provider iteration returns the recorded outcome without re-joining, re-validating, or
  re-writing. Inside the callback window it waits bounded (`_CALLBACK_JOIN_BUDGET_S = 4.0` <
  C1C's ~4.9s barrier budget; the C1B `terminal` event is already on the observer pipe before
  the barrier invokes the callback — `process_lifecycle.py:1256-1258` — so the reader
  self-terminates on processing it and the wait is a safety margin, exactly as the implementer
  states). It joins reader and ticker, requires `reader_done` + validated monotonic terminal
  C1B event + full 4.2 `_valid_terminal_result`, then commits (single commit-gated terminal
  heartbeat, canonical only, 515-523) or cancels (writes nothing) — before returning.
- **`completed` reachable only after commit.** In the committed C1C bytes the sequence-2
  `completed` is emitted only after `publication(...)` returns
  (`process_lifecycle.py:1275→1293-1294`), followed by lock release (1305) and
  `_restore_and_redeliver` (1309). Since `submit_result` returns only with the join COMMITTED
  or synchronously CANCELLED, a recorded `completed` can no longer front-run the terminal
  write. (Where the join synchronously CANCELS, `completed` acknowledges on-time callback
  completion over a correctly cancelled projection — the disjunction AM2 4.1 itself permits:
  "must return only after the join is `COMMITTED` or synchronously `CANCELLED`". The false-ack
  defect — `completed` recorded over an undecided join — is what finding A required closed, and
  it is closed.)
- **Default-disposition redelivery cannot kill ahead of the terminal write:** redelivery
  (1309) is unreachable until the callback has returned, i.e. until the write landed (or the
  join validly cancelled with zero write and a truthful ack). Proven live by the real-SIGTERM
  subprocess test (below): the child dies on redelivery (nonzero returncode) yet the terminal
  heartbeat for the killed provider exists.
- **Custom/ignored cannot observe a late write (AM2 §5.2):** the post-`run_owned_process`-return
  `_finalize_join` call (635-641, `reader_wait_timeout=None`) is an idempotent no-op whenever
  the callback already decided — no second write when COMMITTED, no write when CANCELLED, no
  post-return continuation. On the ordinary no-signal path it is the sole, first commit, with
  deterministic EOF (both write ends closed at 627-628 before the call).

Non-blocking observation (outside finding A, inherited C1C R4 semantics): if the barrier budget
is already exhausted when the barrier evaluates (~4.9s after first signal), C1C skips the
callback and truthfully acknowledges `cancelled` (sequence-2) — no false ack is possible on that
marginal path either; for custom/ignored the ordinary-path commit then lands post-redelivery,
which is the pre-existing accepted R4 shape, not a revision defect. Also noted: the drained
publication-status value is not re-consulted post-return (`_drain_publication_pipe` result
discarded at 642); this is sound because the only `contract_violation` emission co-occurs with
the raised `_PublicationContractViolation`, which takes the fail-stop path, never the commit path.

## Criterion 3 — R-A2 verified: PASS

The finding-B write is gone in the bytes: `run_provider_probe` contains **no** terminal-heartbeat
write after `_finalize_join` returns — the predecessor's unconditional
`terminal_failure = … if committed else "contract_invalid"` block (old 597-605) has no successor.
Exhaustive `_heartbeat` call-site audit: `_tick` (353, interim states only, write-locked),
`_read` (386, explicitly `state != "terminal"`), `_finalize_join` (517, gated by
`if committed and consumer.enabled` — the join's COMMITTING owner, once), and the
`_PublicationContractViolation` fail-stop block (616). A cancelled join emits no terminal
projection on any reachable path; proven by the write-spy test (zero terminal-state `_heartbeat`
calls on a cancelled join) and the conflicting-duplicate test (committed value not overwritten).

**Adjudication — fail-stop heartbeat (614-621) retained:** this is not a cancelled-join write and
is not the finding-B target. It is the aggregate's observable fail-stop signal
(`contract_invalid`) on the permanent-stop path where the C1C barrier classified
`contract_violation` and the invocation lock is never released. The first acceptance reviewed
this exact 25-line block (predecessor lines 563-587) and recorded it "Compliant"; finding B cited
only the separate 597-605 write. Carried-forward accepted behavior, consistent with the
harness observability principle; unchanged by the revision.

## Criterion 4 — R-A3, six SignalPathAdversarialTests genuinely prove the findings: PASS

All six are event-barrier deterministic (marker-file barrier against real fixture-process state;
proofs are state/order-based, never sleep-only) and each of findings A/B would be re-caught:

1. `test_default_disposition_kill_writes_exactly_one_terminal_heartbeat` — real subprocess, real
   SIGTERM, SIG_DFL redelivery kills the child (asserted nonzero returncode) yet the killed
   provider's (`qwen`) terminal heartbeat exists with a valid failure class. The predecessor
   produced **zero** writes here — this test fails against it. Catches finding A (default).
2. `test_custom_disposition_terminal_write_precedes_redelivered_handler` — the redelivered
   custom handler itself reads back `("qwen", "terminal")` at redelivery time: a deterministic
   ordering proof (handler runs only after `_restore_and_redeliver`, which runs only after the
   callback returned). Against the predecessor the handler would observe interim/other-provider
   state — fails. Catches finding A (custom §5.2 ordering).
3. `test_ignored_disposition_terminal_write_precedes_ordinary_continuation` — SIG_IGN variant
   via the last-in-policy-order provider (`pi`), so the post-return final heartbeat is
   unambiguously that provider's own single valid terminal write (AM2 §5 item 1 coverage for
   the ignored path; the ordering mechanism itself is shared with and proven by tests 1-2).
4. `test_conflicting_duplicate_submission_cancels_without_overwrite` — deterministic fed-pipe
   consumer; a conflicting duplicate after commit neither overwrites nor flips state.
5. `test_identical_duplicate_submission_is_idempotent` — identical duplicate stays COMMITTED.
6. `test_invalid_observer_stream_cancels_with_zero_heartbeat_writes` — write-spy on
   `probe._heartbeat` proves **zero** terminal-state writes on a cancelled join (interim
   observability writes correctly distinguished). The predecessor wrote a terminal heartbeat
   here — fails against it. Catches finding B.

Determinism re-verified: full suite 24/24 once plus the adversarial class 6/6 twice more this
session (3 clean runs total, no flakes).

**Adjudication of the two disclosed debugging deviations — both ACCEPTED:**

- *Fixed 0.5s delay → marker-file event barrier:* the flaky first attempt would itself have
  violated AM2's "no timing-only assertion" rule; the replacement is a genuine event barrier
  against real process state (marker touched by the fixture before sleeping; sender polls the
  marker). The residual 0.1s buffer is not load-bearing for any assertion. This deviation moved
  the tests toward the contract, and was disclosed.
- *Shell `touch`/`sleep` fixture → pure-Python helper via `sys.executable` absolute path:*
  `run_provider_probe` deliberately scopes child PATH to the fixture bin dir, so the shell
  fixture silently no-op'd; broadening PATH was correctly rejected because this repo's real
  system PATH contains genuine `codex`/`claude`/`qwen`/`pi` CLIs — a real-provider-execution
  hazard the authorization prohibits. The chosen fix has zero external-binary dependency and
  zero PATH-broadening risk. Correct call, properly disclosed.

## Criterion 5 — fresh validation re-runs (all executed by this reviewer, this session): PASS

| Validation | Result |
|---|---|
| `python3 scripts/testing/test-qa-provider-probe-adoption.py` | **24/24 OK** (19.3s); adversarial class re-run 6/6 twice more |
| `python3 scripts/testing/test-qa-provider-probe-lifecycle.py` (frozen C1C) | **39/39 OK** (71.5s) — unaffected |
| `bash scripts/testing/verify-flake-first-roadmap-completion.sh` | **611 pass, 0 fail**, exit 0 |
| `py_compile` (probe, adoption test, result, process_lifecycle) | clean |
| `bash -n` (verifier, smoke) | clean |
| `git diff --check` (worktree + cached) | clean |
| Secret scan over the two MODIFY files | no matches |
| Daemon-publication pattern | no `threading.Thread(target=publication` in the probe; adoption test enforces its absence |

## Criterion 6 — governance trail and prohibitions: PASS

- Canonical writers throughout (aq-event projections in `.agents/events/a2a-events.jsonl`).
- Chain in correct order: first-acceptance verdict pulse (event 501 / PULSE 313) →
  `[owner] [revision-activated]` naming `224447ad…` (502 / 314) → `[owner]
  [revision-activation-amended]` window-start correction to 2026-07-19T19:17:00Z, explicitly
  recording **the implementer's correct pre-window refusal** (504 / 315) → implementer
  `resume.update` 19:17:33Z → candidate edits 19:18:32Z and 2026-07-20T01:38:09Z (both inside
  the amended window, resume before first edit) → implementer `pulse.append` 01:41:23Z with full
  R-A1/R-A2/R-A3 and deviation disclosure (506 / 316) → owner acceptance activation naming
  `5e2df000…` and this reviewer (507 / 317).
- Prohibitions: nothing staged in the governed set (`git status`: both MODIFY paths untracked,
  frozen worktree modifications unstaged); no frozen-path edit (byte-exact); no third candidate
  file; no provider/network/live action in tests (offline fixtures, pure-Python helper, real
  CLIs explicitly avoided); no self-acceptance; A2 untouched.

## Scope of this PASS

Per the activated authorization: this PASS authorizes **only the orchestrator** to run Tier-0,
stage, and commit the exact bytes hashed above. Any changed byte voids this verdict. **A2 remains
blocked** pending its own rebind. This reviewer performed no subject edits, no staging, no
commit, no Tier-0, no delegation; writes were limited to this artifact and one closing pulse.

VERDICT: PASS
