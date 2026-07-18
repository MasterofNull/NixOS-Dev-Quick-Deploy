# Foundation B2-M1 design and authorization review

**Review date:** 2026-07-18
**Reviewer:** Codex sub-agent `/root/b2_m1_review`
**Roles:** independent database migration architect, security/least-privilege reviewer, Nix integration reviewer, SRE, and contract reviewer
**Review type:** exact-subject PREPARED_ONLY design/authorization gate; no implementation or migration acceptance
**Overall verdict:** **REQUEST_REVISION**

## Exact subject

| Subject | SHA-256 | Verdict |
|---|---|---|
| `.agents/plans/aqos-foundation-b2/B2-M1-DESIGN-PACKET.md` | `d5a10d59470bda64a14cef33aeafaae305d998809749cc8a97e4a7ae912e10d8` | **REQUEST_REVISION** |
| `.agents/plans/aqos-foundation-b2/B2-M1-IMPLEMENTATION-AUTHORIZATION.md` | `ee70a8daf80369165d876e87a26c45e9252916856a0121c95c7c5320ec817f59` | **REQUEST_REVISION** |

Any content change invalidates this review subject. The reviewed files are `PREPARED_ONLY`; this
review performs and authorizes no implementation, Alembic execution or rendering, database access,
DDL, grant, Nix activation, deployment, or later B2 slice.

## Evidence and focused validations

- Read the B2 ADR, PRD, D0 packet/review, C1 authorization/review/acceptance, canonical Alembic
  configuration and revisions, the selected Nix service migration call, and the legacy/unwired
  migration environment.
- Recomputed every predecessor and read-only SHA-256 named by the authorization: all match. Git
  identities `8e285cdd978f2fc020393ac4327747f3e8f31476` and
  `19c78faaf5ab6d3635ac05a80fd5ba3c63cb1aae` resolve exactly. All three proposed new implementation
  paths are absent.
- `nix eval --raw .#nixosConfigurations.hyperd-ai-dev.pkgs.python3Packages.alembic.version` reports
  Alembic `1.18.1`. Read-only inspection of that exact Nix-store implementation confirms
  `branch@head` parsing and branch-label lineage filtering in `RevisionMap`; therefore `aidb@head` is
  supported by the deployed package. The exact future two-root candidate graph remains a candidate
  acceptance check because this review was prohibited from creating the revision or invoking
  Alembic, including offline mode.
- Repository-wide static search found two canonical-tree callers: the deployed Nix pre-start and
  `ai-stack/migrations/test-migrations.sh`. The latter invokes unqualified `upgrade head` twice and
  `downgrade -1` once.
- No database client, Alembic command, offline render, migration import, socket, service action,
  deployment, DDL, or Nix activation was executed.

## Findings requiring revision

### R1 — canonical migration test becomes invalid under the proposed two-head graph

The design correctly identifies unqualified `upgrade head` as unsafe once the dormant B2 root is
introduced, but its six-file ceiling changes only the Nix caller. The existing canonical test runner
`ai-stack/migrations/test-migrations.sh` still executes `upgrade head` at lines 6 and 8. With two
heads, Alembic 1.18.1 treats singular `head` as ambiguous and raises `MultipleHeads`; the canonical
migration test therefore regresses as soon as M1A lands. Its unqualified `downgrade -1` also needs an
explicit AIDB-lineage adjudication rather than being left to current-head state.

Required correction: include the canonical test runner in the M1A inventory, bind its predecessor,
and freeze branch-qualified forward and rollback behavior that cannot select or execute the dormant
B2 branch. Reconcile the D0 ceiling accurately: D0 describes a maximum eight-file **later migration
candidate inventory**; it does not say the design and authorization records consume two
implementation slots. A seven-file implementation candidate remains within that ceiling. If the
program intends governance files to count instead, that new interpretation must be stated as a
deliberate stricter amendment rather than attributed to D0.

### R2 — table grants do not enforce the promised expected-revision CAS boundary

The proposed writer receives direct `SELECT, INSERT, UPDATE` on `workflow_snapshot`. Those grants let
any holder issue an arbitrary qualifying update and bypass the promised `expected_revision` compare,
terminal transition checks, and mutation shape. Table checks can bound resulting values but cannot
prove that the caller supplied the expected prior revision. This conflicts with the design statement
that the snapshot is “mutable only by the writer through expected-revision CAS” and with the B2
zero-trust boundary.

