# QPPR-A1 Amendment 3 — roadmap verifier recovery

**Status:** PREPARED_ONLY / CONDITIONAL / NON-ACTIVATABLE  
**Prepared:** 2026-07-19  
**Required implementer after final C1C rebind:** `codex-subagent-qppr-a1-am3-implementer`

## 1. Evidence and decision

Mandatory Tier-0 against the frozen A1 candidate reports **22 PASS / 1 FAIL**. The failure is a
stale static assertion in `scripts/testing/verify-flake-first-roadmap-completion.sh`: it requires the
retired inline `commands=(cn codex qwen gemini claude pi)` / `--help` loop even though A1 correctly
replaces that loop with the canonical `qa-provider-probe.py --machine` compatibility entrypoint.

Removing the check would weaken coverage. A1-AM3 therefore expands its correction inventory by
exactly one existing verifier path. The verifier must recognize the canonical compatibility route,
reject reintroduction of the legacy inline loop, and independently retain direct Phase-0 check
`0.6.1` coverage. This is an A1 atomic compatibility correction, not a separate runtime authority.

## 2. Bound governance subjects

| Subject | SHA-256 |
|---|---|
| A1-AM3 prerequisite rebind | `41ca28a2d0d4960ec6849d93cc013912ecaa545dfe0b6b645f76a14cc7c5f0b2` |
| prior A1-AM3 non-activatable authorization | `63f28c168b0b2a6547d72b00df9122cc8ef5c6e02443a78b5b5d271b5920f621` |
| C1C design | `2a04262e0b278eeaeff271475f003e13883615aff906a132a9ee2e8c2f470974` |
| C1C authorization | `c9460d0b7468defb0807ca4d51ff2ae615e6d0764b9b836fe0c58bdade237c23` |
| A1-AM2 decision-basis review | `6827864ccdcae765b47f0c4daf32416199270a8ef825f1e3efb0e3395ede2d14` |
| A1-AM1 revision record | `d9d44bc37b3a3415d2a2805b115a01bfe808276cdf8ceab8b33f84a935bdaff9` |

## 3. Exact four-file future correction ceiling

| # | Operation | Path | Exact current predecessor |
|---:|---|---|---|
| 1 | MODIFY | `scripts/testing/qa-provider-probe.py` | `755b730d6d7446d76f21933d2e273ca4ed7f8f65a808672e532caab007b5d0ab` |
| 2 | MODIFY | `scripts/testing/harness_qa/core/result.py` | `4c72e8aa658a67a5168fb9817a21a247c596ac29aa55b7fd776d5f18f0320776` |
| 3 | MODIFY | `scripts/testing/test-qa-provider-probe-adoption.py` | `f7e286dfa23ef3b22eea713e1ec4b9b350c3e5e4b29ba4a0098d9d4f0eb7123c` |
| 4 | MODIFY | `scripts/testing/verify-flake-first-roadmap-completion.sh` | `c8602060565decdeef229042d2e15bf4b875f78f5a71eb4422cfcc3dd074a9d9` |

The other five existing A1 candidate paths remain frozen:

| Path | Required unchanged SHA-256 |
|---|---|
| `scripts/testing/smoke-flagship-cli-surfaces.sh` | `98a1c8f2a9b67895f7e42d9ae176d65b706128d92b93033c1094c2b6d23bcdfb` |
| `scripts/testing/harness_qa/phases/phase0.py` | `b01edf1308c6433c6fae1316a75b7d4251b77df9afa5d8e4fb41b99c5ca63999` |
| `scripts/testing/harness_qa/core/context.py` | `ef2993079c1ffed301e9b9cc41014944706f37ca4e3879fb7605223af314e6ea` |
| `scripts/testing/harness_qa/main.py` | `2137974e61f991cf363ae0dbca1511f3d801728d01f43b5af974050e4df9f4c0` |
| `scripts/testing/harness_qa/reporters/json_out.py` | `7d62ff15da20e969384a858c67d8e0dea1b34423e941f205f780d66d65a11f29` |

Any fifth AM3 correction path, substitution, or hash drift is a hard stop.

## 4. Exact verifier semantics

The roadmap verifier must replace only the stale flagship CLI assertion with deterministic static
coverage that independently requires all of the following:

1. `smoke-flagship-cli-surfaces.sh` resolves `qa-provider-probe.py` relative to its own script
   directory and performs exact argv execution through `exec python3 "${runner}" --machine`;
2. the compatibility shell contains no inline `commands=(...)` provider loop, GNU `timeout`,
   `bash -c`, `eval`, or second lifecycle owner;
3. `phase0.py` retains check ID `0.6.1` and a direct `module.run_provider_probe(` call;
4. the canonical runner remains the fixed four-provider policy owner; the static verifier does not
   execute it and does not infer provider health; and
5. the verifier labels distinguish compatibility-entrypoint coverage from Phase-0 registration/
   adoption coverage.

The existing A1 adoption test must assert the verifier contains both positive canonical-entrypoint
and Phase-0 patterns plus the negative legacy-loop assertion. A deterministic fixture copy of the
three static subjects must prove the verifier passes the canonical form and fails when the exec is
removed, Phase-0 direct call is removed, or the legacy loop is reintroduced. No real provider,
network, heartbeat/evidence, or Phase-0 live execution may occur.

This changes no roadmap claim, provider list, accepted policy, runtime behavior, test count
authority, or Tier-0 fail-open/fail-closed semantics. It corrects only architecture-aware static
recognition while increasing the evidence from one ambiguous alternation to explicit positive and
negative assertions.

## 5. Prerequisite, review, and stops

This recovery supersedes the three-file ceiling in the prior A1-AM3 conditional authorization; it
does not make A1 activatable. C1C must still be independently activated, implemented, accepted, and
committed. A final exact A1-AM3 rebind must then bind the accepted C1C commit/acceptance/final hashes,
this recovery, all nine A1/verifier subject hashes, and required implementer
`codex-subagent-qppr-a1-am3-implementer` before owner activation.

Stop on verifier coverage removal, an alternation that permits either legacy or canonical form,
runtime execution from the verifier, candidate path expansion, C1C absence/drift, different
implementer, real provider/network/live Phase-0/heartbeat/evidence/API/browser action, new route/
store/env/port/dependency, Nix/service/deploy/traffic/rollback, staging, commit, deletion, delegation,
or self-acceptance. A2 remains blocked until A1-AM3 acceptance and commit followed by its separate
adjacency rebind.

`RECORD: PREPARED_ONLY / NON-ACTIVATABLE. C1C and final byte rebind remain prerequisites; A1-AM3,
A2, providers, network, Phase 0 live execution, deployment, traffic, and rollback are unauthorized.`
