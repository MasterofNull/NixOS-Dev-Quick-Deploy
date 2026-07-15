# Consumed Implementation Authorization — Agent Ops Traceability M1

**Decision:** `implementation_authorized = CONSUMED`
**Authorization ID:** `auth-agent-ops-m1-20260715`
**Idempotency key:** `6de63005-a8eb-4d3b-8efa-c565a5cf1069`
**Prepared:** 2026-07-15 by Codex orchestrator
**Activated:** 2026-07-15 by Codex orchestrator under owner direction
**Review evidence:** `antigravity-m1-design-review.md` (`PASS`, SHA-256 `a4c0e3ddbfc5df82505749108aea9a60b48eba0c3b83a97180efe8ea21abcdf7`)
**Consumed:** 2026-07-15 after producing the staged M1 review candidate; any revision requires a new grant

## Preconditions

- R0 reliability contract accepted and committed: `8c26a7de`.
- M0 pure projection accepted and committed: `a8e94249`.
- L2B-A accepted and committed: `fbeffbab`.
- Antigravity explicitly unblocked M1–M3 for separate authorization.
- M1 design/inventory review: **PASS**.

## Subject binding at preparation

| File | SHA-256 |
|---|---|
| `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PRD.md` | `e8601801034bd83b4897aedf8f4f7fcfc565d285a9e73e30bcd2e485af211199` |
| `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PLAN.md` | `e93e56158c75edbb96fc53a0a916138a890ade2d0314bd25b91ccb416e94a48f` |
| `config/schemas/agent-ops-projection.schema.json` | `4aace22c05cacc4bc1135b5c82976552dbb7e16d4f424d0a462240ddaa5d53e0` |
| `scripts/ai/lib/agent_ops_projection.py` | `8fe991be4e7d5652ba4a488664ae9c4129e944069e0f341f560473700cbf29f5` |
| `scripts/testing/fixtures/agent-ops-projection-golden.json` | `faa4ee68ddb0194d592a0e96a5e92faee3327ee06948638f69ac26a608cf9163` |
| `scripts/testing/test-agent-ops-projection.py` | `8c3ce0df50e067d9b30a62ac2ca4e2592d7a8d0eab153ab4c1e895912a359b08` |
| `scripts/ai/aq-tui-dashboard` | `d2c4caa070a3cd483ff20acfc0d29ac7347078b08ba0a3556450c63aafd98f80` |
| `docs/operations/agent-ops-window.md` | `989799802ee92f4cf8d2a18d2d23f2f790bbca398136ced6379c1139d993a64c` |

Repository base: `fbeffbab`. Any bound-file drift before activation requires review refresh.

Activation changed only the reviewed PRD/plan status and review-evidence wording. The implementation
start hashes are PRD `b071a351ffc066409450cf698005cdff41daaf5d047dce856fb497af48b2cdbd` and plan
`3d432b47db81b26c7a36b3500669e245c87fca8a9d30a52de7e99486080bedec`; the other six subject
hashes remain as reviewed above.

## Proposed grant

Once activated, one implementer may edit only the eight bound M1 files. M1 may:

- add bounded read-only adapters for process, registry, trusted progress, and Antigravity inbox facts;
- inject those facts into the accepted M0 pure projector;
- replace raw substring classification in Agentic Ops with projector records;
- expose sanitized TUI cards and machine JSON for tracked, idle, stale, untracked, conflict, and blocked;
- add adversarial fixtures/tests and update the operator document.

M1 may not write or repair registry/inbox/process/lifecycle state, terminate processes, change any
delegation wrapper, add Phase-0/Bash/registry gates, modify the web dashboard, alter inference,
introduce a store, or touch a ninth file.

## Mandatory implementation evidence

1. Stable PID identity uses start time; PID-only correlation is forbidden.
2. Executable/argv parsing uses NUL boundaries; arbitrary substring matching cannot assert work.
3. Parent/child wrappers deduplicate only with bounded ancestry/cgroup evidence.
4. Missing/denied `/proc`, generic/missing cgroups, oversized inputs, malformed JSON, and terminal/live
   conflicts render typed degraded/blocked results rather than exceptions or nominal cards.
5. Registry, progress, and inbox reads are byte/count/time bounded and reject symlinks/non-regular files.
6. Default cards/metrics expose no prompt, output, raw argv, secrets, unbounded IDs, or sensitive paths.
7. Unit fixtures pass in the managed sandbox. Final acceptance also requires a host-visible smoke run
   because the Codex implementation sandbox has a private PID namespace and cannot validate host
   process convergence itself.

## Validation after activation

```bash
python3 scripts/testing/test-agent-ops-projection.py
scripts/ai/aq-tui-dashboard --json
scripts/governance/tier0-validation-gate.sh --pre-commit
```

The TUI smoke is diagnostic during implementation and becomes acceptance evidence only when executed
from a host-visible reviewer/operator lane. Synthetic facts must be labeled fixtures.

## Stop conditions

Stop immediately for any out-of-inventory edit, new writer/store, process mutation, prompt exposure,
uncorrelated process shown nominal, raw substring used as authority, host-smoke substitution with a
private PID namespace, inference behavior change, or need for M2 wrapper/gate work.

`RECORD: implementation_authorized = CONSUMED after one M1 implementation; M2–M3 and R1–R4 remain UNAUTHORIZED.`
