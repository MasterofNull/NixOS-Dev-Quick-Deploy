# Independent Security Review — Evidence Scope Fix

VERDICT: REQUEST_REVISION

Reviewed commit: `737bb428329d537ff7cf636d71aadf43d8f02b4a`

Reviewed subject (`git diff de84c9e3..review/evidence-scope-fix | sha256sum`): `5bbdce98c8623af36cfb751487a07b7adc068b647dc386ddadbcc02877f98c63`

1. **HIGH — TOCTOU still permits an unverified replacement check to execute**
   - File: `templates/factory-gate-bundle/gate-runner:337` and `templates/factory-gate-bundle/gate-runner:348-369`
   - Attack inputs -> outcome: begin with a valid receipt-bound installation; start `gate-runner --pre-commit`; after `canonical_scope()` returns success, but while an earlier legitimate check is still running, replace a later receipt-recorded check such as `checks.d/hard-50-lint.sh` with `#!/usr/bin/env sh; touch <sentinel>; exit 0` without changing either the receipt or manifest. The bash code subsequently re-globs/re-opens the repository path and executes the replacement. In the adversarial reproduction, the sentinel was created and the runner printed `PASS: hard-50-lint`; only the post-execution scope check detected the mutation, emitted `FAIL: execution did not cover the canonical installed check scope`, and returned 1. Detection after arbitrary code execution does not satisfy the before-execution security contract.
   - Bounded follow-up: couple verification to execution so the loop never re-opens a mutable repository path after validation (for example, execute already-open verified descriptors or exact-byte verified private snapshots), retain the post-run scope check, and add a deterministic race regression in which an earlier check blocks, a later check is replaced after validation, and the sentinel must remain absent.

2. **INFO — The reported static new-check + matching-manifest injection is closed faithfully**
   - File: `templates/factory-gate-bundle/gate-runner:272-345`
   - Attack inputs -> outcome: add executable `checks.d/hard-90-injected.sh` and a matching `MANIFEST.json` entry while leaving `.factory/gate-install.json` unchanged. The manifest hash no longer matches the receipt at lines 301-305, `canonical_scope()` returns false, and `SystemExit(3)` occurs inside the pre-execution Python block before the bash glob at line 348 or any check invocation at line 369. A mode-only mutation is also rejected by the receipt mode comparison; replacing a receipt-recorded check is rejected by its recorded sha256/mode unless its bytes and mode still match (apart from an assumed SHA-256 collision). This preserves the original receipt-bound manifest, per-check sha256/mode, and `receipt_expected` design rather than substituting a name-set shortcut.

3. **INFO — The three `canonical_scope()` copies are logically equivalent for acceptance, though textually divergent**
   - File: `templates/factory-gate-bundle/gate-runner:65-105`, `templates/factory-gate-bundle/gate-runner:289-329`, and `templates/factory-gate-bundle/gate-runner:410-450`
   - Attack inputs -> outcome: malformed/missing/symlinked manifest or receipt, manifest hash/mode mismatch, missing/extra/symlinked/non-executable check, check hash/mode mismatch, or disagreement among manifest names, disk names, and `receipt_expected` causes all three copies to reject. The pre-execution return additionally spells out `and manifest_provenance`; the preflight and post-execution copies omit that final conjunct, but this is not an acceptance divergence because every path that leaves `manifest_provenance` false also sets `check_provenance` false in the shared exception handler. The duplication remains a maintenance risk, not a present bypass.

4. **INFO — The added test genuinely proves refusal for the static injection, but does not cover the race**
   - File: `scripts/testing/test-factory-gate-readiness.py:257-276`
   - Attack inputs -> outcome: the test installs a valid bundle, adds an executable recognized `hard-*` payload and matching manifest entry, runs the normal `--pre-commit` path, asserts the payload sentinel was never created, and checks the pre-execution diagnostic plus preflight blocker. On the vulnerable ordering, the recognized injected check would execute and create the sentinel before the post-run rejection, so this assertion cannot pass coincidentally merely because the final process status is non-zero. The branch fixture completed with all 20 evidence assertions true; `bash -n` and `py_compile` also passed. Its static setup cannot expose finding 1 because no mutation occurs between validation and invocation.
