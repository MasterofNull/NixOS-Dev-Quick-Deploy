# Foundation B2-M1A acceptance-recovery authorization review — revision 2

**Review date:** 2026-07-18 UTC
**Reviewer role:** independent recovery-authorization, database-boundary, security, and SRE reviewer
**Subject:** `B2-M1A-ACCEPTANCE-RECOVERY-AUTHORIZATION.md`
**Subject SHA-256:** `b8455788464bd22f261e0e5254c1cc3bce2f7af3b881cf2cd92eb0ce77da4b3a`
**Verdict:** **PASS**

## 1. Rebound evidence and semantic equivalence

The exact subject binds the normalized procedural-stop record at SHA-256
`2572e4ab858842ea272648d223c4cb503d8f8bfa1a123bb9680653211219532f`. The normalized record differs
from prior identity `df4afae478a399d5748710bb66089b405f2513dd4000a131e1b0c9880e4504f0` only by removal of two
trailing spaces from metadata lines 3 through 8. Restoring those six suffixes in a read-only stream
reproduces the prior digest exactly. Its incident finding, containment facts, procedural-stop verdict,
and required recovery gate are semantically unchanged.

The recovery authorization itself is also a semantic rebind. A read-only reconstruction that:

1. restores the normalized metadata hard-break suffixes on lines 3 through 7;
2. restores the prior procedural-stop digest in the evidence table; and
3. removes the new four-line normalization explanation

reproduces the prior authorization SHA-256
`e4509b3d6dc593ca51ed1608d6e3c9761bf6e35f06b9ddc9a52735925cd2f29a` exactly. No authority,
command allowlist, operator identity, expiry, stop condition, acceptance requirement, or exclusion was
weakened. The previous authorization review at SHA-256
`ec70f3290a188679dc5731052e0b33ac992dc2b70eec6b1b5481387fbbed0b71` is retained only as stale
historical evidence and grants no authority over this new subject.

The remaining bound evidence also matches:

| Subject | SHA-256 / identity |
|---|---|
| consumed implementation authorization | `0db0a396331ee0eabbc91259c11a6ac14bb3ebd5fdd46735d291a201c6a0e906` |
| accepted design packet revision 4 | `020462d0ec3222bc893c7543712856a80ce8acb92b5b9caa48ab3a902e1860aa` |
| revision-1 review | `ed816d7d02c237216ffb85678dc16b03fc07429eef19d75afd8d20a809fc30f4` |
| revision-2 review | `26e3fad6d524d2d88d39ec0eedb63a1f083109260b1160a45d6def827603a052` |
| revision-3 review | `09e994c8f7fa7e9df11f0b00d412d7304d523187568e61bce8a3c95483d085f1` |
| revision-4 review | `84cd8a5b2f8e5d272c548c40e0fe02e50d53333a2a13f57aa84f6e30ac16a6ce` |
| accepted B2-C1 implementation | Git `8e285cdd978f2fc020393ac4327747f3e8f31476` |

## 2. Exact unchanged seven-file subject

All candidate digests were independently recomputed and remain exact:

| # | Path | SHA-256 |
|---:|---|---|
| 1 | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | `73730c4a89d751c7d7ee9761b29a7183de561d5e6a4e1d1de0fda12281478468` |
| 2 | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | `22aad9bdc3491bb9f17124a9aba782a25bc44e6f6552d8b4158e9c5bf0eaa914` |
| 3 | `nix/modules/services/mcp-servers.nix` | `d822547d50f7fb09987a368043c6e96b8b3ac53de140e91e0b2ee326cb6d3ed8` |
| 4 | `config/workflow-shadow-db-privileges.json` | `ff141f3685dfd72e6147cb70d758f26abb6b0826f759ce8f9a59353c8c1eeb43` |
| 5 | `scripts/testing/test-workflow-shadow-migration.py` | `208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df` |
| 6 | `config/validation-check-registry.json` | `a7870d07091ba15d947ee6712b50fe6b0f8d779060f98a0dd4d9c3af23304a8d` |
| 7 | `ai-stack/migrations/test-migrations.sh` | `353d7c6d1a134d8606d0c75c420f11a8615e82f44f9ed24ac799b0aeeb7de6b3` |

No candidate byte or authorization byte was edited by this review.

## 3. Recovery-boundary adjudication

The rebound grant remains suitable because it:

- is single use and binds one exact-byte acceptance verdict to
  `codex-subagent-b2-m1a-recovery-acceptance`;
- requires this independent review plus a later owner activation naming the exact subject hash,
  operator, start time, and expiry no more than 24 hours later;
- permits no candidate edit, normalization, generation, import, bytecode, staging, or reviewer commit;
- restricts execution to hashing, path-limited status/diff inspection, in-memory syntax parsing,
  standard-library JSON parsing, Bash syntax, read-only searches, and the exact no-argument default
  offline oracle;
- prohibits every alternate oracle argument or environment-expanded path, including `--integration`,
  DSN files, and M1E evidence tokens;
- prohibits Alembic commands/APIs, SQL rendering, databases/clients/drivers, DNS/network/sockets,
  child processes, Nix evaluation/build/activation/deployment, services, runtime hooks, traffic,
  cutover, dashboard claims, and broad QA, Tier-0, or Phase-0 reruns;
- makes drift, an eighth path, any prohibited attempt, or any dynamic database-readiness claim an
  immediate hard stop without a fail-closed exception; and
- keeps legacy JSON as sole live authority while M1E, DDL, grants, runtime adoption, cleanup,
  rollback, and later B2 slices remain unauthorized.

This review ran only read-only hashing, line-numbered text inspection, trailing-whitespace search, and
an in-memory reconstruction hash. It did not invoke the candidate oracle, Python migration imports,
Alembic, a database/client/driver, a socket or child-process probe, Nix, QA, Tier-0, Phase-0, a service,
or deployment. It did not stage or commit.

## 4. Verdict and next gate

`VERDICT: PASS — the rebound recovery authorization at SHA-256
b8455788464bd22f261e0e5254c1cc3bce2f7af3b881cf2cd92eb0ce77da4b3a is semantically equivalent,
correctly binds the normalized procedural-stop record and unchanged seven-file subject, and is
suitable for one static-only, no-edit recovery acceptance after a fresh expiring owner activation
naming codex-subagent-b2-m1a-recovery-acceptance. This PASS authorizes no acceptance execution.`
