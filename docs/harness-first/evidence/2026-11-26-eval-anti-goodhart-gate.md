# Eval anti-Goodhart promotion and futility gate evidence

## 1. Objective and scope

Add fail-closed statistical promotion and queue futility decisions to the existing eval integrity library. Owned surfaces: `scripts/ai/lib/eval_integrity.py`, `scripts/testing/test-eval-integrity.py`, and this evidence file. Preserve the scorer trustworthiness API and its seven existing tests. No dependency, service, deployment, or loop-caller changes.

## 2. Harness-first discovery

Queried AIDB before implementation for `error-solutions eval_integrity promotion McNemar holdout harness-first eight evidence sections` (limit 2). The tool returned `documents_search_fallback` with two unrelated Nix document metadata records and no content; it supplied no reusable solution. Inspected only bounded ranges of the two owned Python files. Existing code supplied scorer discrimination, determinism, abstention, isolation and exec-scoring checks, but no promotion/cache/futility API.

## 3. Plan and design decisions

Plan emitted to stdout before editing: extend the stdlib module, retain its existing API, add focused regression cases, run the four requested checks and record evidence. The explicit three-file scope excludes PULSE, RESUME, backlog and shared workflow writes.

Cache keys hash sorted compact JSON of model identity, quantization, dataset hash and decode parameters. Promotion separately validates pairing/labels, both crash rates, selection sample size, baseline non-crash accuracy, error headroom, improvement direction, continuity-corrected McNemar significance and holdout ID separation. Every applicable check is recorded; failed check names appear in the reason. Invalid thresholds raise ValueError instead of producing a promotion decision.

## 4. Implementation and acceptance coverage

Added PromotionResult and FutilityDecision dataclasses, baseline_cache_key, promotion_gate and futility_breaker with stdlib-only helpers. Crashes count toward crash rates and never toward fail/pass paired transitions. Baseline accuracy uses baseline non-crash items; sample size uses the full selection mapping as specified. Holdout is required by default, must have valid paired labels and disjoint IDs, and must pass crash, directional improvement and significance checks. Explicitly supplied holdouts are validated even when the requirement is disabled.

Added seven test functions covering cache canonicalization and identity/parameter sensitivity; blank identity rejection; empty, mismatched and unknown-label pairs; 99% saturation and fewer than 20 baseline errors; 42% crashes on either side; n=39 rejection; n=40 noise (3 wins/1 loss, z=0.5), zero gains, regressions and ties; absent, leaked, invalid, flat and crash-heavy holdouts; significant disjoint gains (20 wins/2 losses, z=17/sqrt(22)); configurable thresholds and exact boundaries; crash pair exclusion; and futility streak/reset/crash behavior. All seven original tests remain in place.

## 5. Verification commands and verbatim output

Final verification run, all exit codes zero. Empty stdout/stderr for py_compile is represented by an empty output block; exit codes are annotations, not command output.


Command: `python3 -m py_compile scripts/ai/lib/eval_integrity.py scripts/testing/test-eval-integrity.py`

Exit code: 0

```text
```

Command: `ruff check scripts/ai/lib/eval_integrity.py scripts/testing/test-eval-integrity.py`

Exit code: 0

```text
All checks passed!
```

Command: `basedpyright scripts/ai/lib/eval_integrity.py scripts/testing/test-eval-integrity.py`

Exit code: 0

```text
0 errors, 0 warnings, 0 notes
```

Command: `python3 scripts/testing/test-eval-integrity.py`

Exit code: 0

```text
PASS reference exec_scorer certified TRUSTWORTHY (min margin 1.0)
PASS gate REJECTS a non-discriminating scorer (always-1.0)
PASS gate REJECTS a non-deterministic scorer (stdev 0.328348)
PASS gate REJECTS a scorer that grades infra-noise as a capability miss
PASS gate REFUSES to certify when golden set is agent-readable (anti-gaming)
PASS exec_scorer abstains on infra-noise (contention can't fake a regression)
PASS exec_scorer ranks good>bad across json_parse / py_compile / keyword
PASS baseline cache canonical SHA-256, order invariance, sensitivity and empty rejection
PASS promotion rejects empty, unpaired and unknown-label selection data
PASS promotion rejects 99% saturation, fewer than 20 errors and 42% crashes on either side
PASS promotion rejects undersized samples, small-N noise, zero gains and non-improvements
PASS disjoint selection/holdout gain: w_to_c=20 c_to_w=2 z_score=3.624412178045377
PASS promotion rejects missing, leaked, invalid, flat and crash-heavy holdouts
PASS configurable thresholds, exact boundaries, non-crash accuracy and crash pair exclusion
PASS futility stops repeated failures/high crashes and resets after promotion
ALL PASS
```

## 6. Security and failure-mode review

No secrets, service ports, URLs, subprocess execution, external dependencies or filesystem-topology changes introduced. Outcome labels, nonempty paired item sets and threshold domains fail closed. Nonfinite rate thresholds and z thresholds cannot silently bypass comparisons. Futility rejects summaries with missing/nonboolean promotion state or invalid latest crash rates. Missing crash_rate defaults to zero as an optional field.

Initial ruff run found an existing unused Optional import; removed that import in the owned module and reran all four checks successfully. Initial diagnostic (verbatim):

```text
F401 [*] `typing.Optional` imported but unused
  --> scripts/ai/lib/eval_integrity.py:36:35
   |
34 | from collections.abc import Mapping, Sequence
35 | from dataclasses import dataclass, field
36 | from typing import Any, Callable, Optional
   |                                   ^^^^^^^^
37 |
38 | # A scorer under test: (response_text, task_dict) -> {"score": 0..1, "abstain": bool}
   |
help: Remove unused import: `typing.Optional`

Found 1 error.
[*] 1 fixable with the `--fix` option.
```

## 7. Activation boundaries and limitations

These are library APIs exercised directly by the standalone test runner. This slice does not wire them into existing autonomous callers, prove an operational queue has adopted them, or deploy a running service. Holdout locking and prevention of repeated tuning against holdout results remain caller responsibilities; the library verifies ID separation, not access-control provenance. McNemar uses the requested continuity-corrected z approximation, not an exact test or sequential/multiple-testing correction.

No tier0, commit, staging, deployment or service restart was performed, per the headless slice instructions. The task supplies no eight-section heading template; this record uses eight explicit sections covering scope, discovery, plan, implementation, verification, security, limitations and handoff.

## 8. Handoff and reproducibility

Modified only the three owned paths, leaving changes unstaged for orchestrator review. The pre-evidence git diff whitespace check passed; final whitespace and scope checks follow this write. Reproduce with the four commands above. The existing nondeterministic-scorer test intentionally uses random scores, so its displayed stdev varies; the captured output above is verbatim from the final passing run.

Root cause addressed: scorer trustworthiness alone cannot certify that a candidate's benchmark gain is statistically reliable or that a queue should continue spending compute. Added explicit promotion evidence and queue-stop decisions without changing scorer behavior.
