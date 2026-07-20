# QPPR A1-AM3 candidate acceptance — independent flagship review

**Reviewer identity:** `claude-subagent-qppr-a1-am3-acceptance-reviewer`
**Model:** Claude Fable 5 (`claude-fable-5`), flagship tier, fresh session — not the Sonnet
implementer, not the Opus design/rebind reviewer, not the C1C-AM3 acceptance session, not the
orchestrator
**Reviewed:** 2026-07-19 (inside activation window 2026-07-19T18:50:00Z → 2026-07-20T18:50:00Z)
**Grant:** `auth-qa-provider-probe-reliability-a1-am3-acceptance-20260719`, authorization document
recomputed SHA-256 `55e8eccec05575f136d5bd69d26931f6a5be5d6154ec75d873800a0c7a0389c3` (exact
match); owner `[acceptance-activated]` PULSE entry (line 312) names this hash, this reviewer
identity, and this window, derived from the `[owner] [standing-authorization]` entry (line 294).
**Verdict:** **REQUEST_REVISION** (criterion 2 / Crux A; secondary criterion 4 finding with the
same root)

## Recomputed subject hashes (all fresh, this session)

Four MODIFY (candidate):

| Path | Required | Recomputed | Result |
|---|---|---|---|
| `scripts/testing/qa-provider-probe.py` | `38940640…6747e84` | `3894064065607ac4e8437c404aec81285b7ab3d9c2087a83f7f9e59bd6747e84` | exact |
| `scripts/testing/harness_qa/core/result.py` | `37821dcf…b0d550` | `37821dcffa3ec98ddfc1cb82ed965d518b7f0bf0fa9088fb369be9cfe1b0d550` | exact |
| `scripts/testing/test-qa-provider-probe-adoption.py` | `15dbe325…42fa4a` | `15dbe32592a2a4994c357c76921fac92ec9866bcf25b5f67010a098e1b42fa4a` | exact |
| `scripts/testing/verify-flake-first-roadmap-completion.sh` | `4f5ce42e…529be4` | `4f5ce42ed1f6163d82c1b6c4c913cc4b2dc800e4723591a4ea302e8063529be4` | exact |

Five frozen (final-rebind values):

| Path | Recomputed | Result |
|---|---|---|
| `scripts/testing/smoke-flagship-cli-surfaces.sh` | `98a1c8f2a9b67895f7e42d9ae176d65b706128d92b93033c1094c2b6d23bcdfb` | exact |
| `scripts/testing/harness_qa/phases/phase0.py` | `b01edf1308c6433c6fae1316a75b7d4251b77df9afa5d8e4fb41b99c5ca63999` | exact |
| `scripts/testing/harness_qa/core/context.py` | `ef2993079c1ffed301e9b9cc41014944706f37ca4e3879fb7605223af314e6ea` | exact |
| `scripts/testing/harness_qa/main.py` | `2137974e61f991cf363ae0dbca1511f3d801728d01f43b5af974050e4df9f4c0` | exact |
| `scripts/testing/harness_qa/reporters/json_out.py` | `7d62ff15da20e969384a858c67d8e0dea1b34423e941f205f780d66d65a11f29` | exact |

C1C prerequisite (committed `1cca8c57`, verified unchanged):

| Path | Recomputed | Result |
|---|---|---|
| `scripts/testing/harness_qa/core/process_lifecycle.py` | `c7407ea4d172abd2250c459dbe6fdd1bfd4fec959d834abaf553f5e903c32ae2` | exact |
| `scripts/testing/test-qa-provider-probe-lifecycle.py` | `d95479d0aa0961d4d5561e0239aa0c1547577190ca07208b460a04aeb579148b` | exact |

Verifier predecessor confirmed: `git show HEAD:` of the verifier hashes to
`c8602060565decdeef229042d2e15bf4b875f78f5a71eb4422cfcc3dd074a9d9` and its working-tree diff is
confined to the flagship-CLI check region (1 check removed, 3 added).

## Criterion 1 — nine hashes and delta confinement: PASS

All nine governed hashes match exactly (tables above). The five frozen paths are byte-exact at
their final-rebind predecessor values, so every predecessor delta is confined to the four MODIFY
paths. `qa-provider-probe.py` and `test-qa-provider-probe-adoption.py` are untracked candidate
files (their predecessors `755b730d…`/`f7e286df…` were themselves uncommitted candidate bytes);
`result.py` and the verifier are worktree modifications. Nothing in the governed set is staged.

## Criterion 2 — Crux A, C1C publication_barrier integration: FAIL

**What is correct in the bytes:**

