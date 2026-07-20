# QPPR-A1 Amendment 3.1 reproducible prerequisite rebind

**Status:** PREPARED_ONLY / NON-ACTIVATABLE  
**Required future implementer:** `codex-subagent-qppr-a1-am3-implementer`

## Reproducible named subjects

| Current named workspace subject | SHA-256 |
|---|---|
| `A1-AM2-DESIGN-AMENDMENT.md` | `2d6d7e490b70d307ff6c3d5daf1d89c0ab85bba8cc331e8f8491be1aacb309f9` |
| `A1-AM2-AUTHORIZATION-REVIEW.md` | `214a3a99fbadf9895311c7142e63fc4787e1b7fb3fe10c115fbfaac305cc89c6` |
| `C1C-A1-AM3-AUTHORIZATION-REVIEW.md` | `15a1b110e2483d6be46aa8f46faf56fd27288ce4fbfc611fbea944dcb0c81e38` |
| C1C-AM1 SRE amendment | `bced486ad8af5ced589b71a853ccdffe2927dd5288b650e0c2b48c7eaa924f3c` |
| C1C-AM1 authorization | `d9b97c0ca7aee73e437b3bba280eec72c5adce2b567c3066af86109d1a81c702` |
| roadmap verifier recovery | `0d16fa8e96413e6368aa0dfb4331f5dbfa79e652187eb9d4a98405c33ab0c1a4` |
| roadmap recovery authorization | `6590176eb70ec09296f87bad1a2d4c58220086aa21fe09cc4058d77c35d359ac` |

Earlier hashes `6992c98f...` and `6827864c...` remain historical decision-lineage identifiers from
prior reports, not assertions about current named file bytes and not activation dependencies. The
current named subjects above are the reproducible requirements source.

## Final A1 boundary

The post-C1C final A1-AM3 ceiling remains exactly four MODIFY paths: `qa-provider-probe.py`,
`harness_qa/core/result.py`, `test-qa-provider-probe-adoption.py`, and
`verify-flake-first-roadmap-completion.sh`, at predecessors frozen in the roadmap recovery. The
other five A1 candidate paths remain frozen there. Verifier positive canonical-entrypoint and direct
Phase-0 assertions plus negative legacy-loop fixtures remain mandatory.

This rebind is non-activatable until: owner ratifies C1C-AM1's fail-stop SRE tradeoff; C1C-AM1 is
reviewed, activated, independently accepted, and committed; and a final amendment binds that exact
commit, acceptance, process-owner hash, lifecycle-test hash, all nine A1/verifier hashes, and this
required implementer identity. No owner wording can waive these gates.

A2 and all provider/live/network/heartbeat/evidence/Phase-0/API/browser/deployment actions remain
blocked. No staging, commit, deletion, or candidate edit is authorized.

`RECORD: PREPARED_ONLY / NON-ACTIVATABLE.`
