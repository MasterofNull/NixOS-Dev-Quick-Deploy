# Foundation B2-M1A recovery acceptance review

**Review date:** 2026-07-19 UTC
**Reviewer identity:** `codex-subagent-b2-m1a-recovery-acceptance`
**Reviewer role:** independent static recovery acceptance operator
**Authorization:** `B2-M1A-ACCEPTANCE-RECOVERY-AUTHORIZATION.md`
**Activated authorization SHA-256:** `b8455788464bd22f261e0e5254c1cc3bce2f7af3b881cf2cd92eb0ce77da4b3a`
**Owner activation window:** 2026-07-18T18:08:30Z through 2026-07-19T18:08:30Z
**Verdict:** **REQUEST_REVISION — static oracle coverage is incomplete and the recovery command discipline was not exact**

## 1. Exact-byte subject and containment lineage

The required first and final digest passes both produced the following exact identities:

| Subject | SHA-256 |
|---|---|
| recovery authorization | `b8455788464bd22f261e0e5254c1cc3bce2f7af3b881cf2cd92eb0ce77da4b3a` |
| normalized procedural-stop record | `2572e4ab858842ea272648d223c4cb503d8f8bfa1a123bb9680653211219532f` |
| consumed implementation authorization | `0db0a396331ee0eabbc91259c11a6ac14bb3ebd5fdd46735d291a201c6a0e906` |
| accepted design packet revision 4 | `020462d0ec3222bc893c7543712856a80ce8acb92b5b9caa48ab3a902e1860aa` |
| revision-1 design review | `ed816d7d02c237216ffb85678dc16b03fc07429eef19d75afd8d20a809fc30f4` |
| revision-2 design review | `26e3fad6d524d2d88d39ec0eedb63a1f083109260b1160a45d6def827603a052` |
| revision-3 design review | `09e994c8f7fa7e9df11f0b00d412d7304d523187568e61bce8a3c95483d085f1` |
| revision-4 design review | `84cd8a5b2f8e5d272c548c40e0fe02e50d53333a2a13f57aa84f6e30ac16a6ce` |

The procedural-stop record remains the governing containment lineage. Its prior prohibited
`--integration` attempt returned `M1E_NOT_AUTHORIZED` before DSN, driver, socket, subprocess,
database, Alembic, DDL, or byte mutation. This review did not repeat that invocation.

The exact seven-file candidate remained byte-identical before and after all static checks:

| # | Path | SHA-256 |
|---:|---|---|
| 1 | `ai-stack/migrations/versions/20260125_01_add_llm_used_column.py` | `73730c4a89d751c7d7ee9761b29a7183de561d5e6a4e1d1de0fda12281478468` |
| 2 | `ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py` | `22aad9bdc3491bb9f17124a9aba782a25bc44e6f6552d8b4158e9c5bf0eaa914` |
| 3 | `nix/modules/services/mcp-servers.nix` | `d822547d50f7fb09987a368043c6e96b8b3ac53de140e91e0b2ee326cb6d3ed8` |
| 4 | `config/workflow-shadow-db-privileges.json` | `ff141f3685dfd72e6147cb70d758f26abb6b0826f759ce8f9a59353c8c1eeb43` |
| 5 | `scripts/testing/test-workflow-shadow-migration.py` | `208a9bf29d05a1162f38fb1fdb29ebd79d38261fbf9af1ded31093ef4bfe34df` |
| 6 | `config/validation-check-registry.json` | `a7870d07091ba15d947ee6712b50fe6b0f8d779060f98a0dd4d9c3af23304a8d` |
| 7 | `ai-stack/migrations/test-migrations.sh` | `353d7c6d1a134d8606d0c75c420f11a8615e82f44f9ed24ac799b0aeeb7de6b3` |

Path-limited status showed exactly four modified and three new authorized paths. `git diff --check`
returned exit 0. The tracked textual diff contained only the `aidb` branch label, branch-qualified Nix
and canonical test targets, and one default-mode registry entry. No eighth implementation path or
candidate-byte edit was observed.

## 2. Permitted static evidence