Required correction: freeze a database-enforced mutation interface (for example, a narrowly scoped
owner function with fixed arguments, explicit CAS/terminal predicates, fixed `search_path`, revoked
`PUBLIC` execution, and writer `EXECUTE` without direct snapshot mutation grants), or explicitly
weaken the invariant and obtain architectural approval for application-enforced CAS. The privilege
policy, object/function inventory, positive/negative tests, and authorization acceptance criteria
must agree on one model. Do not leave this security decision to the implementer.

The related outbox claim must also be narrowed or enforced. An immutability trigger protects against
ordinary DML under the frozen grants, but it cannot protect against a principal that later becomes
table owner because an owner can disable or replace the trigger. Either state the guarantee only for
the accepted ownership/grant topology and continuously verify ownership, or specify a stronger
separate ownership/control boundary. The current “including ... a role that later gains table
ownership accidentally” claim is not supportable.

### R3 — migration executor, bootstrap privileges, and object-owner semantics are conflated

All four fixed roles, including `aq_b2_shadow_migrator_v1`, are created by the new revision as
`NOLOGIN`. Consequently that role cannot be the connection principal that begins the revision, and
it does not exist before the revision starts. Creating roles also requires an already-existing
bootstrap principal with `CREATEROLE` (normally the disposable test administrator/superuser), while
creating schema/objects owned by the new migrator requires explicit membership or administrator
authority. The packet calls the NOLOGIN role the “migration owner role” without distinguishing the
actual revision executor from the durable object-owner role or freezing `SET ROLE`/ownership behavior.

Required correction: name and constrain the pre-existing M1E bootstrap executor, state whether it
runs the revision as administrator and assigns ownership to the NOLOGIN owner role or switches role
after bootstrap, freeze the required membership/`CREATEROLE` boundary, and prove no bootstrap
membership or elevated attribute remains after the disposable run. The forward transaction and
injected-failure test must verify that roles, schema, ownership, grants, and the Alembic version row
all roll back together. Future live execution remains separately unauthorized and must not be
silently inferred from the ephemeral bootstrap model.

## Threat-model disposition

| Challenge | Result | Assessment |
|---|---|---|
| Multiple-head and branch resolution | **REVISION** | `aidb@head` is supported by installed Alembic 1.18.1, but the omitted canonical test runner retains ambiguous commands. |
| Accidental auto-apply | **PASS WITH CANDIDATE GATE** | Pinning the deployed pre-start to `aidb@head` prevents that caller from selecting B2; exact two-root graph proof remains required at candidate acceptance. |
| Revision/branch identity consistency | **PASS** | Filename, revision ID, branch label, policy identity, and Nix target are consistently distinguished and frozen. |
| Exact inventory / D0 ceiling | **REVISION** | Six files omit a required canonical caller; counting governance files against D0's candidate ceiling is not supported by D0 wording. |
| Transaction and failure rollback | **REVISION** | PostgreSQL transactional DDL/role changes are a sound target, but the bootstrap executor and ownership transition are not frozen. |
| NOLOGIN and least privilege | **REVISION** | Runtime roles are non-login and scoped, but direct snapshot UPDATE bypasses the stated CAS boundary and executor privileges are undefined. |
| Schema ownership and immutable outbox | **REVISION** | Current grants can isolate DML, but the accidental-owner trigger guarantee is false without ownership enforcement. |
| Static non-connectivity | **PASS** | M1A commands and validation registry are constrained to parsing/mocked import; integration gates precede driver/DSN access. |
| M1E separation | **PASS** | Disposable execution remains a distinct, expiring, post-acceptance authorization with no repo edits. |
| Destructive down refusal | **PASS** | `downgrade()` is required to raise before SQL; persistent cleanup remains unauthorized. |
| Resource/time bounds | **PASS** | Local SQL and suite/database ceilings are explicit, bounded, and non-retrying. |
| Predecessors, activation, stop/rollback | **PASS** | Hashes and absences match; activation remains explicit, single-use, expiring, and non-transitive. |

## Per-subject conclusion

- **Design packet — REQUEST_REVISION.** The architecture is directionally sound and properly
  separates M1A from M1E, but it omits an affected canonical runner and leaves the CAS and migration
  bootstrap privilege boundaries unenforced or ambiguous.
- **Implementation authorization — REQUEST_REVISION.** Its frozen six-file ceiling cannot implement
  a non-regressing canonical migration graph, and it delegates two security-critical database
  authority decisions to the future implementer.

`VERDICT: REQUEST_REVISION — add the canonical migration test caller, freeze a database-enforced CAS/ownership model, and distinguish the privileged bootstrap executor from the NOLOGIN object-owner role before owner activation.`
