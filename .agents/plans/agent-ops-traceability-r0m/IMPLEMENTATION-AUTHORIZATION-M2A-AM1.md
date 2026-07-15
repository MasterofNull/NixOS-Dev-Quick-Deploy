# Prepared Implementation Authorization — Agent Ops Traceability M2A Amendment 1

**Decision:** `implementation_authorized = PREPARED_ONLY_PENDING_FABLE_CONFIRMATION`
**Authorization ID:** `auth-agent-ops-m2a-am1-20260715`
**Idempotency key:** `m2a-am1-2d8fc2d7-20260715-single-use`
**Prepared:** 2026-07-15 by Codex orchestrator
**Activation:** requires (1) Fable flagship `PASS` or explicit owner waiver of that unavailable lane,
then (2) explicit owner activation of this exact authorization ID
**Amendment binding:** `M2A-INVENTORY-AMENDMENT-1.md` SHA-256
`2d8fc2d759bab8dc595f05fa09cfd5de331cf9466025e9a9470386b8d3883fa8`
**Review evidence:** `antigravity-m2a-inventory-amendment-1-review.md` (`PASS`)
**Unavailable review evidence:** monitored Fable task `claude-20260715-154248-hu6hof` returned no verdict
because the Claude account session limit was reached

## Preconditions

- Original authorization `auth-agent-ops-m2a-20260715` is suspended at commit `7a839b80`.
- The unauthorized fixture edit was restored byte-for-byte; its working-tree diff is empty.
- The retained eight-file candidate passes the focused M2A suite 51/51.
- The restored parent reliability suite fails 3/16 only because the frozen TaskRegistry source hash
  remains intentionally stale and D8/D11 therefore fail closed.
- Antigravity independently approved the one-file, two-scalar amendment.
- This grant remains inert until the review and owner-activation conditions above are satisfied.

## Exact ten-file binding

| File | Bound candidate / preparation state |
|---|---|
| `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PRD.md` | `2be0a0a2472a49af032ff563ae5822af2bfc041c12d646a8373129e73e7ef798` |
| `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PLAN.md` | `0d7a726eaf9e429e23efc03a843d75b566e1e3b0c19bd44edbeeab4d9771d049` |
| `config/schemas/delegation-task-record.schema.json` | `d15baf71a63273a675e6d5286530ed6cc0cd5fd62ca203d73de39434b9ca68f3` |
| `config/schemas/agent-ops-projection.schema.json` | unchanged `4aace22c05cacc4bc1135b5c82976552dbb7e16d4f424d0a462240ddaa5d53e0` |
| `scripts/ai/lib/agent_ops_projection.py` | `53491a1c27b7b270caea67a57dd5375c279242207668e8c98f96c9fa92ea3511` |
| `scripts/testing/test-agent-ops-projection.py` | `241bee32bbc71f5513a2d4a17ba4434bffb7d6f0a80e65cc7bde01b0d9685fe9` |
| `scripts/ai/aq-delegation-registry` | `06b2eb781afab996683926d418b0ff32fe55ee54901b9b0aa6d623be0c26355d` |
| `scripts/ai/lib/task_registry.py` | `33bb715cf8c644b9e1cc14ef7190562976321d4cce5cf51fcf4cb435f1e7a496` |
| `docs/operations/agent-ops-window.md` | `94e326dc09bf29b7eb07ca0beda5146d308c86ba3c6d1d1611be14da340a05ff` |
| `scripts/testing/fixtures/local-delegation-reliability-golden.json` | restored `5f962337c7e6f2a9700d3fd27ea60b55de15252fc449a9ba921e1c299323bc97` |

Any drift in the first nine bindings before activation requires review refresh.

## Grant after explicit activation

One implementer may change only the restored fixture and only these two scalar values:

1. TaskRegistry live-source SHA-256 to
   `33bb715cf8c644b9e1cc14ef7190562976321d4cce5cf51fcf4cb435f1e7a496`.
2. `stable_digests.source_manifest` to
   `3281a6234c8d64095d92bc57f1705f7d3e490755fae943e5455b8491b2d93a56`.

The implementer may not reformat the fixture, reorder keys, weaken or add characterizations, touch any
other scalar, revise the retained candidate, use `git stash`, stage, commit, deploy, or edit an
eleventh file. A third changed line is a hard stop.

## Required evidence

1. Fixture diff is exactly two removed scalar lines plus two replacement scalar lines.
2. Focused M2A suite passes 51/51 or more.
3. Parent local-delegation-reliability suite passes 16/16.
4. All five live delegation-wrapper hashes remain unchanged.
5. Tier0 passes.
6. Independent flagship acceptance reviews the complete ten-file candidate before commit.

M2B, M3, local reliability R1–R4, inference R1–R4, live cutover, new stores, and all other files remain
unauthorized.

`RECORD: PREPARED_ONLY_PENDING_FABLE_CONFIRMATION for auth-agent-ops-m2a-am1-20260715; no implementation authority is granted or implied.`