| Command or read-only operation | Exit/result |
|---|---|
| first and final `sha256sum` passes over all bound evidence and seven candidate paths | 0; all exact |
| path-limited `git status --short` | 0; exact four-modified/three-new shape |
| path-limited `git diff --check` | 0 |
| path-limited textual `git diff` | 0; tracked changes bounded as described above |
| `ast.parse` of both migration sources and the static oracle | 0; three sources parsed without import or bytecode |
| standard-library JSON parsing of the privilege policy and validation registry | 0; two documents parsed |
| `bash -n ai-stack/migrations/test-migrations.sh` | 0 |
| oracle hash recheck immediately before invocation | 0; exact `208a9bf2...34df` |
| `python3 scripts/testing/test-workflow-shadow-migration.py` with no arguments | 0; static `PASS`, legacy JSON authoritative |
| read-only source searches for branch, process/network, destructive, secret, and runtime surfaces | 0; findings described below |

No `--integration`, `--dsn-file`, evidence token, Alembic command/API, SQL rendering, database client,
driver, DSN read, DNS, socket, network, child subprocess from the candidate oracle, Nix evaluation,
build, activation, deployment, service action, runtime hook, traffic, cutover, `aq-qa`, Phase-0, or
Tier-0 runner was invoked. Neither migration source was imported or executed. No bytecode/cache was
generated. No candidate byte was edited, staged, or committed. This record makes no claim that DDL,
branch resolution, grants, rollback, database health, migration readiness, or M1E behavior was
dynamically proven.

## 3. Blocking acceptance finding — incomplete static-oracle coverage

The original authorization sections 3.4 and 7 item 8 require the static oracle to verify the complete
design contract and every positive and negative policy cell. The exact oracle can return `PASS` while
material closed-contract cells are absent or expanded:

1. `scripts/testing/test-workflow-shadow-migration.py:28` lists the existing AIDB revision path, but
   no later code reads that file or verifies its `branch_labels = ("aidb",)` declaration. A missing
   AIDB label could therefore pass the oracle while making `aidb@head` invalid.
2. `check_policy()` validates only the delivery and reader table maps. It does not require the exact
   `schema` or `functions` cells for either role. An added delivery/reader schema privilege or function
   privilege can therefore pass.
3. The function, trigger, index, constraint, and foreign-key policy collections participate only in a
   cross-list duplicate-name count. Their exact identities and their correspondence to migration SQL
   are not asserted. Missing or substituted security/constraint objects can therefore pass.
4. The policy digest constant binds bytes but the migration does not load the policy, so the digest
   does not close the omitted source-to-policy comparisons.

The independent read-only search for these assertions returned only the AIDB path tuple at oracle
line 28 and no matching exact-cell/source-binding assertions. This is a candidate acceptance defect,
not dynamic database evidence. Repair requires candidate-byte changes and therefore triggers the
authorization's mandatory stop and fresh candidate/review sequence.

## 4. Procedural command-discipline disclosure

Before the exact recovery scope was fully loaded, the reviewer used the repository-mandated
`lean-ctx` wrapper to read the two assigned skill files and invoked `lean-ctx read --help` (failed) and
`lean-ctx --help` (exit 0) to recover uncompressed skill content. It also used `rg --files` to locate
the B2 plan records. The remaining document reads were read-only `sed` through `lean-ctx`, followed by
only the enumerated static operations above.

These preliminary help/file-list operations caused no candidate read/write, process launch from the
candidate, database, socket, Alembic, Nix, QA, deployment, or runtime effect. They nevertheless are
not named in the recovery authorization's entire top-level command allowlist. Consequently this
review cannot truthfully confirm that no unlisted command ran. Under the strict single-use recovery
contract there is no harmless-command exception; this is an independent procedural reason that the
grant cannot earn `PASS`.

## 5. Required next gate

Do not stage or commit the seven-file candidate as accepted. A bounded amendment must close every
privilege-policy and source-binding hole, including the AIDB label assertion, then produce new exact
candidate hashes, independent review, a fresh static-recovery authorization, independent review of
that authorization, and a fresh expiring owner activation. The next acceptance operator must begin
with the exact authorization command allowlist already loaded by the orchestrator so no discovery or
help command is needed inside the activation window.

Legacy `workflow-sessions.json` remains the sole live authority. M1E, database connectivity, DDL
render/execution, grants, runtime adoption, deployment, traffic, cutover, cleanup, rollback, and all
later B2 slices remain unauthorized.

VERDICT: REQUEST_REVISION — the exact candidate is contained, but its static oracle does not cover the required closed privilege/source contract, and this recovery run cannot attest to exact command-allowlist compliance
