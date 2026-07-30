# Foundation B1 L2B-B Candidate Revision Amendment 4

**Prepared:** 2026-07-22T17:05:00Z

**Status:** `PREPARED_ONLY — POST-NARROW-WRITE REFREEZE; NO IMPLEMENTATION AUTHORITY`

**Required activation HEAD:** `99364942d42a31b33248abc8db7f840ee590c9b5`

**Governing acceptance:** `L2B-B-NARROW-REVISION-CODEX-ACCEPTANCE.md`, SHA-256
`97e68a7c7ee96750deb669f2168e7e67bd514881a3f78e56544b3e567b8bfb6a`

## 1. Lineage and supersession

The completed narrow Fable write changed the transport and focused-test predecessors after AM3 was
prepared. Independent acceptance confirms two partial corrections: recursive NFC key normalization
and opaque rejection of non-string mapping keys both PASS. It also issues REQUEST_REVISION for the
four remaining defects. AM3 is therefore invalidated without use.

On valid owner activation of AM4, these exact earlier grants are superseded and void for every
future claim, dispatch, write, resume, staging, and acceptance:

- consumed AM2 `d5e78b793df0767399a8559d77360c84cecc8225f67880518adf5d22a961d593`;
- conflicting and completed narrow grant
  `1b043066ffe785f1be6e1934fcd6d7d7b50d9e24b17e416d7946ea74f16a8391`; and
- invalidated PREPARED_ONLY AM3
  `951c9f9dfde931f7349ae7c817874ee6889b76b26ac396f87e5752a3b72ced6f`.

This PREPARED_ONLY record is not owner activation. The owner statement must repeat all three exact
hashes and their supersession/void disposition.

## 2. Exact current subject and index disposition

| State | Operation | Path | Current SHA-256 |
|---|---|---|---|
| WRITABLE | MODIFY | `scripts/ai/lib/local_inference_transport.py` | `39ee836f2eb595e877dd29bba15f7ac955ab2a6aa24639c87aca6ae1a27b2866` |
| WRITABLE | MODIFY | `scripts/testing/test-local-inference-l2b.py` | `33ab4d84e642873ddc4a5fa2b8488c157f221550340366a8bdc04cfa0250319d` |
| FROZEN | NO EDIT | `assets/dashboard.js` | `1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49` |
| FROZEN | NO EDIT | `config/schemas/local-inference-payload-v1.json` | `7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65` |
| WRITABLE | MODIFY | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662` |
| WRITABLE | MODIFY | `dashboard/backend/api/routes/aistack.py` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` |

At final preparation, all six listed L2B paths are absent from the shared index and their worktree
bytes match the hashes above. That exact candidate-path absence must hold at authorization review,
activation, dispatch, and before first write. No reset, revert, checkout, deletion, or candidate-byte
rewrite is permitted as an index-disposition mechanism.

Staged L2B governance records and disjoint staged VF-7 paths may remain only if an exact staged-name
inventory proves none is one of the six L2B candidate paths and no shared path is introduced. Every
foreign staged path is preserved, never modified or attributed to AM4.

## 3. Accepted partial behavior and remaining corrections

AM4 must preserve the independently accepted NFC key normalization and opaque non-string-key
rejection. It authorizes only these remaining corrections across the exact four writable paths:

1. Detect NFC-equivalent object-key collisions before overwrite at every nesting depth and fail
   closed with bounded reason code `nfc_key_collision`; add a deterministic collision adversary.
2. Canonicalize known model names and charge effective residency as
   `max(valid_caller_value, _KNOWN_MODEL_VRAM_GB[canonical_name])`; underreported `qwen3-35b` plus
   either known 8B model must fail with `vram_budget_exceeded`.
3. Make the golden fixture strict RFC 8259 JSON. Construct NaN and both infinities only inside the
   Python oracle and retain their normalization coverage.
4. Carry closed `payload_normalization_status` values (`pass`, `fail`, `unavailable`) through the
   existing backend default, extraction, validation, sanitized result, and cache so the frozen
   dashboard consumer receives the measurement; add an offline projection assertion.

No fifth path, substitution, mode change, move, deletion, symlink, frozen-byte drift, live action,
network action, staging, commit, delegation, or self-acceptance is allowed.

## 4. Acceptance and owner decisions

A fresh independent reviewer from a different agent/session must bind all six final hashes, inspect
the four-path diff and frozen paths, rerun the exact offline validation, confirm the accepted partial
fixes remain intact and all four remaining defects are closed, then issue an explicit verdict. Only
an independent PASS may unlock separately authorized Tier-0, staging, or commit.

Before activation, the owner must bind exact HEAD and every hash above, ratify the three-hash
supersession, confirm the required clean L2B index disposition and VF-7 disjointness, assign only
`codex-subagent-l2b-b-am4-implementer`, and provide a positive single-use window no longer than 24
hours after fresh independent exact-subject authorization review.

`RECORD: PREPARED_ONLY AM4 post-narrow-write refreeze; no implementation, live, network, staging,
commit, or acceptance authority is granted.`
