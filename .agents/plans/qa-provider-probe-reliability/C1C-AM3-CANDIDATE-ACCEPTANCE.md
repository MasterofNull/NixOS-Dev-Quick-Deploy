# QPPR C1C-AM3 candidate acceptance — independent flagship review

**Reviewer identity:** `claude-subagent-qppr-c1c-am3-acceptance-reviewer`
**Model:** Claude Fable 5 (`claude-fable-5`), flagship tier, fresh session — not the implementer
(Sonnet), not the R1/R2 design reviewer (Opus), not the orchestrator drafting session, and not an
author anywhere in this slice's lineage.
**Reviewed:** 2026-07-19 UTC, within activation window 2026-07-19T07:30:00Z → 2026-07-20T07:30:00Z.
**Authority:** `C1C-AM3-CANDIDATE-ACCEPTANCE-AUTHORIZATION.md`, recomputed SHA-256
`2a8cc8aad20a6c88f0b999982dc415a4e74112e561d52895915a8d0cee19847d` (exact match); owner activation
PULSE entry `auth-qa-provider-probe-reliability-c1c-am3-acceptance-20260719`
(2026-07-19T07:12:52-0700, line 303) confirmed, derived from the owner `[standing-authorization]`
entry (2026-07-18T21:33:26-0700, line 294).

## Recomputed hashes (all exact matches)

| Subject | Recomputed SHA-256 | Required |
|---|---|---|
| `scripts/testing/harness_qa/core/process_lifecycle.py` (candidate) | `c7407ea4d172abd2250c459dbe6fdd1bfd4fec959d834abaf553f5e903c32ae2` | match |
| `scripts/testing/test-qa-provider-probe-lifecycle.py` (candidate) | `d95479d0aa0961d4d5561e0239aa0c1547577190ca07208b460a04aeb579148b` | match |
| `scripts/testing/test-qa-provider-probe-observer.py` (frozen, working tree) | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` | match |
| `HEAD:…/process_lifecycle.py` (predecessor) | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` | match |
| `HEAD:…/test-qa-provider-probe-lifecycle.py` (predecessor) | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` | match |
| `HEAD:…/test-qa-provider-probe-observer.py` (observer at HEAD) | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` | match |
| `C1C-AM3-SYNCHRONOUS-FAIL-STOP-AMENDMENT.md` (rev 2, technical SSOT) | `719115853f0129c13dadad49de3cc736edddec1f64d9d9b9c4b973949cd2f0f6` | match |
| `C1C-AM3-IMPLEMENTATION-AUTHORIZATION.md` (consumed) | `95d8d947d69ca37bd996e8240f4ee56aa231db93d159b8b5eebca3d649204474` | match |

## Criterion 1 — hash freeze and delta confinement: PASS

All three subject hashes match exactly (table above). Predecessor bytes at HEAD match both
predecessor hashes; the observer file is byte-identical between HEAD and working tree (no delta at
all). `git diff --stat` over the three paths shows changes in exactly the two MODIFY paths
(+255/−? lines lifecycle, +560 lines test; 810 insertions, 5 deletions total) and nothing in the
observer. No third file is part of the candidate.

## Criterion 2 — R5 fail-stop mechanism, traced in the bytes: PASS (the crux)

Current-line anchors (candidate bytes): publication invocation `publication(dict(provisional))` at
**1275**; violation branch **1277-1292**; `except Exception:` re-raise gate at **1330-1331**
(`if controller is None and identity is None and not lock_held: raise`); handler recovery lock
release at **1362** (predecessor 1118) and handler `_restore_and_redeliver` at **1386**
(predecessor 1142); `finally:` lock release at **1423** (predecessor 1179) and finally
`_restore_and_redeliver` at **1428** (predecessor 1184).

**`identity` is provably None at line 1275 on every path that reaches it.** Exhaustive path trace:

- `identity` is initialized `None` at 1006 and assigned exactly once, at 1123, inside the
  `else` branch of the `stat is None` check.
- Paths where 1123 never executes: preflight/controller failure returns at 1027; spawn failure
  returns at 1096; pidfd/stat failure (1099-1120) leaves `identity = None` and falls through the
  skipped `if identity is not None:` block to 1224 and onward to 1258 — identity None.
- Path where 1123 executes: control enters the `if identity is not None:` block (1127-1222). That
  block contains no `return`, no `break`/`continue` escaping the block, and ends with the
  unconditional straight-line pair `os.close(identity.pidfd); identity = None` at 1219-1220. Every
  non-exceptional exit of the block therefore clears identity before 1224. Any exception inside the
  block goes to the handler with identity live — but then line 1275 is never reached, so no
  violation-path interaction exists.
- `rg -n 'publication\('` confirms 1275 is the only synchronous invocation site (the only other
  reference is the legacy thread `target=`).

