# Foundation B1 L2B-B Candidate Revision Amendment 2

**Prepared:** 2026-07-22T11:48:25Z

**Status:** `PREPARED_ONLY — CORRECTION DESIGN; NO IMPLEMENTATION AUTHORITY`

**Governing acceptance:** `L2B-B-CODEX-CANDIDATE-ACCEPTANCE.md`, SHA-256
`0b56d7d59ab50ce3496ee2cb0a7c2bc8e4762db7604fe8e4fc929feeffe87b5d`

**Acceptance subject HEAD:** `90a55e06d653b4c7a7366f5880b3c30bd9ba0898`

**Actual preparation HEAD:** `60e47d9515a234e3179cf72e95f576e88dc4e047`

## 1. HEAD and candidate binding

The owner requested AM2 against HEAD `90a55e06`. Before this record was written, HEAD advanced
through `d1c8e55b` to `60e47d95`. The exact range `90a55e06..60e47d95` contains only B3-C1 code and
governance records; it changes none of the five L2B-B candidate paths or the new AM2 backend path.
AM2 therefore records `90a55e06` as the acceptance lineage anchor and binds activation to the
truthful current HEAD `60e47d9515a234e3179cf72e95f576e88dc4e047`. Any later HEAD change requires
another freeze and exact-subject review, even if apparently disjoint.

The REQUEST_REVISION subject is the following exact unstaged five-file candidate:

| Candidate operation | Path | Frozen SHA-256 |
|---|---|---|
| MODIFY | `scripts/ai/lib/local_inference_transport.py` | `6c28a4110966b326bfba30abf9c399a073a9f6079cd7f2843bf8345ecbce60be` |
| MODIFY | `scripts/testing/test-local-inference-l2b.py` | `2af6ae699c322bc5701ba147b5ea8c2b744185a82ab6ee686508f8746099c495` |
| MODIFY | `assets/dashboard.js` | `1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49` |
| NEW | `config/schemas/local-inference-payload-v1.json` | `7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65` |
| NEW | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662` |

The new backend predecessor is:

| Path | Frozen SHA-256 |
|---|---|
| `dashboard/backend/api/routes/aistack.py` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` |

The candidate, backend predecessor, acceptance record, and acceptance authorization are all inputs.
They are not accepted merely by being frozen here.

## 2. Smallest correction inventory

AM2 authorizes corrections to exactly four paths:

| Operation | Path | Correction |
|---|---|---|
| MODIFY | `scripts/ai/lib/local_inference_transport.py` | NFC object-key normalization/collision refusal and trusted known-model VRAM floors |
| MODIFY | `scripts/testing/test-local-inference-l2b.py` | Deterministic adversarial and backend/dashboard projection assertions |
| MODIFY | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | Strict RFC 8259 fixture representation with no bare non-finite tokens |
| MODIFY | `dashboard/backend/api/routes/aistack.py` | Sanitize and forward `payload_normalization_status` |

`assets/dashboard.js` and `config/schemas/local-inference-payload-v1.json` remain frozen at the hashes
above. Their existing candidate bytes are part of the final acceptance subject but are not writable
under AM2. No fifth AM2 write path or substitution is allowed.

## 3. Required correction semantics

### 3.1 Canonical NFC keys and values

- Recursively NFC-normalize every string value and every JSON object key without mutating caller
  input.
- Construct each normalized mapping deliberately; never use a comprehension that can silently
  overwrite two source keys.
- If two distinct source keys normalize to the same NFC key at any nesting depth, fail closed with
  reason code `nfc_key_collision`. `canonical_transformer()` must return its existing bounded
  `REJECTED_SCHEMA_INVALID` envelope with no source key, value, exception, path, or traceback leak.
- Reject non-string mapping keys through the existing closed invalid-payload path rather than
  relying on sort/type exceptions.
- Run forbidden-credential-key scanning on the normalized mapping so normalization cannot bypass
  the existing credential prohibition.

### 3.2 Non-bypassable known-model VRAM accounting

- Canonicalize known model identifiers before accounting.
- For each name in `_KNOWN_MODEL_VRAM_GB`, compute effective residency as
  `max(valid_caller_value, trusted_known_model_floor)`; caller underreporting must never lower the
  trusted floor.
- Reject concurrent `qwen3-35b` with either known 8B resident (`qwen3-8b` or `llama-8b`) under the
  ordinary `vram_budget_exceeded` fail-closed reason. The trusted floors must independently push the
  combination above the 27 GB ceiling even when both caller values are `0`, `1`, or otherwise low.
- Preserve strict shape validation, single-model acceptance, custom-budget behavior, and pure
  calculation. Do not query hardware, inspect a process, allocate VRAM, load a model, or create a
  routing/concurrency authority.

### 3.3 Strict fixture and programmatic non-finite coverage

- `l2b_b_golden_payloads.json` must parse under a strict RFC 8259 loader that rejects `NaN`,
  `Infinity`, and `-Infinity`; those tokens must not occur as unquoted JSON values.
- Construct `float("nan")`, `float("inf")`, and `float("-inf")` only inside the Python test and
  assert the normalization behavior there. Do not weaken or remove non-finite input coverage.
- Preserve deterministic fixture ordering and stable IDs for all unaffected vectors.

### 3.4 Live dashboard contract through the existing backend projection

- Add `payload_normalization_status` to `_local_inference_l2b_health_sync()`'s default, raw-field
  extraction, closed-state validation, healthy-state invariant, sanitized result, and cached result.
- Permit only `pass`, `fail`, or `unavailable`; malformed/missing producer values must fail closed
  through the existing degraded/unavailable contract.
- Adjust the focused oracle so producer `pass` survives sanitization and is observable by the
  already-frozen dashboard consumer. Do not add a route, poller, endpoint, request, listener, cache,
  client authority, or live browser/network check.

## 4. Preserved boundaries

This is a pure, offline correction slice. It grants no live inference, model load, provider call,
network, DNS, socket, credential, secret, database, service, Nix, deploy, restart, traffic, browser,
filesystem-topology, route, writer, store, queue, environment-variable, port, URL, package-dependency,
staging, commit, deletion, delegation, or self-acceptance authority. Existing B3 and other foreign
worktree bytes must not be modified, staged, reverted, included, or attributed to AM2.

## 5. Owner decisions required

Before activation, the owner must explicitly ratify:

1. the actual prepared HEAD `60e47d95` and the disclosed disjoint advance from requested
   `90a55e06`;
2. retirement of the prior implementation grant for further edits after its completed candidate
   received REQUEST_REVISION;
3. the exact four-file AM2 correction ceiling and two frozen candidate paths;
4. `codex-subagent-l2b-b-am2-implementer` as the cheapest eligible current lane: local modes cannot
   reliably complete a four-file shell-validated code correction, Gemini auto-edit cannot run the
   required tests, and no authenticated headless Gemini-yolo lane is established; Codex supplies
   bounded patch and shell capability, with Claude as the higher-cost fallback; and
5. fresh independent exact-subject authorization review before activation and fresh independent
   candidate acceptance by a different agent/session after correction.

`RECORD: PREPARED_ONLY AM2 correction design; no implementation, provider, live, network, staging,
commit, or acceptance authority is granted.`
