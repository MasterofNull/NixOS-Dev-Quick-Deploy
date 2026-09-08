# Binding Review — P1 Guided-Install Slice (feat/aqos-p1-guided-tui)

Reviewer: independent, adversarial (Claude, this session). Did not author the code.
Worktree reviewed: `/tmp/aqos-golden-fix` (branch `feat/aqos-p1-guided-tui`).
First pass HEAD: `fb4ec61b` (2026-09-08) — **FAIL** (silent data-loss on the real guided→resolve seam).
Re-review HEAD: `5c95ff79` (2026-09-08) — fix commit on top of `fb4ec61b`, no history rewrite.

Files reviewed:
- `scripts/ai/aqos-guided-install`
- `scripts/testing/test-aqos-guided-install.py`
- `scripts/testing/test-aqos-adapter-parity.py`
- Supporting (read for verification): `scripts/ai/lib/aqos_install_resolver.py`, `scripts/ai/aqos-install-resolve`, `scripts/ai/lib/ai_fit.py`, `scripts/ai/lib/hw_probe.py`.

---

## First-pass finding (HEAD fb4ec61b) — FAIL, for the record

`build_guided_request()` emitted a full `request_plan` shape (`{artifact_type, schema_version, selection: {...}, host_target}`) to `--out`, while the tool's own printed step 1 said `aqos-install-resolve --adapter guided --request <file>`. `normalize_adapter("guided", payload)` in `aqos_install_resolver.py` reads `payload["answers"]`, not `payload["selection"]` — on the real guided output, `answers` was `None`, so the resolver silently normalized to `selection: {}`, dropping the operator's AI-on / extra-role choices with no error. Live-reproduced at the time: feeding a real `--out` file (built with `--ai yes --role role.gaming`) through the exact printed `--adapter guided` command produced `selection: {}` instead of the chosen values. The parity suite at that HEAD did not catch this because it hand-fabricated its own `{"answers": {...}}` "guided" fixture rather than calling the real `aqos-guided-install` producer — a fixture-concealment defect, not a logic defect in the resolver itself.

## Re-review (HEAD 5c95ff79) — fix verified

### The fix (read in full, `git show 5c95ff79`)
- `build_guided_request()` now emits the guided-**adapter input** it always claimed to: `{"answers": {golden_profile, roles, include_local_ai}, "host_target": ...}` (aqos-guided-install:70-77). This is exactly the shape `normalize_adapter("guided", ...)` reads.
- `preview()` updated to read `request["answers"]` (aqos-guided-install:81).
- `main()`'s `--hardware` load is now wrapped in `try/except (OSError, ValueError)`, printing a clean `error: could not read hardware probe ...` message and returning exit code `2` instead of an uncaught traceback (aqos-guided-install:120-127) — closes the point-4 CONCERNS from the first pass.
- Root-cause fix on the producer side (per Rule 19), not a resolver-side workaround — correct fix location, since `normalize_adapter`'s contract (`answers` for guided, `proposal` for ai) is shared with the `ai` adapter and other callers; changing the producer to match the documented contract is the minimal correct change.

### 1. Non-destructive — PASS (unchanged)
The write-gate (`if args.out: args.out.write_text(...)`, aqos-guided-install:133-134) and the pure `run()` core are untouched by this fix. Re-confirmed no subprocess/os.system/shutil mutation calls in the file.

### 2. Hardware-honest optional-AI — PASS (unchanged)
`ai_decision()` logic (aqos-guided-install:37-59) is byte-identical to the first pass. Verdict-driven auto mode and explicit-choice-with-warning behavior unaffected by this fix.

### 3. ONE ENGINE — **PASS, independently reproduced live**

Reran the exact reproduction from the first pass, on the new HEAD:
```
$ python3 scripts/ai/aqos-guided-install --host-target parityhost --ai yes --role role.gaming \
    --out /tmp/aqos-golden-fix-req3.json --authorize
...
  1. resolve : scripts/ai/aqos-install-resolve --adapter guided --request /tmp/aqos-golden-fix-req3.json
...

$ cat /tmp/aqos-golden-fix-req3.json
{
  "answers": {
    "golden_profile": "aqos-workstation",
    "include_local_ai": true,
    "roles": ["role.gaming"]
  },
  "host_target": "parityhost"
}

$ python3 -c "
import sys, json
sys.path.insert(0, 'scripts/ai/lib')
import aqos_install_resolver as resolver
raw = json.load(open('/tmp/aqos-golden-fix-req3.json'))
normalized = resolver.normalize_adapter('guided', raw)
print(json.dumps(normalized, indent=2))
"
{
  "artifact_type": "request_plan",
  "schema_version": "aqos-install-plan/v1",
  "selection": {
    "golden_profile": "aqos-workstation",
    "include_local_ai": true,
    "roles": ["role.gaming"]
  },
  "host_target": "parityhost"
}
```
The operator's actual choices (`--ai yes`, `--role role.gaming`) now survive the exact command the tool prints, byte for byte. The silent-data-loss defect is closed.

