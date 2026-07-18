# Foundation B2-M1A acceptance-recovery authorization review

**Review date:** 2026-07-18 UTC
**Reviewer role:** independent recovery-authorization, database-boundary, security, and SRE reviewer
**Subject:** `B2-M1A-ACCEPTANCE-RECOVERY-AUTHORIZATION.md`
**Subject SHA-256:** `e4509b3d6dc593ca51ed1608d6e3c9761bf6e35f06b9ddc9a52735925cd2f29a`
**Verdict:** **PASS**

## 1. Bound evidence

The review recomputed and matched the recovery grant's evidence chain:

| Subject | SHA-256 / identity | Result |
|---|---|---|
| procedural-stop record | `df4afae478a399d5748710bb66089b405f2513dd4000a131e1b0c9880e4504f0` | match |
| consumed implementation authorization | `0db0a396331ee0eabbc91259c11a6ac14bb3ebd5fdd46735d291a201c6a0e906` | match |
| accepted design packet revision 4 | `020462d0ec3222bc893c7543712856a80ce8acb92b5b9caa48ab3a902e1860aa` | match |
| revision-1 review | `ed816d7d02c237216ffb85678dc16b03fc07429eef19d75afd8d20a809fc30f4` | match |
| revision-2 review | `26e3fad6d524d2d88d39ec0eedb63a1f083109260b1160a45d6def827603a052` | match |
| revision-3 review | `09e994c8f7fa7e9df11f0b00d412d7304d523187568e61bce8a3c95483d085f1` | match |
| revision-4 review | `84cd8a5b2f8e5d272c548c40e0fe02e50d53333a2a13f57aa84f6e30ac16a6ce` | match |
| accepted B2-C1 implementation | Git `8e285cdd978f2fc020393ac4327747f3e8f31476` | bound |

The reviewed authorization accurately records the incident: forbidden integration mode returned the
stable refusal before a DSN read, driver import, socket, subprocess, database operation, Alembic call,
DDL render/execution, or candidate-byte mutation. It treats containment as evidence rather than a
waiver and leaves the original authorization consumed.

## 2. Exact frozen candidate

All seven required candidate hashes were independently recomputed and match:

| # | Path | SHA-256 |
|---:|---|---|
| 1 | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | `73730c4a89d751c7d7ee9761b29a7183de561d5e6a4e1d1de0fda12281478468` |
| 2 | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | `22aad9bdc3491bb9f17124a9aba782a25bc44e6f6552d8b4158e9c5bf0eaa914` |
| 3 | `nix/modules/services/mcp-servers.nix` | `d822547d50f7fb09987a368043c6e96b8b3ac53de140e91e0b2ee326cb6d3ed8` |
| 4 | `config/workflow-shadow-db-privileges.json` | `ff141f3685dfd72e6147cb70d758f26abb6b0826f759ce8f9a59353c8c1eeb43` |
| 5 | `scripts/testing/test-workflow-shadow-migration.py` | `208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df` |
| 6 | `config/validation-check-registry.json` | `a7870d07091ba15d947ee6712b50fe6b0f8d779060f98a0dd4d9c3af23304a8d` |
| 7 | `ai-stack/migrations/test-migrations.sh` | `353d7c6d1a134d8606d0c75c420f11a8615e82f44f9ed24ac799b0aeeb7de6b3` |

Path-limited `git status` showed exactly the expected four modified and three new candidate paths.
Path-limited `git diff --check` passed. No candidate edit or eighth implementation path was introduced
by this review.

## 3. Authority-boundary adjudication

The recovery authorization is sufficiently narrow and fail closed:

1. It permits no implementation or candidate edit and binds one exact-byte, single-use acceptance
   verdict to `codex-subagent-b2-m1a-recovery-acceptance`.
2. It requires independent review before activation and then an owner statement naming this exact
   authorization hash, the operator, start time, and expiry no more than 24 hours later.
3. Its complete execution allowlist is limited to hash comparison, path-limited status/diff
   inspection, in-memory Python syntax parsing without imports or bytecode, standard-library JSON
   parsing, Bash syntax, read-only source search, and the exact no-argument default-offline oracle.
4. It expressly prohibits integration flags, DSN or token material, Alembic commands/APIs, database
   clients/drivers, DNS/network/socket/process activity, Nix evaluation/build/deployment, services,
   broader test runners, runtime adoption, staging, and commit by the acceptance operator.
5. It makes any drift, candidate write, forbidden invocation, expanded command path, or dynamic-proof
   claim a hard stop. A fail-closed result is not an exception.
6. It bridges the prior broad validation only through exact candidate-byte identity and does not
   authorize rerunning `aq-qa`, Tier-0, Phase-0, or other runners.
7. It preserves legacy JSON as sole live authority and explicitly leaves M1E, database connectivity,
   DDL, grants, runtime adoption, traffic, cutover, cleanup, rollback, and later B2 slices unauthorized.

This review used only read-only document and candidate hashing, path-limited status/diff inspection,
and read-only authorization text inspection. It did not run the candidate oracle, broad QA, Tier-0,
Phase-0, Alembic, Nix evaluation, a database/client/driver, a socket/process check, or any deployment
action. It did not edit candidate or authorization bytes, stage, or commit.

## 4. Verdict and next gate

`VERDICT: PASS — the exact recovery authorization at SHA-256
e4509b3d6dc593ca51ed1608d6e3c9761bf6e35f06b9ddc9a52735925cd2f29a is suitable for one
static-only, no-edit acceptance recovery after a fresh expiring owner activation naming
codex-subagent-b2-m1a-recovery-acceptance. This PASS authorizes no acceptance execution by itself.`
