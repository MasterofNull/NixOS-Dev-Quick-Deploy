# QPPR-C1C Amendment 3 implementation authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-c1c-am3-20260719`
**Idempotency key:** `qa-provider-probe-reliability:c1c:am3:synchronous-fail-stop:20260719`
**Required implementer:** `claude-subagent-qppr-c1c-am3-implementer`
**Required implementer tier:** balanced (Claude Sonnet lane)
**Tier deviation reason (Rule 17):** the cheapest tier was tried and measurably failed this exact
slice — the Haiku AM2 candidate bound the observable contract to the wrong event and its fail-stop
did not precede restoration/redelivery (`C1C-AM2-CANDIDATE-REJECTION.md`,
`544b84dd5a01c7b57e9ebcf27b7a0849a3eb395b1642b52f9ac7fce039a1a9b6`). Codex remains quota-exhausted
until 2026-07-25; local Qwen is outside its measured envelope for multi-site concurrent-safety edits
(capability envelope: single-edit only).
**Status:** **PREPARED_ONLY — NOT ACTIVATED**
**Single use:** consumed by the first complete exact two-file candidate report after valid activation

## Exact binding and ceiling

| Subject | SHA-256 |
|---|---|
| C1C-AM3 amendment revision 2 | `719115853f0129c13dadad49de3cc736edddec1f64d9d9b9c4b973949cd2f0f6` |
| C1C-AM3 R1 review (`REQUEST_REVISION`, R5 anchor defect; retained history) | `C1C-AM3-AUTHORIZATION-REVIEW.md` at its committed bytes |
| inherited C1C-AM2 amendment (contract SSOT) | `02f4c5317faa80aac7d2872d04eafa8cf5337c9297f1a335fe737160d06e8dfc` |
| consumed C1C-AM2 authorization | `0145aabac0d538831940c86d30bd750e6d4484e9ee06238bd7636c34269d1135` |
| C1C-AM2 authorization review (`PASS`) | `73b16202d6ae9991677ddbe0140bfef9b730b98cefa187401cc9982172067364` |
| AM2 candidate rejection record | `544b84dd5a01c7b57e9ebcf27b7a0849a3eb395b1642b52f9ac7fce039a1a9b6` |
| rejected candidate evidence (context only, frozen) | `f01a460819a5e1b6deef2688ec1fb5c64aa0b38f6a4f2a1080bdcc5800692716`, `61b2301e8574c02729d4ed0c13b8dd8be637254e380b7c93afeafe1d8dc8a5fd` |
| process-owner predecessor | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` |
| lifecycle-test predecessor | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` |
| frozen observer test | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` |

The ceiling is exactly the two MODIFY paths bound in the amendment. Any third path, substitution,
byte drift, identity drift, expired window, or replay after consumption hard-stops without
workaround. The implementer must recompute the two predecessor hashes and the frozen observer hash
before any edit.

## Exact grant

After independent design/authorization `PASS` on the AM3 amendment and this document, and valid
owner activation, only the required implementer may implement amendment requirements R1–R7 in the
two ceiling files: synchronous opt-in publication invocation replacing the barrier-path worker
thread at predecessor lines 1051-1057, sequence-1/2 status records with absolute monotonic deadline,
mechanical fail-stop that neutralizes the `finally` restoration state before raising (lock held, no
controller transfer), blocked-owner never-return safety, corrected pure classifier with
non-downgrade and post-terminal rejection, fail-closed record validation, and the amendment's six
deterministic proofs as tests. The implementer may reuse the descriptor-validation and classifier
logic from the frozen rejected-candidate evidence files where the amendment marks them salvageable.
No existing assertion may be weakened; legacy no-`publication_fd` semantics are byte-frozen in
behavior.

The rejected-candidate evidence files are read-only context. Editing, executing, importing, or
copying them wholesale into the candidate without correction is prohibited.

## Exact required validation commands

```bash
python3 scripts/testing/test-qa-provider-probe-lifecycle.py
python3 scripts/testing/test-qa-provider-probe-observer.py
python3 -m py_compile scripts/testing/harness_qa/core/process_lifecycle.py scripts/testing/test-qa-provider-probe-lifecycle.py
sha256sum scripts/testing/test-qa-provider-probe-observer.py
git diff --check -- scripts/testing/harness_qa/core/process_lifecycle.py scripts/testing/test-qa-provider-probe-lifecycle.py
rg -n 'shell=True|os\.system|https?://|BEGIN (RSA|OPENSSH) PRIVATE KEY|Bearer [A-Za-z0-9]' scripts/testing/harness_qa/core/process_lifecycle.py scripts/testing/test-qa-provider-probe-lifecycle.py
rg -n 'threading\.Thread' scripts/testing/harness_qa/core/process_lifecycle.py
```

The observer hash must match the frozen value; the secret-scan `rg` must return no matches; the
`threading.Thread` scan must show no thread creation on the new barrier path (the legacy line is
expected and must remain). Nothing outside this list may be executed.

## Governance-event obligations (canonical writers only)

Before any candidate edit the implementer must: read `.agent/collaboration/RESUME.json`; run exactly
once `scripts/ai/aq-event resume --agent claude-subagent-qppr-c1c-am3-implementer --objective
"Implement C1C-AM3 synchronous publication fail-stop" --phase "C1C-AM3 implementation" --hint
"Two-file ceiling; stop on any scope or connectivity expansion" --todo "Edit only the two ceiling
paths"`; and run exactly once `python3 scripts/ai/lib/pending-update add c1c-am3-20260719
claude-subagent-qppr-c1c-am3-implementer scripts/testing/harness_qa/core/process_lifecycle.py
"Implement C1C-AM3 synchronous publication fail-stop"`. Immediately after the candidate write, emit
exactly one pulse (`--action write`, both paths in `--scope`, truthful outcome). On finish run the
validate pulse plus `pending-update done c1c-am3-20260719`; on a mandatory stop substitute the stop
pulse plus `failed` (before edit) or `partial-success` (after edit). Direct edits to any governance
evidence path are prohibited; only these literal canonical writers may touch them.

## Activation, replay, and exclusions

Owner activation must state this authorization's exact SHA-256, repeat the required implementer
identity `claude-subagent-qppr-c1c-am3-implementer`, restate the SRE ratification (no finite
redelivery claim for late/never-returning publication; fail-stop before restoration/redelivery), and
provide activation and expiry timestamps no more than 24 hours apart. Activation before independent
review, after expiry, for another identity, or without the ratification restatement is invalid. The
first complete exact two-file report atomically consumes the idempotency key; later reports or
activation replay cannot authorize edits and require fresh reviewed bytes.

The implementer cannot delegate, stage, commit, deploy, delete, or self-accept. Control-plane
session/intent/resume/pulse/handoff evidence contains no product code and is not staged. No
provider/live/network/heartbeat/evidence/Phase-0/A1/A2/API/browser/Nix/service/deploy/traffic/
rollback action is authorized. Acceptance requires a different independent reviewer under a
separately prepared, reviewed, and owner-activated grant; Tier-0, staging, and commit remain
orchestrator-only after that independent `PASS`.

A1-AM3 four-file recovery remains NON-ACTIVATABLE pending C1C-AM3 acceptance/commit and final exact
rebind. A2 remains blocked.

`RECORD: PREPARED_ONLY / SINGLE USE. Implementation and all live actions remain unauthorized.`
