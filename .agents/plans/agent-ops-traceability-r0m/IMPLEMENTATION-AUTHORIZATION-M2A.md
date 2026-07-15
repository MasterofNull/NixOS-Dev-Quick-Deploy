# Prepared Implementation Authorization — Agent Ops Traceability M2A

**Decision:** `implementation_authorized = SUSPENDED_PENDING_INVENTORY_AMENDMENT`
**Authorization ID:** `auth-agent-ops-m2a-20260715`
**Idempotency key:** `m2a-2b4a2aad-20260715-single-use`
**Prepared:** 2026-07-15 by Codex orchestrator
**Activated:** 2026-07-15 by explicit owner command `Activate auth-agent-ops-m2a-20260715`
**Suspended:** 2026-07-15 by Codex orchestrator after the implementer discovered that the mandatory
R0 reliability source-manifest fixture must change when `task_registry.py` changes; that fixture is
outside this authorization and cannot be edited without a reviewed owner-approved amendment
**Design binding:** `M2-DESIGN-PACKET.md` SHA-256
`2b4a2aad1960927554ec1f72af4e6bd458cbb0529fa7bea645a677c62fb52428`
**Review evidence:** `claude-fable-m2-rev3-review.md` (`PASS`) and
`antigravity-m2-rev3-review.md` (`PASS`)

## Preconditions

- M0 and M1 are accepted and committed.
- L2B-A and L2B-A.1 are accepted and committed.
- M2 Revision 3 has independent Fable and Antigravity flagship PASS verdicts.
- The Fable routing bootstrap is committed as `dde2601f`.
- Owner activation is recorded above; the grant is single-use and becomes consumed when one bounded
  M2A implementation candidate is produced for independent acceptance.

## Exact nine-file inventory and preparation hashes

| File | Preparation state / SHA-256 |
|---|---|
| `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PRD.md` | `f4846924ef3684c094a3cf48ba3404ae9fe245992aa7b3799ed5fd3ee64e75a5` |
| `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PLAN.md` | `1b394767da1c9406000158727f65edb02a810957afe7692c0992af6bbe45eb6d` |
| `config/schemas/delegation-task-record.schema.json` | `ABSENT — sole new implementation file` |
| `config/schemas/agent-ops-projection.schema.json` | `4aace22c05cacc4bc1135b5c82976552dbb7e16d4f424d0a462240ddaa5d53e0` |
| `scripts/ai/lib/agent_ops_projection.py` | `687f43380fc999f6e51aa3d7b79d71e28313af5c2034463f5671fb53279512a8` |
| `scripts/testing/test-agent-ops-projection.py` | `a19c083580afff111ef027ea0bfbce068f9fb27f82658d92c940853eef536fa9` |
| `scripts/ai/aq-delegation-registry` | `95287c20577ca81f7da0792782b393baf163e90faec066c6c2b658a3bb28bcd8` |
| `scripts/ai/lib/task_registry.py` | `c6d2da793a2804d184567c4096eb20bd35677bb8e6a2652b18e0328eeff689ca` |
| `docs/operations/agent-ops-window.md` | `2f4a748e790cfc41e6e339ce75a7e58459af72ffb24b1e10858a90950ee7be9a` |

Repository base at preparation: `dde2601f`. Any bound-file drift before activation requires a review
refresh. Any tenth implementation file is a stop condition.

## Grant after explicit activation

One implementor may produce one dormant M2A candidate limited to the nine files above. M2A may:

- add the closed Draft 2020-12 delegation task-record schema with no raw prompt or prompt-derived
  digest property;
- make `TaskRegistry` and `aq-delegation-registry` provide bounded, transactional, revision-checked
  `begin`, `attach-process`, `transition`, `show`, and `reconcile` primitives;
- use a stable sibling lock inode, bounded lock acquisition, atomic replacement, file and parent-dir
  durability, and fail-closed symlink/non-regular-file handling;
- project fresh PID-less rows only as non-authoritative `degraded/queued` and promote only after PID
  plus process start-time correlation;
- add hermetic concurrency, illegal-transition, privacy-canary, and anonymous-pipe barrier tests; and
- document a dated activation deferral declaring M2B wrapper adoption unauthorized.

## Adoption guard and mandatory evidence

1. Existing delegation wrappers remain byte-for-byte unchanged by M2A and do not import or invoke the
   new writer/contract path.
2. No provider/fake-provider byte is emitted before successful PID/start-time attachment and barrier
   release; EOF, timeout, malformed release, and attachment failure never exec the provider.
3. Concurrent mutations lose no rows, create no duplicates, and never expose truncated JSONL.
4. New records reject unknown fields, illegal transitions, stale revisions, oversized input,
   symlinks, non-regular files, raw prompts, and prompt-derived digest fields.
5. The 30-second queued grace and 5-second future-skew bounds are deterministic and tested.
6. Phase-0, TUI route adoption, wrapper changes, and live traffic cutover are absent from M2A.
7. Independent flagship acceptance is required before commit or any M2B authorization.

## Validation after activation

```bash
python3 scripts/testing/test-agent-ops-projection.py
python3 scripts/testing/test-local-delegation-reliability.py
scripts/ai/aq-delegation-registry --help
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Explicit exclusions

M2A does not authorize edits to any delegation wrapper, TUI implementation, Phase-0/Bash/validation
gates, role matrix, web dashboard, inference path, service configuration, lifecycle database, or
process-killing route. M2B, M3, local reliability R1–R4, inference R1–R4, and Q8 authority decisions
remain unauthorized.

`RECORD: implementation_authorized = SUSPENDED_PENDING_INVENTORY_AMENDMENT for auth-agent-ops-m2a-20260715. The unauthorized fixture edit was restored exactly; the eight-file candidate is retained but may not be accepted, revised, staged, or committed until a new reviewed grant explicitly adjudicates the reliability fixture. M2B/M3/R1-R4 remain UNAUTHORIZED.`
