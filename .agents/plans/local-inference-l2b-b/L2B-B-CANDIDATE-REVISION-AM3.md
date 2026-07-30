# Foundation B1 L2B-B Candidate Revision Amendment 3

**Prepared:** 2026-07-22T16:50:00Z

**Status:** `PREPARED_ONLY — REFREEZE DESIGN; NO IMPLEMENTATION AUTHORITY`

**Required activation HEAD:** `60e47d9515a234e3179cf72e95f576e88dc4e047`

**Governing REQUEST_REVISION:** `L2B-B-CODEX-CANDIDATE-ACCEPTANCE.md`, SHA-256
`0b56d7d59ab50ce3496ee2cb0a7c2bc8e4762db7604fe8e4fc929feeffe87b5d`

## 1. Refreeze cause and prior-grant disposition

The owner activated reviewed AM2 authorization SHA-256
`d5e78b793df0767399a8559d77360c84cecc8225f67880518adf5d22a961d593` for
`codex-subagent-l2b-b-am2-implementer`. Event `067887d75ec140c0849f19d3c066d865` records the
activation. A later owner pulse, event `6b738ae183f341dc8d6ae386ff6981cb`, also activated the
overlapping two-path authorization SHA-256
`1b043066ffe785f1be6e1934fcd6d7d7b50d9e24b17e416d7946ea74f16a8391` for
`claude-subagent-l2b-b-implementer`.

The AM2 overlap oracle stopped on that conflict before any successful write. Event
`8f3d4e81ead0446993941a857852e094` records the zero-write fail-stop. AM2 is consumed and
non-replayable by its own single-use rule. The narrower conflicting grant is unsafe for further use
because it overlaps two AM3 writable paths, omits two required corrections, permits staging, and
names another implementer.

On owner activation of AM3, both earlier grants are explicitly and permanently superseded and
void for any future claim, dispatch, write, resume, staging, or acceptance:

1. consumed AM2 authorization SHA-256
   `d5e78b793df0767399a8559d77360c84cecc8225f67880518adf5d22a961d593`; and
2. conflicting narrow authorization SHA-256
   `1b043066ffe785f1be6e1934fcd6d7d7b50d9e24b17e416d7946ea74f16a8391`.

This PREPARED_ONLY record cannot itself activate AM3 or retroactively alter an owner grant. The
owner activation statement must repeat the two exact hashes and the supersession/void disposition.
Any external L2B process, live delegation-registry task, or writable intent at activation time is a
hard stop. A stale projected intent row is not implementation authority and must be cancelled or
truthfully terminal before dispatch.

## 2. Verified zero-write refreeze

At preparation time, no external L2B process appeared in the process table and no live L2B entry
appeared in `.agents/delegation/registry.jsonl`. The AM2 intent is terminal `cancelled`. A conflicting
projected intent named `l2b-b-rev-20260722` still reports `running` in
`.agent/collaboration/PENDING.json` despite having no process or delegation-registry task. AM3 must
not activate or dispatch until the owner has made that stale/foreign intent terminal.

The exact six implementation bytes remain unchanged from AM2:

| State | Operation | Path | Frozen SHA-256 |
|---|---|---|---|
| WRITABLE | MODIFY | `scripts/ai/lib/local_inference_transport.py` | `6c28a4110966b326bfba30abf9c399a073a9f6079cd7f2843bf8345ecbce60be` |
| WRITABLE | MODIFY | `scripts/testing/test-local-inference-l2b.py` | `2af6ae699c322bc5701ba147b5ea8c2b744185a82ab6ee686508f8746099c495` |
| FROZEN | NO EDIT | `assets/dashboard.js` | `1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49` |
| FROZEN | NO EDIT | `config/schemas/local-inference-payload-v1.json` | `7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65` |
| WRITABLE | MODIFY | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662` |
| WRITABLE | MODIFY | `dashboard/backend/api/routes/aistack.py` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` |

The exact four AM2 writable predecessors therefore remain byte-identical. The dashboard consumer
and payload schema remain frozen. No candidate path is staged.

## 3. Exact correction ceiling and semantics

AM3 preserves the exact AM2 four-path write ceiling and required behavior without substitution:

- recursively NFC-normalize string keys and values without mutating caller input; reject
  non-string keys and fail closed with `nfc_key_collision` before any normalized-key overwrite;
- scan normalized keys for forbidden credential fields and retain the bounded
  `REJECTED_SCHEMA_INVALID` envelope without sensitive detail;
- canonicalize known model names and account each known resident model as
  `max(valid_caller_value, trusted_known_model_floor)`, so `qwen3-35b` plus either known 8B model
  exceeds 27 GB despite caller underreporting;
- make the golden fixture strict RFC 8259 JSON while constructing NaN and both infinities only in
  programmatic tests;
- sanitize and forward only `pass`, `fail`, or `unavailable` for
  `payload_normalization_status` through the existing backend projection and cache; and
- preserve exactly 14 deterministic top-level L2B checks while adding assertions for the four
  correction defects.

`assets/dashboard.js` and `config/schemas/local-inference-payload-v1.json` are frozen. Any fifth
write path, substitution, mode change, move, deletion, symlink, foreign overlap, frozen-byte drift,
staging, or HEAD drift hard-stops.

## 4. Preserved boundaries and acceptance

This is a pure offline correction slice. It grants no live inference, model load, hardware probe,
provider call, network, DNS, socket, credential, secret, database, service, browser, Nix,
deployment, restart, traffic, route, poller, endpoint, store, writer, queue, environment-variable,
port, URL, dependency, production subprocess, staging, commit, deletion, delegation, or
self-acceptance authority.

After implementation, a fresh reviewer from a different agent/session must bind all six final
candidate hashes, inspect the four-path diff and two frozen paths, rerun every authorized offline
validation, verify the four REQUEST_REVISION defects are closed, and issue an explicit verdict.
Only an independent PASS may unlock separately authorized Tier-0, staging, or commit.

## 5. Owner decisions required

Before activation, the owner must explicitly:

1. bind AM3 to exact HEAD `60e47d9515a234e3179cf72e95f576e88dc4e047` and all hashes above;
2. supersede and void both exact prior authorization hashes in Section 1 for all future use;
3. confirm no external L2B process or live delegation-registry task exists and make the stale
   `l2b-b-rev-20260722` projected intent terminal;
4. assign only `codex-subagent-l2b-b-am3-implementer` under a fresh single-use window of no more
   than 24 hours; and
5. require fresh independent exact-subject authorization review before activation and fresh
   independent candidate acceptance after correction.

`RECORD: PREPARED_ONLY AM3 zero-write refreeze; no implementation, provider, live, network,
staging, commit, or acceptance authority is granted.`
