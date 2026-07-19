# QPPR-C1C Amendment 1 implementation authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-c1c-am1-20260719`  
**Required implementer:** `codex-subagent-qppr-c1c-am1-implementer`  
**Status:** **PREPARED_ONLY / OWNER SRE RATIFICATION REQUIRED — NOT ACTIVATED**

## Exact binding and ceiling

| Subject | SHA-256 |
|---|---|
| C1C-AM1 SRE amendment | `bced486ad8af5ced589b71a853ccdffe2927dd5288b650e0c2b48c7eaa924f3c` |
| blocking review | `15a1b110e2483d6be46aa8f46faf56fd27288ce4fbfc611fbea944dcb0c81e38` |
| process owner predecessor | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` |
| lifecycle test predecessor | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` |
| frozen observer test | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` |

The exact ceiling is the two MODIFY paths in the amendment section 2. Only the required implementer
may implement after independent review, explicit owner ratification of the non-returning callback
fail-stop/no-finite-redelivery tradeoff, and owner activation of this exact authorization hash.

## Exact validation commands

The implementer and independent reviewer must run exactly:

```bash
python3 scripts/testing/test-qa-provider-probe-lifecycle.py
python3 scripts/testing/test-qa-provider-probe-observer.py
python3 -m py_compile scripts/testing/harness_qa/core/process_lifecycle.py scripts/testing/test-qa-provider-probe-lifecycle.py
sha256sum scripts/testing/test-qa-provider-probe-observer.py
git diff --check -- scripts/testing/harness_qa/core/process_lifecycle.py scripts/testing/test-qa-provider-probe-lifecycle.py
rg -n 'shell=True|os\.system|https?://|BEGIN (RSA|OPENSSH) PRIVATE KEY|Bearer [A-Za-z0-9]' scripts/testing/harness_qa/core/process_lifecycle.py scripts/testing/test-qa-provider-probe-lifecycle.py
```

Expected observer hash is the frozen value above. The final `rg` command must return no matches.
After independent exact-candidate `PASS`, only the orchestrator runs
`scripts/governance/tier0-validation-gate.sh --pre-commit` before staging/commit. No weaker or
substituted command earns acceptance.

## Stops and completion

All amendment stops apply. The implementer cannot delegate, stage, commit, deploy, or self-accept.
Control-plane session/intent/resume/pulse/handoff/registry evidence is outside the product ceiling,
contains no product code, and is not staged with C1C-AM1. Tests use isolated local fixtures only.
No provider/live/network/heartbeat/evidence/Phase-0/A1/A2/API/browser/Nix/service/deploy action.

An independent exact-hash reviewer must accept the two-file candidate. C1C-AM1 acceptance/commit is
only an A1 prerequisite and grants no A1 authority. A1-AM3 requires final exact rebind; A2 stays
blocked.

`RECORD: PREPARED_ONLY. Owner SRE ratification and exact activation are absent; implementation and
all live actions remain unauthorized.`
