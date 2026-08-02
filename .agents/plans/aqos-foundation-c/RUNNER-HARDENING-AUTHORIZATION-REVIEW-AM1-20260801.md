---
review_kind: "independent exact authorization review"
reviewer_role: "Codex independent reviewer"
subject: "RUNNER-DEPLOYMENT-HARDENING-IMPLEMENTATION-AUTHORIZATION-20260801.md"
subject_sha256: "e94e36bf7a2f50dbab286bc35a07a80b5f1a6591f5cb93b94dd3837d1fd06059"
reviewed_head: "17f899bf838973c755ab7a3e6095ec04a2e74220"
verdict: "PASS"
implementation_authorization: "PREPARED_ONLY — owner activation required"
activation_authorization: "NONE"
---

# Runner-Hardening Authorization AM1 — Independent Exact Review

## Exact subject and chain

Reviewed authorization SHA-256:
`e94e36bf7a2f50dbab286bc35a07a80b5f1a6591f5cb93b94dd3837d1fd06059`.
Its declared and observed HEAD are both
`17f899bf838973c755ab7a3e6095ec04a2e74220`.

All three explicitly named chain files resolve to the authorization's exact
hashes:

| Chain subject | Observed SHA-256 | Assessment |
|---|---|---|
| `RUNNER-DEPLOYMENT-HARDENING.md` | `48cae30d1c93ff9e76fdff0e3866f885b54e544de95c978c8286a1c8065f0c63` | exact design match |
| `RUNNER-DEPLOYMENT-HARDENING-FREEZE.md` | `430093d2c4af905793c9cdf4539b9b5a50c93b16976ede2d08795f34921a25df` | exact freeze-candidate match |
| `FOUNDATION-C-REV3-CODEX-ACCEPTANCE-20260801.md` | `c802f5f50c140129925ae5067b444d2fb5a6b1db24b8373e3832dab5226b89ca` | exact independent binding review; runner design `PASS_DESIGN`, freeze candidate `PASS_FREEZE_CANDIDATE` |

The prior authorization review's sole blocker is closed: the corrected grant
now supplies the immutable revision-3 review path and exact hash, whose persisted
verdict covers the same design and freeze-candidate bytes.

## Four-file ceiling and anchors

Every editable path remains byte-identical to the freeze:

| Operation | Path | Observed SHA-256 |
|---|---|---|
| EDIT | `ai-stack/switchboard/execution_cell_runner.py` | `34837d4dc6718afccc2f663e590024f7d18723712a0a42c7cefd1969273e60fb` |
| EDIT | `scripts/testing/test-execution-cell-runner.py` | `4f8094bcc11cb29d8ce9ec8348bb4356d51df862bab4ee1124fcd87b13ea93ef` |
| EDIT | `nix/modules/services/execution-cell-runner.nix` | `d2f12a1cdcf4c33aae17239fbdbf92877a5b8940cd52e1946f60eab2cb6e1d12` |
| EDIT | `config/env-contract.yaml` | `62450e1f6e84f9c473b2bf838e1121d6db3e40227480c1845d5b24c54686be4f` |
| NO EDIT | `nix/modules/services/switchboard.nix` | `10e3bbfd3bcaef1beef0782f106614968f7ba0cd193c68a8bf6a17ca68d1343a` |

The authorization permits no fifth path, new file, substitution, mode change,
staging, commit, deployment, restart, provider/network action, or traffic. It
retains default OFF, independent candidate acceptance, single-use consumption,
drift/overlap/test fail-stops, and a separately authorized later live exercise.

## Decision

The corrected prepared authorization is exact and eligible for a fresh owner
activation that names this authorization hash, one implementer, and a bounded
UTC window. This review does not itself activate the authorization or permit any
write, stage, commit, runtime, deployment, provider, network, or traffic action.

**VERDICT: PASS — the exact four-file PREPARED_ONLY runner-hardening authorization is eligible for fresh owner activation; no activation occurs by this review.**
