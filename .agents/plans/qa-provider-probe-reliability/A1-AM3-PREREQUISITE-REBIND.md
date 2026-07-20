# QPPR-A1 Amendment 3 prerequisite rebind

**Status:** PREPARED_ONLY / CONDITIONAL / NON-ACTIVATABLE  
**Prepared:** 2026-07-19  
**Required implementer after final rebind:** `codex-subagent-qppr-a1-am3-implementer`

## 1. Decision

Independent review SHA-256
`6827864ccdcae765b47f0c4daf32416199270a8ef825f1e3efb0e3395ede2d14` correctly found that A1
cannot guarantee completion/cancellation before redelivery while the accepted lifecycle owner may
leave a daemon publication worker running. C1C is therefore a mandatory separately implemented,
accepted, and committed interface prerequisite. A1-AM2 is superseded for activation purposes.

A1-AM3 preserves the five A1 corrections and the exact three-file product subset from AM2, but may
not be activated until a final byte-level rebind names the exact accepted C1C commit, acceptance
record, process-owner hash, and lifecycle-test hash. C1C authorization, implementation, or review
alone is insufficient.

## 2. Exact preparation subjects

| Subject | SHA-256 |
|---|---|
| C1C design | `2a04262e0b278eeaeff271475f003e13883615aff906a132a9ee2e8c2f470974` |
| C1C PREPARED_ONLY authorization | `c9460d0b7468defb0807ca4d51ff2ae615e6d0764b9b836fe0c58bdade237c23` |
| A1-AM2 design | `6992c98f3c2e00d91cf5c5893b6116e23b484f16a3121a9f32899e3f4ab77f6d` |
| A1-AM2 authorization | `246060d853c730191cc9515dca227d31ba5ebd03f8bb921f3cbdac5ac37e5bdd` |
| A1-AM1 revision record | `d9d44bc37b3a3415d2a2805b115a01bfe808276cdf8ceab8b33f84a935bdaff9` |
| adoption design | `44b600bfb3a22e05205c0babb9a72e1ed02c6f84afd71127a5a71afb99c79f18` |
| accepted schema | `1acaa61d4b3fe2737a513112c49578bf5b596c04f4916f4e4647e8e7516b7ac4` |
| accepted policy | `2cbe6e350f35cd9e0831186df31f9631a10c1e838fb0246fc1f56828abb4a6af` |

The instructed decision-basis review SHA above is authoritative for this rebind. The currently
observed staged review bytes hashed differently during concurrent orchestration; they are not
silently substituted for the instructed subject and must be reconciled by the orchestrator before
final rebind review.

## 3. Frozen current A1 candidate and AM3 subset

| Path | Current SHA-256 | AM3 disposition |
|---|---|---|
| `scripts/testing/qa-provider-probe.py` | `755b730d6d7446d76f21933d2e273ca4ed7f8f65a808672e532caab007b5d0ab` | **MODIFY** |
| `scripts/testing/smoke-flagship-cli-surfaces.sh` | `98a1c8f2a9b67895f7e42d9ae176d65b706128d92b93033c1094c2b6d23bcdfb` | freeze |
| `scripts/testing/harness_qa/phases/phase0.py` | `b01edf1308c6433c6fae1316a75b7d4251b77df9afa5d8e4fb41b99c5ca63999` | freeze |
| `scripts/testing/harness_qa/core/result.py` | `4c72e8aa658a67a5168fb9817a21a247c596ac29aa55b7fd776d5f18f0320776` | **MODIFY** |
| `scripts/testing/harness_qa/core/context.py` | `ef2993079c1ffed301e9b9cc41014944706f37ca4e3879fb7605223af314e6ea` | freeze |
| `scripts/testing/harness_qa/main.py` | `2137974e61f991cf363ae0dbca1511f3d801728d01f43b5af974050e4df9f4c0` | freeze |
| `scripts/testing/harness_qa/reporters/json_out.py` | `7d62ff15da20e969384a858c67d8e0dea1b34423e941f205f780d66d65a11f29` | freeze |
| `scripts/testing/test-qa-provider-probe-adoption.py` | `f7e286dfa23ef3b22eea713e1ec4b9b350c3e5e4b29ba4a0098d9d4f0eb7123c` | **MODIFY** |

AM3 implements the AM2 sections 4.2-4.5 unchanged. For section 4.1 it must exclusively use the
accepted C1C `publication_barrier`, never the legacy daemon publication callback. Its acknowledgement
must be `completed` only after terminal projection is committed and all A1 reader/ticker activity is
joined, or `cancelled` only after incomplete work is synchronously disabled and joined. The callback
must respect the supplied absolute deadline and leave no post-return continuation. All deterministic
AM2 signal/order/no-late-write tests remain mandatory.

## 4. Final rebind gate

After C1C independent acceptance and commit, a final rebind must record:

- exact C1C commit and no unrelated intervening mutation of either prerequisite path;
- exact independent C1C acceptance record and final `PASS`;
- exact final `process_lifecycle.py` and lifecycle-test hashes;
- unchanged hashes for all eight current A1 candidate paths;
- exact final A1-AM3 authorization bytes and required identity
  `codex-subagent-qppr-a1-am3-implementer`; and
- independent flagship `PASS` over that complete binding.

Until all six exist, owner wording cannot activate A1-AM3. Any drift requires a new reviewed rebind.

## 5. Stops and A2 block

All A1-AM2 stops remain, plus: stop on missing/unaccepted/uncommitted C1C, use of legacy
`publication`, callback continuation after acknowledgement, deadline extension, prerequisite path
edit under A1, different implementer identity, or incomplete final binding. No provider, network,
heartbeat/evidence activation, live Phase 0, API/browser, deployment, traffic, rollback, or A2 action
is authorized. A2 remains blocked until independently accepted and committed A1-AM3, then requires
its own exact adjacency rebind and owner activation.

`RECORD: PREPARED_ONLY / NON-ACTIVATABLE. C1C and final rebind must complete first; A1-AM3, A2, and
all live actions remain unauthorized.`