- Exclusive C1C barrier use: the single `run_owned_process` call site always passes
  `publication_fd=pub_write_fd` alongside `publication=consumer.submit_result`
  (`qa-provider-probe.py:549-562`); the legacy daemon path (publication without publication_fd)
  is unreachable, and the adoption test `test_publication_barrier_exclusively_used` enforces both
  the call-site shape and the absence of `threading.Thread(target=publication`.
- `publication_fd` mechanics match the committed contract: `os.pipe2(O_NONBLOCK|O_CLOEXEC)` write
  end satisfies `_open_publication_observer` (write-only, nonblocking, FIFO, CLOEXEC); the caller
  closes its write end before draining, so `_drain_publication_pipe` reaches EOF deterministically
  and applies `accept_publication_record` fail-closed stream discipline (R7).
- `_PublicationContractViolation` fail-stop (`qa-provider-probe.py:563-587`): no retry, no
  release of the C1C invocation lock (held permanently per R5 — every later `run_owned_process`
  returns `probe_busy`), deterministic reader/ticker joins, remaining profiles typed
  `contract_invalid`, aggregate permanently stops. Compliant.
- Ordinary (no-signal) return path: `_join_terminal` closes both write ends first, joins
  reader/ticker without arbitrary timeouts, requires a validated strictly-monotonic C1B terminal
  event, refuses commit on `contract_violation` barrier state, and applies the full 4.2 closed
  terminal-result validation before the canonical terminal write. This half of the implementer's
  reading — "ordinary return path drives the same try_commit synchronously" — matches AM2 4.1.
- "Barrier activates only on mid-run signal" is factually true of the committed C1C bytes
  (`process_lifecycle.py:1258` — `publication` is invoked only when `controller.first_signal` is
  set); the caller cannot change that.

**Blocking finding A — the callback does not drive the join; `completed` is acknowledged before
any terminal projection commit or reader/ticker join.**

AM2 4.1 (inherited requirement, unamended — C1C-AM3 states "AM3 changes no requirement of AM2"):
"The ordinary return path and C1 bounded publication callback must **both** synchronously drive
the same `try_commit`. The callback may wait only inside C1's existing bounded publication
remainder and **must return only after the join is `COMMITTED` or synchronously `CANCELLED`**."
`COMMITTED` is defined in the same section as the state reached through `COMMITTING`, whose owner
"writes the terminal heartbeat, once, under the existing writer lock."

In the candidate, `ObserverConsumer.submit_result` (`qa-provider-probe.py:385-401`) only CAS-fills
the result slot and returns; the join is in `HAVE_RESULT` (or event+result, uncommitted) state.
The barrier then emits sequence-2 `completed` (`process_lifecycle.py:1293-1294`), releases the
invocation lock, and performs restoration/redelivery — all before any terminal projection commit
and before any reader/ticker join. Consequences, by disposition:

- **default_terminating** (the common canonical Phase-0 case): `_restore_and_redeliver` re-raises
  the signal with `SIG_DFL` restored — the process dies inside `run_owned_process`.
  `_join_terminal` never runs. Canonical mode produces **zero** terminal heartbeat writes, while
  the immutable publication-status channel has already recorded `completed` — a false completion
  acknowledgement (Anti-Gaming HARD rule adjacent: an observability signal reports work that was
  never performed). AM2 §5 items 1-2 require exactly one valid terminal write completing before
  redelivery on this path.
- **custom / ignored**: `run_owned_process` returns and the caller commits — exactly once, but
  after handler return/redelivery, violating AM2 §5.2's ordering ("the terminal write completes
  before redelivery/handler return/ordinary continuation").

