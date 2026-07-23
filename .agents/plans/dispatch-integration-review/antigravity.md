# Antigravity — Independent Critique Review: Router/Claim Dispatch Integration

**Reviewer Model:** Antigravity (Gemini 3.5 Flash)
**Task ID / Round:** `dispatch-integration-review`

---

## 1. Resolution A-vs-B Decision & Reasoning

**Verdict: ADOPT-B-CONFIRMED**

### Rationales:
1. **Preservation of the Golden Source Manifest (L2B):**
   * The `local-inference-l2b-payload-golden.json` is a hard boundary artifact that locks the hashes of critical transport-surface files, including `dispatch.py`. Modifying `dispatch.py` directly (Resolution A) drifts this signature, breaking the integrity constraints established in that parallel reliability track.
   * A drift detector's signal should only be overridden if the file *must* change for its own core purpose.
2. **Proper Separation of Concerns:**
   * Claiming and routing orchestration are concern-level behaviors that manage *how* dispatches run and coordinate between lanes. They do not belong inside low-level, frozen inference-transport wrappers.
   * `delegate-to-local` (and other `delegate-to-*` shims) already act as the entry point shims responsible for converting CLI flags into actual executions. Injecting the consult phase here keeps the transport logic clean and untouched.
3. **Universality:**
   * Resolution B exposes `dispatch_consult.py` as a CLI command. This enables all lane shims (local, codex, gemini, antigravity) to easily call the same consult/release workflow via subprocesses, avoiding language-specific import requirements or duplicated Python boilerplate across lanes.

---

## 2. Critique of the Library (`dispatch_consult.py`)

1. **Fail-Open Contract:**
   * The fail-open implementation is robust and complete. Any error in `aq-role-route` or `aq-slice-claim` (such as tool missing, OS execution failures, timeouts, empty stdout, or unparseable JSON) successfully degrades the outcome to `ok=True, degraded=True` without interrupting the active runner process.
   * The CLI subcommand wrapper (`_cli_consult`) is protected by a catch-all exception handler that gracefully formats a fallback result (`ok=True`, `degraded=True`) and exits 0. This ensures Python-level exceptions cannot block the calling bash script.
   * **Only a healthy, parseable `already-held` response from the claim tool will block the launch (returning `blocked=True` and exit code 3).** This is the correct, intended behavior.
2. **Release Cross-Claim Safety:**
   * `release_after_dispatch` guards against releasing someone else's claim by:
     - No-oping (returning `False`) early if `result.claim_token` or `result.claim_owner` is missing.
     - Specifically matching the claim owner: calling `release <subject> --owner <owner>`. The underlying `aq-slice-claim` binary will reject the release attempt with `not-holder` if the owner doesn't match the current lockholder.
3. **Command Injection and Execution Safety:**
   * No shell-based subprocess invocation (`shell=True`) is used.
   * Executables are invoked via an argv list with absolute paths (`sys.executable` + resolved path). Command injection via arguments is not possible.
   * Timeout checks (`DEFAULT_SUBPROCESS_TIMEOUT = 8.0`) prevent stuck subprocesses from blocking harness execution.
4. **Test Load-Bearingness:**
   * The 12 unit tests in `scripts/testing/test-dispatch-consult.py` are highly effective and load-bearing.
   * **Negative control check:** The inclusion of the `_fail_open=False` test specifically validates that the code would block without the fail-open toggle, ensuring the fallback code paths are not vacuous.
   * The CLI subprocess tests successfully execute the real `__main__` entrypoint of `dispatch_consult.py`, ensuring argv handling, JSON deserialization, and exit codes are verified.
   * Test 6 asserts that `dispatch.py` contains no `dispatch_consult` references, ensuring the L2B frozen constraint is maintained.

---

## 3. Verification Details
* Run `git diff HEAD -- scripts/ai/lib/dispatch.py` returned empty output, confirming `dispatch.py` is byte-identical to HEAD (sha256 `1b083b1025877385cb4e295234edd23a61a85aae554393fb87792c732e01dd92`).
* Executed `python3 scripts/testing/test-dispatch-consult.py` which completed successfully with all 12/12 checks passing.

VERDICT: ADOPT-B-CONFIRMED