**Neutralization precedes the raise, and both restoration paths are unreachable with live state:**

- Late-return path: after `observed_ms > barrier_deadline_ms`, the code emits sequence-2
  `contract_violation` (emitters are exception-proof: `_write` catches
  `BlockingIOError/BrokenPipeError/OSError/ValueError`, `close` catches `OSError`, so no exception
  can escape before neutralization), then sets `lock_held = False` (1287) **without releasing the
  lock object** and `controller = None` (1288) **without transferring to a redelivery variable**,
  then raises the dedicated `_PublicationContractViolation` (1289). At the handler gate (1330):
  controller None ∧ identity None (proven above) ∧ lock_held False → immediate re-raise; handler
  recovery lines 1362/1386 (pred. 1118/1142) unreached. In `finally:`: `identity is None` (no
  teardown), `if lock_held:` False → 1423 (pred. 1179) skipped, `if controller is not None:` False
  → 1428 (pred. 1184) skipped. Only subreaper restore, observer close, and publication-observer
  close run — none of which are prohibited (prohibition covers handler/mask restoration,
  redelivery, lock release, ordinary return). The invocation lock remains held forever → every
  later `run_owned_process` returns `probe_busy` (verified by test evidence, below).
- Never-return path: the owner thread blocks inside line 1275 itself, structurally before lines
  1302-1309 (subreaper restore, lock release, `_restore_and_redeliver`, return) and before any
  `except`/`finally` execution. All four restoration/release lines are unreachable; the lock stays
  held. No code after the call is needed or relied upon.
- The finally-block guards `if lock_held:` / `if controller is not None:` are confirmed to be the
  only conditionals standing between the violation path and finally-restoration, and both are
  neutralized before the raise. The dedicated exception type prevents classification as the generic
  recovery case; the pre-existing gate (predecessor-identical bytes, verified against
  `git show HEAD`) is what propagates it.

## Criterion 3 — R2/R6 structure: PASS

- Synchronous invocation on the barrier path: the `publication_fd is not None` branch (1262-1294)
  contains no thread, worker, task, queue, retry, or second writer. Fresh
  `rg -n 'threading\.Thread'` on the lifecycle file yields exactly four lines: 1009 (pre-existing
  `readers` annotation), 1130/1131 (pre-existing `_drain` readers), 1297 (legacy worker line) —
  nothing new on the barrier path.
- Legacy path byte-identical in behavior: the `else` branch (1296-1299) carries the predecessor's
  exact three worker lines (`threading.Thread(target=publication, …, daemon=True)` / `start()` /
  `join(timeout=remaining)`) with identical preceding `signal_started`/`remaining` computation,
  verified against `git show HEAD` bytes. With `publication_fd=None`, `publication_observer` is
  None and no new code executes.
- Never-return blocks before any restoration: structural, per Criterion 2 trace.

## Criterion 4 — the six deterministic proofs: PASS

1. On-time `completed` (`test_on_time_publication_barrier_…`) and zero-budget `cancelled`
   (`test_zero_budget_…`, unconditional single-site 3.3s injection at `normalize_probe_output`
   plus a SIGTERM-ignoring fixture whose forced ~2s cleanup grace deterministically exceeds the
   4.9s budget by construction — not a race) emit the exact sequence-1/2 records; callback
   invocation counts asserted (1 and 0 respectively). Existing ≤5s redelivery evidence untouched
   (`test_outer_sigterm_redelivery_within_slo` unchanged, suite green).
2. Never-return (`test_never_returning_callback_…`): subprocess fixture (`pub:never_return`) with
   an `entered` event barrier and watcher; select-based event-driven reads (`_drain_publication`,
   `_read_stdout_line`) — no sleep-only assertions; exactly one `running` record; injected
   classifier time `deadline_ms + 1` yields `CONTRACT_VIOLATION`; evidence proves lock held inside
   the callback; absence of any further stdout/record proves no ordinary return, no redelivery, no
   second record/writer; tracked `threading.Thread` subclass proves no publication thread; parent
   kills and reaps only its exact fixture child in `finally`.
3. Late-return (`test_late_return_…`): event-delayed callback (`Event().wait(timeout=6.0)` > 4.9s
   budget) in a subprocess fixture; records `running` + `contract_violation`; fixture proves
   `_PublicationContractViolation` propagated, `lock_held_after_violation` true, zero publication
   thread constructions, and a follow-up in-fixture `run_owned_process` returning `probe_busy`
   (the enforced "no later provider start").
4. Strict rejection: 15 malformed records fail closed in `parse_publication_record`; duplicate,
   backward, and post-terminal records rejected in `accept_publication_record`; composed
   non-downgrade test proves a stray sequence-2 `completed` after a violation-classified point is
   refused and the classification retained.