This is precisely the defect lineage: A1-AM1 blocking defect #1 (terminal publication not
synchronously joined ahead of redelivery) → A1-AM2 review finding 1 (blocking: the aggregate
"cannot cancel or join its terminal projection before redelivery"; remedy = "completed/cancelled
acknowledgement **that the lifecycle owner waits for before redelivery**") → C1C design packet
("**return is the completion/cancellation barrier**"). The barrier window exists so the aggregate
can complete or cancel its terminal projection inside it. The candidate uses the window only to
hand over the provisional record. A callback-internal bounded commit is feasible within the
committed interface: the C1B terminal observer event is already written to the pipe before the
barrier fires (`process_lifecycle.py:1256-1257`), the reader self-terminates on processing
`terminal`, the ticker terminates ≤0.9s after `done`, and the heartbeat write is a bounded
rename — comfortably inside the ~4.9s barrier budget AM2 explicitly permits the callback to wait
in. The acceptance criterion's required ordering — "`completed` is acknowledged only after
terminal projection commit + full reader/ticker join" — is therefore not satisfied in the bytes,
and the implementer's interpretation does not match AM2 section 4.1. Per the activated criterion,
this is REQUEST_REVISION even though all shipped tests pass.

**Blocking finding B — canonical terminal heartbeat is written even when the join cancels.**

`run_provider_probe` (`qa-provider-probe.py:597-605`): when `canonical`, a terminal heartbeat is
written unconditionally after `_join_terminal`, with
`terminal_failure = joined_failure_class if committed else "contract_invalid"`. A cancelled join
(conflicting duplicate, invalid observer input, failed 4.2 validation, barrier
`contract_violation`) therefore still emits a terminal projection. AM2 4.1: "a conflicting
duplicate **cancels without writing**"; 4.2: schema/ordering failure "cancels the join and
**emits no terminal projection**"; "**Only** the join's `COMMITTING` owner writes the terminal
heartbeat." This deviation was not disclosed anywhere in the implementer's report or PULSE entry.
(The adoption suite contains no canonical-mode cancel-path test, so 18/18 does not exercise it.)

## Criterion 3 — Crux B, roadmap-verifier recovery (anti-gaming): PASS

The rewrite at the former line 597 replaces one genuinely ambiguous alternation
(`commands=\(cn codex qwen gemini claude pi\)|--help` — satisfiable by any `--help` substring)
with three independent architecture-aware assertions plus the retained 0.6.1 label check
(verifier lines 597-606): positive exact-argv delegation
(`exec python3 "\$\{runner\}" --machine`), negative legacy-form rejection
(`commands=\(`, word-bounded `timeout`, `bash -c`, `eval `), and positive Phase-0 direct
`module\.run_provider_probe\(` adoption. Reasoning through the assertions: a reintroduced legacy
provider loop trips the absent-pattern check; removed exec delegation trips the positive check;
removed Phase-0 adoption trips the direct-call check. This verifies the real architecture rather
than the current bytes: the patterns bind the canonical delegation chain, not incidental text.
The fixture proof (`RoadmapVerifierFixtureTests`) extracts the verifier's **own** live
check regexes and replays them against mutated fixture texts (exec removed, Phase-0 call removed,
legacy loop reintroduced — each must fail), anchoring the proof to the shipped verifier instead
of a copy. Confirmed passing against the frozen smoke candidate `98a1c8f2…` unmodified (fresh
611/0 run + fresh 18/18 adoption run).

**611-vs-609 adjudication:** predecessor (`c8602060…`, = git HEAD) invokes 609 checks; the
candidate removes 1 and adds 3 (net +2 → 611), exactly as required by recovery §4 items 1-5's
explicit positive+negative split ("increasing the evidence from one ambiguous alternation to
explicit positive and negative assertions"). Disclosed in the implementer's PULSE entry and
matching the activated expectation (611/0). Spec-driven; accepted.

## Criterion 4 — AM2 4.2-4.5 in the bytes: FAIL on the 4.2 cancel path (same root as finding B); 4.3/4.4/4.5 PASS

- **4.2**: `_valid_terminal_result` is a complete closed validation (exact field set, schema
  version, UUID+invocation binding, provider/profile binding, terminal state, timing/deadline
  bounds, exit-code range, result/failure-class enum + pass/failure relation, bounded
  termination-action records, disposition closure incl. `redelivered⇒class` consistency, exact
  digest shape) and is evaluated inside the join before any commit decision. Correct as far as it
  goes — but a failed validation still results in a canonical terminal heartbeat via finding B,
  so "cancels the join and emits no terminal projection" is not honored.
- **4.3**: canonical mode fail-closes on missing/invalid `qa_invocation_id` at
  `run_provider_probe` entry — before `_load_policy`, before `AggregateLock` construction, before
  any resolution/spawn/heartbeat/evidence work. Proven with zero-side-effect assertions
  (`test_canonical_missing_invocation_is_zero_action`: no lock file, no heartbeat file). PASS.
- **4.4**: `AggregateLock.acquire` opens `O_RDWR|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW` at 0600;
  only a **newly created** inode is verified as 0600 (`created` flag); a pre-existing inode is
  opened without O_CREAT and validated (regular, single-link, euid-owned, not group/world
  writable, handle/named same-dev+same-ino) before and after `flock`, and rejected without any
  chmod/write/truncate/identity change (`test_preexisting_unsafe_lock_rejected_without_mutation`
  proves mode/inode/bytes retained). PASS.
- **4.5**: `CheckResult.to_dict()` remains the sole serializer; `_valid_details` accepts only
  `None` or exactly four closed records in `codex,qwen,claude,pi` order with exact profile
  pairing, one shared valid invocation UUID, terminal state, and valid result/failure relation;
  the closed field-set check rejects unknown/sensitive fields (argv, output, credentials, etc.),
  and the negative matrix test covers extra/missing/reordered/duplicate/malformed/sensitive/
  cross-invocation/cross-provider/cross-profile/arbitrary-dict inputs. PASS.
- **Adjudication — self-contained validator instead of `jsonschema` in the production path:**
  ACCEPTED. AM2 §7 lists "new dependency" as a hard stop; `harness_qa/core/result.py` currently
  has zero external dependencies and importing `jsonschema` there would add one to the production
  QA path. The mirrored enum/field constants risk drift from `process_lifecycle.py`, but the
  `qa.provider-probe-result.v1` contract is frozen, and the adoption suite independently
  cross-validates real probe output against the actual JSON-Schema contract file
  (`test_clean_exact_four_policy_order`), which would surface any mirror drift. Sound choice,
  properly disclosed.

## Criterion 5 — fresh validation re-runs (all executed by this reviewer, this session): PASS

| Validation | Result |
|---|---|
| `python3 scripts/testing/test-qa-provider-probe-adoption.py` | **18/18 OK** (8.8s) |
| `python3 scripts/testing/test-qa-provider-probe-lifecycle.py` (frozen C1C suite) | **39/39 OK** (66.5s) — unaffected |
| `bash scripts/testing/verify-flake-first-roadmap-completion.sh` | **611 pass, 0 fail**, exit 0 |
| `py_compile` (probe, result, adoption test, process_lifecycle) | clean |
| `bash -n` (verifier, smoke) | clean |
| `git diff --check` (worktree + cached) | clean |
| Secret scan over the four-subject diff | no matches |
| Daemon-publication pattern | no `threading.Thread(target=publication…)`; only the pre-existing observer reader/ticker threads, deterministically joined |

## Criterion 6 — governance trail and prohibitions: PASS

- Canonical writers throughout: PULSE/RESUME are aq-event projections
  (`.agents/events/a2a-events.jsonl`); no hand edits observed.
- **Ordering correct this time:** implementer `resume.update` event 2026-07-19T18:30:09Z →
  candidate file mtimes 18:40:07Z–18:47:14Z → implementer `pulse.append` 18:50:41Z (PULSE line
  311, with full validation disclosure incl. the 611-vs-609 deviation). Resume/intent preceded
  edits; closing pulse followed completion.
- Chain integrity: rebind prep (PULSE 307) → owner implementation activation naming
  `bedd3eec…`/`711c8c6f…`, Sonnet implementer, 24h window (PULSE 310, within which the
  implementation occurred) → acceptance activation (PULSE 312, this review).
- Prohibitions: no fifth file (frozen five byte-exact), no frozen-path edit, no provider/network/
  live action in tests (offline fixtures only), no A2 work, nothing staged in the governed set,
  no self-acceptance. The implementer identity deviation (Codex→Sonnet, Rule-17) was disclosed
  and independently reviewed upstream.

## Required revision scope (fits the existing four-file ceiling; no new inventory)

1. **R-A1 (finding A):** drive the join inside the publication callback on the signal path:
   submit the provisional record, wait (bounded, inside the barrier budget) for the validated C1B
   terminal observer event, join/disable reader and ticker, apply the 4.2 validation, then in
   canonical mode write the single terminal heartbeat (`COMMITTED`) or synchronously `CANCEL` —
   and only then return. Make the post-return `_join_terminal` idempotent (no second write when
   `COMMITTED`; no write when `CANCELLED`).
2. **R-A2 (finding B):** remove the commit-independent canonical terminal-heartbeat write; a
   cancelled join must emit no terminal projection.
3. **R-A3:** add the AM2 §5 items 1-3 adversarial tests (default/custom/ignored SIGTERM/SIGINT
   paths, both input orders, identical/conflicting duplicates, cancel-without-write, post-boundary
   write-spy zero) using deterministic barriers, per AM2's explicit test contract.

A revised candidate requires new hash binding and a fresh independent acceptance per the standing
chain rules. Criteria 1, 3, 5, and 6 findings carry forward and need only re-verification against
the revised bytes.

VERDICT: REQUEST_REVISION — the candidate's publication-barrier interpretation does not match AM2 §4.1: the callback returns before the join is COMMITTED or CANCELLED, so `completed` is acknowledged with no terminal projection commit and no reader/ticker join (zero terminal write on default-disposition signals, post-handler-return write on custom/ignored), and canonical mode writes a terminal heartbeat even when the join cancels, contrary to "cancels without writing" / "emits no terminal projection".