**Test coverage now certifies the real seam, not a fixture:**
- `test-aqos-guided-install.py::test_guided_output_round_trips_through_the_guided_adapter_no_data_loss` (lines 82-95) loads the real `aqos-guided-install` file via `SourceFileLoader`, calls the real `build_guided_request()`, feeds its output through the real `resolver.normalize_adapter("guided", ...)`, and asserts `include_local_ai`/`roles`/`golden_profile` survive. This is exactly the check that would have caught the original bug (confirmed by inspection: with the old `request_plan`-shaped `build_guided_request`, `normalized["selection"]` would have been `{}` and this test would fail).
- `test-aqos-adapter-parity.py::test_REAL_guided_producer_matches_manual_no_data_loss` (lines 101-119) loads the real producer module (`_load_guided()`, `SourceFileLoader` against `scripts/ai/aqos-guided-install`), calls its real `build_guided_request()`, resolves it through `--adapter guided`, and asserts a byte-identical canonical lock and projection versus the equivalent `manual` request, plus a non-empty `roles` assertion explicitly guarding against the old silent-empty-selection regression. This test genuinely exercises the producer script on disk — it is not a hand-typed payload standing in for it.
- Both files' docstrings/comments explicitly document why the fix and the new tests close the fixture-concealment gap, and reference this review by name.

I independently confirmed these are real (not decorative) assertions by reading the full diff and by separately re-deriving the same result outside the test harness (above) — the test and my independent reproduction agree.

### 4. NO secret/PII, fail-safe on bad input — **PASS (upgraded from CONCERNS)**
Re-ran the bad-input cases live on the new HEAD:
```
$ python3 scripts/ai/aqos-guided-install --hardware /nonexistent-file.json
error: could not read hardware probe /nonexistent-file.json: [Errno 2] No such file or directory: '/nonexistent-file.json'
EXIT: 2

$ echo "not json at all" > /tmp/aqos-bad-hw.json
$ python3 scripts/ai/aqos-guided-install --hardware /tmp/aqos-bad-hw.json
error: could not read hardware probe /tmp/aqos-bad-hw.json: Expecting value: line 1 column 1 (char 0)
EXIT: 2
```
Both a missing file and malformed JSON now produce a clean, single-line operator-facing error and exit code 2 — no raw traceback, no mutation. No secrets/credentials/tokens found in any reviewed file (re-confirmed unchanged from first pass).

---

## Test output (verbatim, HEAD 5c95ff79)

```
$ PATH=/run/current-system/sw/bin:$PATH python3 scripts/testing/test-aqos-guided-install.py
{
  "ai": {
    "include_local_ai": false,
    "reason": "a catalog model fits with recommended headroom and GPU offload is available",
    "recommended_model": "qwen3.6-35b",
    "verdict": "recommended",
    "warning": null
  },
  "request": {
    "answers": {
      "golden_profile": "aqos-workstation",
      "include_local_ai": false,
      "roles": []
    },
    "host_target": "h"
  }
}
test-aqos-guided-install: ok 6/6
EXIT: 0
```

```
$ PATH=/run/current-system/sw/bin:$PATH python3 scripts/testing/test-aqos-adapter-parity.py
test-aqos-adapter-parity: ok 4/4 (guided==ai==manual==legacy + REAL producer, byte-identical)
EXIT: 0
```

---

## Summary

| # | Check | First pass (fb4ec61b) | Re-review (5c95ff79) |
|---|-------|------------------------|------------------------|
| 1 | Non-destructive | PASS | PASS (unchanged) |
| 2 | Hardware-honest optional-AI | PASS | PASS (unchanged) |
| 3 | One engine (guided==manual==AI) | **FAIL** — silent data loss on the real seam | **PASS** — live-reproduced fix; new tests exercise the real producer, not a fixture |
| 4 | No secret/PII, fail-safe on bad input | CONCERNS — raw traceback on bad `--hardware` | **PASS** — clean error + exit 2, live-verified |

The fix is root-cause (producer-side, per Rule 19), small, and directly targeted at the defect I found. I independently reproduced both the original bug (at `fb4ec61b`) and its resolution (at `5c95ff79`) outside the test suite, and confirmed the new regression tests genuinely drive the real `aqos-guided-install` script rather than a hand-fabricated fixture standing in for it. No new concerns introduced.

OVERALL: PASS
