# QPPR C1C-AM3 independent design/authorization review

**Reviewer identity:** claude-subagent-qppr-c1c-am3-reviewer
**Model:** Claude Opus 4.8 (flagship-fallback lane — model-independent adjudication)
**Role:** independent architecture / security / SRE / workflow / authorization reviewer
**Reviewed:** 2026-07-19 UTC
**Scope:** design + inactive-authorization gate only. No implementation exists; no candidate acceptance is in scope. A PASS here makes the pair eligible for owner activation only — it activates nothing and is not acceptance.
**Authorship stake:** none (subjects drafted by the Fable 5 orchestrator session).

## Recomputed hashes (all verified against declarations)

| Artifact | Declared | Recomputed | Match |
|---|---|---|---|
| C1C-AM3 amendment (SUBJECT) | `fd0c585f…c9615` | `fd0c585fbf23a3023b69638c41ae232f021b94463c5573269317e61b3d1c9615` | ✓ |
| C1C-AM3 authorization (SUBJECT) | `88d58cb6…1ef6` | `88d58cb6f3f3ae3eb1000674824ee2ce7b57b15ebc06e13e436d071260a31ef6` | ✓ |
| C1C-AM2 amendment (contract SSOT) | `02f4c531…8dfc` | `02f4c5317faa80aac7d2872d04eafa8cf5337c9297f1a335fe737160d06e8dfc` | ✓ |
| C1C-AM2 authorization (consumed) | `0145aaba…d1135` | `0145aabac0d538831940c86d30bd750e6d4484e9ee06238bd7636c34269d1135` | ✓ |
| C1C-AM2 authorization review (PASS) | `73b16202…7364` | `73b16202d6ae9991677ddbe0140bfef9b730b98cefa187401cc9982172067364` | ✓ |
| C1C-AM2 candidate rejection | `544b84dd…a9b6` | `544b84dd5a01c7b57e9ebcf27b7a0849a3eb395b1642b52f9ac7fce039a1a9b6` | ✓ |
| C1C-AM1 SRE amendment | `bced486a…4f3c` | `bced486ad8af5ced589b71a853ccdffe2927dd5288b650e0c2b48c7eaa924f3c` | ✓ |
| rejected evidence — process_lifecycle | `f01a4608…2716` | `f01a460819a5e1b6deef2688ec1fb5c64aa0b38f6a4f2a1080bdcc5800692716` | ✓ |
| rejected evidence — lifecycle-test | `61b2301e…a5fd` | `61b2301e8574c02729d4ed0c13b8dd8be637254e380b7c93afeafe1d8dc8a5fd` | ✓ |
| process-owner predecessor | `ceef8fbe…0b38e` | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` | ✓ |
| lifecycle-test predecessor | `4dc49ef8…efac7` | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` | ✓ |
| frozen observer test | `a17d70be…ee63b` | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` | ✓ |

No hash drift. Both subjects and the entire declared lineage bind to exact on-disk bytes. No hard stop on hashes.

## Findings

### 1. Code-anchor accuracy — FAIL (blocking)

Verified against predecessor `ceef8fbe…` (function `run_owned_process`, def at line 740):

- **1051–1057 = publication invocation (daemon thread + join): CORRECT.** Line 1051 `if controller.first_signal is not None and publication is not None:`; 1055 `worker = threading.Thread(target=publication, args=(dict(provisional),), daemon=True)`; 1056 `worker.start()`; 1057 `worker.join(timeout=remaining)`. Byte-exact.
- **1061 unconditional `_INVOCATION_LOCK.release()`: CORRECT.** Line 1061 is exactly that call; executes unconditionally on the success path after the join.
- **1065 `_restore_and_redeliver(…)`: CORRECT.** Line 1065 `disposition_class, redelivered = _restore_and_redeliver(redelivery_controller)`. Byte-exact.
- **R3 "≤5-second budget … computed at line 1053": minor off-by-one.** Line 1053 is the explanatory comment; the arithmetic `remaining = max(0.0, signal_started + 4.9 - time.monotonic())` is on line 1054. Correct region, correct value (4.9 ≤ 5s); non-blocking.
- **R5 "the existing `finally` (predecessor lines 1080-1119 region)": WRONG — this is the blocking defect.** Lines 1080–1082 are the tail of the success-path `return _result(...)` inside the `try`; **line 1083 is `except Exception:`**; 1084–1159 is the `except` handler body. **There is no `finally:` keyword anywhere in 1080–1119.** The actual `finally:` clause is at **line 1160**, body 1161–1186. Critically, the `_restore_and_redeliver(…)` call that R5's fail-stop must prevent lives at **line 1184** (`if controller is not None: … _restore_and_redeliver(redelivery_controller)`) — *outside* the cited 1080–1119 range — and the finally's own lock release is at line 1178 (`if lock_held: _INVOCATION_LOCK.release()`), also outside the cited range. The cited region captures only the `except` handler's release at 1117–1119, not the finally's restore/release the requirement is actually about.

R5 is the single most safety-critical requirement (the mechanical fail-stop) in a document whose stated raison d'être (lines 14–18) is "it anchors every requirement to the exact code so the binding cannot be misread again." Mislabeling the `except Exception:` handler as "the `finally` block" and citing a line range (1080–1119) that excludes the actual `_restore_and_redeliver` (1184) and the actual finally release (1178) is precisely the un-misreadable-anchoring failure this document exists to prevent, and it materially raises the risk of the exact finally-leak defect that got the AM2 Haiku candidate rejected (rejection record item 2). Per the stated item-1 standard ("Wrong anchors in a document whose whole purpose is un-misreadable anchoring is a blocking defect"), this blocks.

Note the mechanism R5 prescribes (keep the lock acquired by not taking the `if lock_held` release branch; `controller = None` so the `if controller is not None` restore branch is skipped) is *state-variable-based* and, if implemented from the prose, does correctly neutralize both the `except` handler and the real finally. The defect is the anchor, not the mechanism — but the anchor is exactly what this document promised to get right.

### 2. Contract fidelity (AM2 SSOT preserved) — PASS

Every AM2 requirement is carried into AM3 without weakening:
- Record format `qa.provider-publication.v1|1|running|<absolute_deadline_monotonic_ms>\n` (AM2 L30 = AM3 R3 L49).
- Sequence-2 completed/cancelled/contract_violation (AM2 L33-34 = AM3 R4/R5).
- PIPE_BUF bound, ASCII, no identity/PID/argv/path/output/env/credential/verdict (AM2 L27,36 = AM3 R3 L52-53).
- C1B descriptor validation write-only/nonblocking/FIFO/FD_CLOEXEC (AM2 L37,55-56 = AM3 R3 L53-55).
- Pure classifier rule verbatim (AM2 L43-46 = AM3 R6 L79-82); depends only on validated record + injected same-host monotonic clock (AM2 L50-51 = AM3 R6 L81-82).
- Non-downgrade (AM2 L52 = AM3 R6 L83-85); unavailable-never-healthy (AM2 L52-53 = AM3 R6 L84 / R7).
- No worker/daemon/task/retry/second writer (AM2 L57 = AM3 R2 L44); no finite violation-path redelivery claim (AM2 L73 = AM3 L112-114); backpressure cannot alter cleanup or create fallback writer (AM2 L38 = AM3 R7 L90-91).

Extensions are disclosed strengthenings, not silent scope creep: explicit removal of the predecessor daemon-thread as the prohibited worker (R2, resolving the real contradiction AM2 named); mechanical fail-stop definition (R5); explicit post-terminal sequence-2 rejection (R6); zero-budget `cancelled` definition (R4). None weakens an AM2 rule.

### 3. Architecture / SRE soundness (R2/R5/R6) — PASS on decision, gated by finding 1's anchor

- **Synchronous invocation is implementable** in the predecessor flow: the daemon-thread block (1051–1057) sits in the `try` body between the guard (1051) and the release/restore epilogue (1061/1065); replacing it with a synchronous in-owner-thread call is a local, well-scoped edit.
- **Late-return mechanical fail-stop is implementable** via the two state variables the real code already switches on — `lock_held` (finally 1178, except 1117) and `controller` (finally 1181, except 1120). Setting `lock_held` so the release branch is skipped while leaving `_INVOCATION_LOCK` acquired, and `controller = None`, structurally suppresses restore/redeliver/release in *both* the `except` and the real `finally`.
- **Holding the invocation lock as permanent fail-stop is sound and disclosed.** `_INVOCATION_LOCK` is a module-global `threading.Lock` (line 86); a permanently-held lock forces every later `run_owned_process` to fail the non-blocking acquire at line 788 and return `probe_busy` at line 792 — verified, and this is exactly the disclosed "no later provider start" behavior. No undisclosed side effect: a never-released `threading.Lock` deadlocks only the intended probe path, clears on process restart, and creates no cross-thread ownership hazard.
- **Legacy path (no `publication_fd`) genuinely freezable:** the current guard (1051) keys only on first-signal + publication; making the synchronous path opt-in on `publication_fd` while retaining the daemon-thread block for the legacy branch preserves behavioral equivalence (R2 L45). Sound.
- **Zero-budget `cancelled` is coherent:** line 1054 already computes `remaining = max(0.0, …)`; a zero remaining budget means the callback is not run, so `cancelled` (not `completed`) is the correct sequence-2 — a genuine distinction, not a synonym.

The decision itself is architecturally correct; it is only the R5 anchor (finding 1) that undermines the implementability *guidance*.

### 4. Deterministic-proof adequacy — PASS

AM3's six proofs (L95-110) cover AM2's original six (on-time, never-return, late-return, isolated-fixture reap, fail-closed record validation, legacy/observer/SLO unchanged) and add coverage for both rejected-candidate failure modes: proof 6 (`rg threading.Thread` shows no new barrier-path thread) directly targets the daemon-thread-as-worker defect; proof 3's follow-up `run_owned_process` → `probe_busy` assertion and proofs 2/3's "no restoration/redelivery/lock release" prove the finally-leak is closed; proof 4 (sequence-2 after a classified violation rejected) targets wrong-event/post-terminal binding. Event-barrier + injected-classifier-time subprocess fixtures make never-return and late-return provable without sleep-only assertions (explicitly required, L93). Adequate.

### 5. Authorization discipline — PASS

Single-use + idempotency key with atomic consume-on-first-report and replay rejection (L4, L14, L78-79); exact command allowlist including the `threading\.Thread` scan with stated legacy-line exception (L61, L66); rejected-candidate evidence read-only with copy/import/execute prohibition (L49-50); activation requires exact authorization hash + implementer-identity restatement + SRE-ratification restatement + ≤24h activation/expiry window (L73-77); independent acceptance under a separate reviewed+activated grant (L84-85); Tier-0/staging/commit orchestrator-only (L86); downstream A1-AM3 NON-ACTIVATABLE and A2 blocked (L88-89). Complete.

### 6. Rule-17 tier deviation — PASS

The authorization (L6-12) names a balanced-tier (Sonnet) implementer and cites the Haiku AM2 candidate as measured capability-insufficiency. The rejection record substantiates this on disk: implementer "Claude Haiku 4.5 sub-agent" (L5), verdict REQUEST_REVISION, with two disqualifying failures — observer bound to the wrong contract (L28) and fail-stop that does not precede restoration/redelivery/lock release (L34) — matching the authorization's stated reasons verbatim (rejection VERDICT L64-66). The escalation ladder is recorded, not assumed (Codex quota-exhausted to 2026-07-25; local Qwen outside multi-site concurrent-safety envelope). Reasoning is evidenced.

### 7. Consistency with mandatory workflow — PASS with minor flag

AGENTS.md/WORKFLOW-CANON require mandatory `aq-session-start` hydration (canon L62), the Intent Lock (canon L327), and Atomic Pulse after every file write (canon L348). The authorization specifies the load-bearing closing pulse exactly (`scripts/ai/aq-event pulse …`, L67-69) and names session/intent/resume/pulse/handoff as non-staged control-plane evidence (L82-83). **Minor flag (non-blocking):** relative to a fully section-4-compliant grant, the authorization under-enumerates the implementer's *pre-work* governance obligations — it does not explicitly direct the implementer to run `aq-session-start`, take the Intent Lock, and seed RESUME before editing. These obligations apply to every agent by default via AGENTS.md/CLAUDE.md, so the omission is a completeness gap, not a contradiction. Recommend the revision add a one-line pre-work governance-event requirement mirroring the AM2-era B2 section-4 pattern.

## Verdict rationale

Hashes clean; contract fidelity, proof adequacy, authorization discipline, Rule-17 evidence, and SRE/architecture decision are all sound. The pair fails a single but blocking gate: the R5 fail-stop requirement — the most safety-critical clause — mislabels the predecessor `except Exception:` handler (line 1083) as "the `finally` block" and cites line range 1080–1119, which excludes the actual `finally:` (line 1160) and the actual `_restore_and_redeliver` (line 1184) it must neutralize. In a document whose declared purpose is un-misreadable code anchoring, this is a blocking defect per the item-1 standard and must be corrected before owner activation.

**Required revision (narrow):** in AM3 R5, replace "the existing `finally` (predecessor lines 1080-1119 region)" with an accurate reference — the cleanup epilogue spanning the `except Exception:` handler (release at line 1117) **and** the real `finally:` block at lines 1160–1186 (release at 1178, `_restore_and_redeliver` at 1184) — so the neutralization target is anchored to the bytes that actually perform restore/redeliver/release. Optionally (finding 7) add the implementer's pre-work session-start/Intent-Lock/RESUME governance obligation to the authorization.

VERDICT: REQUEST_REVISION — R5's central fail-stop requirement mis-anchors the restoration/redelivery/release site: it labels the `except Exception:` handler (line 1083) as "the `finally` block" and cites lines 1080-1119, which exclude the real `finally:` (1160-1186) and its `_restore_and_redeliver` call (1184); blocking under the un-misreadable-anchoring standard. All hashes verified clean; items 2,4,5,6 PASS; item 3 decision sound; item 7 minor non-blocking flag on pre-work governance-event enumeration.