5. Legacy path: `test_legacy_publication_without_barrier_fd_still_uses_a_worker_thread` proves the
   daemon worker still runs with `publication` as target; frozen observer suite 8/8 and file hash
   unchanged.
6. `threading.Thread` scan clean per Criterion 3.

Classifier purity per R6: `classify_publication_contract` depends only on the validated record
state, bound deadline, injected observer monotonic time, and sequence-2 presence; missing/invalid
record is always `unavailable`, never healthy, never violated; boundary is strict
(`now == deadline` → `running`, `now > deadline` → violation); terminal states are retained.

## Criterion 5 — validation commands re-run fresh by this reviewer: PASS

| Command | Result |
|---|---|
| `python3 scripts/testing/test-qa-provider-probe-lifecycle.py` | **39/39 OK** (62.8s) |
| `python3 scripts/testing/test-qa-provider-probe-observer.py` | **8/8 OK** (5.8s) |
| `python3 -m py_compile` (both candidate files) | clean |
| `sha256sum` observer | `a17d70be…ee63b` (frozen value) |
| `git diff --check` (both paths) | clean |
| secret-scan `rg` | exactly 3 matches (test file lines 59/208/1280); all 3 exist in predecessor bytes (`git show HEAD` lines 50/130/724 — sanitizer test fixtures + JSON-schema URL); `git diff` added lines contain **zero** matches |
| `rg -n 'threading\.Thread'` lifecycle | only legacy line 1297 + pre-existing 1009/1130/1131 `_drain` lines |

## Criterion 6 — governance trail and deviation adjudication: PASS

Canonical-writer evidence in `.agents/events/a2a-events.jsonl`: `resume.update` (event 483) and two
`pulse.append` events (484 write, 485 validate) by
`claude-subagent-qppr-c1c-am3-implementer`; PULSE projections at lines 301 (write, with explicit
self-disclosure of the ordering deviation) and 302 (validate). Intent lock
`c1c-am3-20260719` present in the pending-update ledger in state `[done]` (add + done both
executed). Owner implementation activation at PULSE line 300 (hash, identity, SRE-ratification
restatement, ≤24h window — all present).

**Deviation adjudication:** the implementer ran the required pre-edit governance commands
(`aq-event resume`, `pending-update add`) after editing rather than before, and self-disclosed
this in both PULSE and its report. I adjudicate this a **procedural deviation with no integrity
impact, accepted**: (a) the candidate bytes are hash-frozen and match the acceptance subject
exactly, so the ordering cannot have altered what is being accepted; (b) every validation was
re-run independently by this reviewer and passes; (c) the intent lock's protective purpose
(concurrent-writer exclusion) was not violated in fact — HEAD is untouched, the delta is confined
to the two ceiling paths, and no other agent wrote them in the window; (d) disclosure was prompt
and truthful in the canonical channels, which the authorization itself names as the mitigating
condition (concealment would have been disqualifying). Process note for the orchestrator, not a
block: future implementation grants may want the resume/intent commands verified before granting
file-write access rather than relying on implementer sequencing.

## Criterion 7 — no prohibited action: PASS

`git diff --cached` for the three subject paths: empty (nothing staged). No commit: HEAD
(`96b6c04f` lineage) still carries exact predecessor bytes. No third file in the candidate. No
live/provider/network action evidenced anywhere in the trail (implementer commands were the
allowlisted tests/scans; validate pulse states none performed). No self-acceptance: the implementer
stopped at the validate pulse; this review is the first acceptance act, by a disjoint identity.

## Non-blocking observations (recorded, not conditions)

1. **Lineage citation ambiguity (governance doc, not candidate):** the acceptance authorization
   (line 21) and the owner activation PULSE line 300 attach the hash `2079ca6a…61df0` to "R2 review
   PASS", but that hash is the **R1** review file (`C1C-AM3-AUTHORIZATION-REVIEW.md`, verdict
   REQUEST_REVISION). The actual R2 PASS review (`C1C-AM3-AUTHORIZATION-REVIEW-R2.md`) hashes
   `b1e931b585556789728c005d5bb939b12f93b29380555460065a114ae671ea82`, mtime 2026-07-18 21:39
   (pre-activation), terminal `VERDICT: PASS` on disk. Both files exist with the expected verdicts;
   no tampering indicated; not an acceptance criterion for the candidate.
2. `classify_publication_contract("running", d, now>d, has_seq2_ack=True) == "running"` is the
   correct reading of the AM2 verbatim rule ("AND no valid sequence-2"); post-violation
   non-downgrade is enforced at the stream-acceptance layer plus consumer terminal latch and is
   proven by the composed test.

VERDICT: PASS
