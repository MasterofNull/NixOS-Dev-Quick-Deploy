# QPPR C1C-AM3 independent design/authorization review — R2 (revised pair)

**Reviewer identity:** claude-subagent-qppr-c1c-am3-reviewer
**Model:** Claude Opus 4.8 (flagship-fallback lane — model-independent adjudication)
**Role:** independent architecture / security / SRE / workflow / authorization reviewer
**Reviewed:** 2026-07-19 UTC
**Scope:** R2 re-review of the revised C1C-AM3 pair after R1 REQUEST_REVISION. Design + inactive-authorization gate only. No implementation exists; no candidate acceptance is in scope. A PASS here makes the pair eligible for owner activation only — it activates nothing and is not acceptance.
**Prior artifact:** `C1C-AM3-AUTHORIZATION-REVIEW.md` (R1, REQUEST_REVISION) — retained lineage, not modified.
**Authorship stake:** none.

## Recomputed hashes (revised subjects + unchanged predecessor/lineage)

| Artifact | Declared | Recomputed | Match |
|---|---|---|---|
| C1C-AM3 amendment **revision 2** (SUBJECT) | `71911585…f0f6` | `719115853f0129c13dadad49de3cc736edddec1f64d9d9b9c4b973949cd2f0f6` | ✓ |
| C1C-AM3 authorization **revision 2** (SUBJECT) | `95d8d947…4474` | `95d8d947d69ca37bd996e8240f4ee56aa231db93d159b8b5eebca3d649204474` | ✓ |
| process-owner predecessor (frozen ceiling) | `ceef8fbe…0b38e` | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` | ✓ |

Both revised subjects match the coordinator's declared hashes exactly; the predecessor ceiling is unchanged. Lineage hashes (C1C-AM2 amendment/authorization/review/rejection, C1C-AM1 SRE amendment, both rejected-evidence files, lifecycle-test predecessor, frozen observer test) were fully verified in R1 and are re-cited unchanged in the revised authorization's binding table; no hard stop on hashes.

## Re-adjudication

### 1. Code-anchor accuracy — PASS (R1 blocking defect resolved)

The revised R5 (revision-2 lines 62-82) replaces the R1 mis-anchor with two byte-accurate path citations, each verified against predecessor `ceef8fbe…`:

- **`except Exception:` handler at line 1083** — verified: 1083 is `except Exception:`.
  - **lock release at line 1118** — verified: 1118 is `_INVOCATION_LOCK.release()` (1117 is the `if lock_held:` guard).
  - **`_restore_and_redeliver(…)` at line 1142** — verified: 1142 is `disposition_class, redelivered = _restore_and_redeliver(redelivery_controller)`.
- **`finally:` block at line 1160** — verified: 1160 is `finally:`.
  - **lock release at line 1179** — verified: 1179 is `_INVOCATION_LOCK.release()` (1178 is the `if lock_held:` guard).
  - **`_restore_and_redeliver(…)` at line 1184** — verified: 1184 is the finally's restore call under `if controller is not None:` (1181).
- **"A violation path that reaches line 1118, 1142, 1179, or 1184 with live state is an automatic acceptance failure"** — all four cited lines are the precise release/restore call sites. Correct.

On the R1-vs-revision line-number discrepancy the coordinator flagged: the revision's **1118/1179** (release calls) are correct; my R1 report's 1117/1178 pointed one line high, at the `if lock_held:` guards rather than the `_INVOCATION_LOCK.release()` calls. The revision holds to the correct byte positions. R1's finding that the actual `finally:` is at 1160 (not the R1-document's cited 1080-1119) is now honored, and the `_restore_and_redeliver` at 1184 that R1 showed was excluded from the old citation is now explicitly named.

The revised R5 also adds a substantively correct new requirement: **"The violation exception must not be classifiable as the generic `except Exception:` recovery case — a dedicated exception type re-raised before that handler's recovery logic is the expected shape."** This is sound and necessary against the bytes: the handler at 1083 catches any `Exception`, and its early guard at lines 1086-1087 (`if controller is None and identity is None and not lock_held: raise`) does not exempt a naive `_PublicationContractViolation`, so without a dedicated non-recoverable type (or an early re-raise ahead of the recovery branch) the violation would fall through to lock release (1118) and restore (1142). This directly closes the AM2 Haiku candidate's disqualifying failure #2 (raised a violation type that the finally still restored past). Implementable within the ceiling file.

R1's byte-exact anchors are undisturbed: R1 publication invocation 1051-1057 (daemon thread + join), unconditional release 1061, restore 1065 — all still correct in revision 2 (R1/R2/R3 text unchanged).

**Minor, non-blocking (carry-forward from R1, unchanged):** R3 (line 51) still cites "line 1053" for the ≤5-second budget; 1053 is the explanatory comment, the arithmetic `remaining = max(0.0, signal_started + 4.9 - time.monotonic())` is at 1054. Correct region and value; not an acceptance anchor. **Minor, non-blocking (new observation):** the authorization "Exact grant" paraphrase (auth line 42) still reads "neutralizes the `finally` restoration state" in the singular, whereas the now-authoritative R5 correctly names both paths; the grant binds by reference to amendment R1-R7 and carries no line-number anchor, so this is a loose summary, not an anchor defect. Recommend aligning the paraphrase on a future touch; it does not block.

### 2. Contract fidelity (AM2 SSOT preserved) — PASS (reaffirmed, undisturbed)

Amendment R1-R4, R6, R7 and the deterministic-proof section are byte-identical to the R1-reviewed text; R5's change strengthens anchoring only and does not alter the contract it enforces (fail-stop before restoration/redelivery/lock-release, no worker, verbatim classifier rule, non-downgrade, unavailable-never-healthy, no finite violation-path redelivery). Every AM2 requirement remains preserved without weakening; the revision introduces no silent extension. Verified the R5 edit did not disturb the record format (R3), classifier rule (R6), or no-worker rule (R2).

### 3. Architecture / SRE soundness (R2/R5/R6) — PASS (reaffirmed and strengthened)

The synchronous-invocation decision, the lock-held→`probe_busy` fail-stop (verified at predecessor 788/792), the `controller = None` restore-suppression, the blocked-owner never-return structural safety, and the byte-frozen legacy path are all unchanged and sound. The new dedicated-exception-type requirement improves implementability guidance by making explicit that the generic recovery handler must not swallow the violation. No undisclosed side effect: a permanently-held module-global `threading.Lock` (line 86) forces later probes to `probe_busy` — the disclosed, intended "no later provider start" — clears on process restart, and creates no cross-thread ownership hazard.

### 4. Deterministic-proof adequacy — PASS (reaffirmed, undisturbed)

The six-proof section (revision-2 lines 102-119) is byte-identical to R1: covers AM2's original six plus both rejected failure modes (proof 6 threading.Thread scan; proofs 2/3 zero-restoration/redelivery/lock-release with the follow-up `probe_busy` assertion; proof 4 post-terminal/wrong-event rejection), event-barrier + injected-time fixtures, no sleep-only assertions.

### 5. Authorization discipline — PASS (reaffirmed; pulse obligation relocated, not lost)

Single-use + idempotency consume/replay rejection, exact command allowlist with the `threading.Thread` legacy-line exception, read-only rejected-candidate evidence, activation requirements (exact hash + identity + SRE-ratification restatement + ≤24h window), independent-acceptance separation, orchestrator-only Tier-0/staging/commit, and downstream A1-AM3/A2 gates are all intact. The R1 closing-pulse sentence formerly in the validation-commands section is not dropped — it is relocated and expanded into the new Governance-event obligations section (below). The binding table now correctly cites amendment revision 2 (`71911585…`) and retains the R1 REQUEST_REVISION review as lineage history (line 21).

### 6. Rule-17 tier deviation — PASS (reaffirmed, undisturbed)

Tier-deviation reasoning (auth lines 6-12) is unchanged and remains substantiated on disk by the rejection record (Haiku 4.5 implementer, REQUEST_REVISION, wrong-event binding + fail-stop after restoration/redelivery), with the recorded escalation ladder (Codex quota-exhausted to 2026-07-25; local Qwen outside the multi-site concurrent-safety envelope).

### 7. Governance-event obligations — PASS (R1 flag closed)

The revised authorization adds a "Governance-event obligations (canonical writers only)" section (auth lines 69-81) that fully closes the R1 item-7 gap. It specifies, in order: read `.agent/collaboration/RESUME.json`; run exactly once the exact `scripts/ai/aq-event resume …` invocation (objective/phase/hint/todo populated); run exactly once `pending-update add c1c-am3-20260719 …`; emit one `--action write` pulse (both paths in scope, truthful outcome) immediately after the candidate write; on finish the validate pulse plus `pending-update done`; on a mandatory stop the stop pulse plus `failed` (before edit) or `partial-success` (after edit); and "only these literal canonical writers may touch" governance evidence, direct edits prohibited. This matches WORKFLOW-CANON's mandatory session/RESUME hydration (canon L62), Intent Lock (L327), and Atomic Pulse (L348) obligations and mirrors the section-4 precedent pattern. Complete and consistent; no over-reach — `aq-event resume`/`pending-update` are control-plane writers, consistent with the authorization's own "control-plane evidence … is not staged" exclusion.

## Verdict rationale

Both R1 blocking defects are resolved. Item 1: R5 is re-anchored to the true bytes — except handler 1083 (release 1118, restore 1142) and real finally 1160 (release 1179, restore 1184), all four failure-lines byte-verified, both paths required unreachable-with-live-state, plus a correct new dedicated-exception-type requirement that closes the generic-handler swallow path. Item 7: the authorization now carries a complete governance-event obligations section. Items 2, 3, 4, 5, 6 were reaffirmed and confirmed undisturbed by the revision (item 3 modestly strengthened). Two residual imprecisions remain (R3's line-1053 comment-vs-1054 arithmetic; the grant paraphrase's singular "finally"), both explicitly non-blocking — neither is an acceptance anchor. Hashes clean on both revised subjects and the predecessor.

The pair is eligible for owner activation only. This review activates nothing and is not candidate acceptance; acceptance remains a separate independent grant, and Tier-0/staging/commit remain orchestrator-only.

VERDICT: PASS — R5 re-anchored to byte-verified 1083/1118/1142/1160/1179/1184 with both restoration paths named, unreachable-with-live-state required, and a correct dedicated-exception-type rule; item-7 governance-event obligations section added and canon-consistent; items 2-6 reaffirmed undisturbed; both revised-subject hashes and predecessor verified clean. Two non-blocking residual imprecisions noted (R3 line-1053, grant-paraphrase singular "finally"). Eligible for owner activation only; not acceptance.
