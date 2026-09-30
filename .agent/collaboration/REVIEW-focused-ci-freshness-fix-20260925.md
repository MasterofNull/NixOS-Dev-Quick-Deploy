# Binding Review — focused-ci freshness-class WARN fix

- **Subject:** branch `factory/fix-focused-ci-freshness-warn` @ `ebffbcb9`, based on `origin/main` (HEAD `2247de61`).
- **Files:** `scripts/governance/run-focused-ci-checks.sh` (+47), `.agent/WORKAROUND-REGISTER.md` (+47).
- **Reviewer:** Claude Opus 4.8 — independent binding reviewer (COMMIT-GATE change, reviewed adversarially, read-only).
- **Reviewed-subject-sha256:** `bfa0db7545778bb55c3c8c921fd07dd6c254437d3dd6c160ff54446051abdddc`
- **Reproduced digest:** `command git diff origin/main..factory/fix-focused-ci-freshness-warn | sha256sum` → `bfa0db7545778bb55c3c8c921fd07dd6c254437d3dd6c160ff54446051abdddc` ✓ **MATCH — no subject drift.**

## Disposition

**APPROVE.** The fix cannot be used to downgrade a real regression to WARN. It is in fact strictly stricter than tier0's existing freshness mechanism (it adds a content-marker guard tier0 does not have). No HIGH or MEDIUM findings.

## Control-flow trace (the load-bearing verification)

The new branch is inserted as an `elif` **before** the `else` that sets `any_failed = True`
(`scripts/governance/run-focused-ci-checks.sh:186-207`, branch version):

```
if exit_code == 0:            -> PASS
elif exit_code in SKIP_...:   -> skip
elif mode == "--pre-commit" and _is_freshness_time_expiry_failure(check_id, stdout+stderr):
                              -> WARN  (result_status="warn"; DOES NOT set any_failed)
else:                         -> FAIL, any_failed = True
```

`_is_freshness_time_expiry_failure` (`:78-81`) returns True **only if BOTH**:
(a) `check_id in FRESHNESS_CLASS_CHECK_IDS` = `{"model-catalog-freshness"}` (`:60`), and
(b) the combined `stdout+stderr` contains one of `FRESHNESS_TIME_EXPIRY_MARKERS` (`:69-73`).
The `elif` additionally requires `mode == "--pre-commit"`. Exit aggregation (`sys.exit(1 if any_failed else 0)`, `:232` base / end of loop) is unchanged; `warn` never touches `any_failed`. Timeout / FileNotFound have their own `except` blocks that always set `any_failed = True` — untouched by the fix.

- `check_id` is sourced from the registry entry's `"id"` (`:109`), confirmed keyed correctly.
- Registry entry `model-catalog-freshness` invokes exactly `python3 scripts/testing/test-model-catalog-freshness.py` (`config/validation-check-registry.json`), the same producer tier0's `0.10.5` wraps.

## Marker fidelity + spoof analysis

The 3 markers are the **exact** `AssertionError` strings the producer raises for its elapsed-days assertions:
- `"model profile review is stale"` → `test-model-catalog-freshness.py:50`
- `"model probe is stale"` → `:51`
- `"model catalog review is stale"` → `:60`

**Structural assertions cannot carry a marker.** The producer's structural messages (`:44-49, 54, 58-59, 63-66`) — `model_id is required`, `probe_model_id must match model_id`, `model_path is required`, `catalog metadata must expose ...`, `/api/models must expose freshness payload`, `dashboard Model Lifecycle must render freshness`, etc. — contain **none** of the 3 marker substrings (note `:44`'s "freshness window" ≠ any marker). `assert_true` raises on the **first** failing assertion and is **silent on success** (`:24-26`), so exactly one message ever reaches output, and the traceback shows only the failing call site. There is therefore **no execution ordering** in which a structural failure and a stale-marker string co-occur in the captured output — a structural regression always falls through to the HARD `else`. Spoofing the content guard via a structural failure is not reachable with the current producer.

Residual coupling (LOW, informational, no action required): the guard depends on the exact producer strings. If those elapsed-days messages are later reworded without updating the markers, freshness failures would begin HARD-failing pre-commit again — i.e. the coupling fails **closed** (toward enforcement), the safe direction; it can never silently start over-matching structural failures.

## Mechanism vs tier0

Mirrors tier0's approach (`tier0-validation-gate.sh:891-940`): `--pre-commit`-gated, hardcoded id set because the registry carries no class field (verified: entries only have `"tier": structural|behavioral`, unrelated to time-expiry). The focused-ci fix keys by the registry `id`; tier0 keys by aq-qa's `0.10.5` — both point at the same producer. The added `FRESHNESS_TIME_EXPIRY_MARKERS` content guard is an **enhancement over** tier0 (tier0 downgrades `0.10.5` on any of-that-id failure once `nonclass_failing` is empty, including a structural failure of the same script). Not a divergent second mechanism — it is the same id-list shape plus a tighter guard, documented in WR-9. (Pre-existing tier0 latent gap noted for a possible follow-up; out of scope for this branch.)

## Findings

- No HIGH findings. No gate-weakening path found.
- No MEDIUM findings.
- **LOW (informational):** marker/producer string coupling fails closed (above); worth a one-line comment in the producer if desired. Optional.
- **LOW (out of scope):** tier0's `0.10.5` block lacks the content-marker guard this fix adds, so tier0 could WARN a structural `0.10.5` failure when it is the only failing check. Pre-existing (WR-5), not introduced here; candidate follow-up to bring tier0 to parity with this stricter guard.

## Explicit verdicts

1. **Freshness WARNs only on genuine time-expiry in pre-commit:** PASS — gated on check-id ∈ set AND exact stale-marker in output AND `--pre-commit`; structurally impossible for a structural failure to match.
2. **Non-freshness checks + structural failures still HARD:** PASS — any check-id outside the set, and any non-time-expiry failure of `model-catalog-freshness` itself, falls to the unchanged HARD `else` (`any_failed=True`). Verified via the author's synthetic always-failing canary and by control-flow trace.
3. **`--pre-deploy` / `--maintenance` still HARD:** PASS — downgrade `elif` requires `mode == "--pre-commit"`; other modes fall to HARD `else`.
4. **No timestamp gaming:** PASS — `git diff origin/main..branch -- config/model-profile.json` is empty; WR-9 explicitly records the timestamp lapse as tracked maintenance, not fixed here.

WR-9 entry matches the register's format and accurately describes the fix.

VERDICT: APPROVE
