# Foundation B2-M1 design and authorization review — revision 4

**Review date:** 2026-07-18
**Reviewer:** Codex sub-agent `/root/b2_m1_review`
**Roles:** independent byte-level contract, database migration architecture, security, Nix integration, and SRE reviewer
**Review type:** exact five-file normalization/rebind gate; no implementation or execution acceptance
**Overall verdict:** **PASS**

## Exact revision-4 subject

| Subject | SHA-256 | Verdict |
|---|---|---|
| `.agents/plans/aqos-foundation-b2/B2-M1-DESIGN-PACKET.md` | `020462d0ec3222bc893c7543712856a80ce8acb92b5b9caa48ab3a902e1860aa` | **PASS** |
| `.agents/plans/aqos-foundation-b2/B2-M1-IMPLEMENTATION-AUTHORIZATION.md` | `0db0a396331ee0eabbc91259c11a6ac14bb3ebd5fdd46735d291a201c6a0e906` | **PASS** |

Any subject-byte change invalidates this verdict.

## Normalized historical evidence

| Evidence | SHA-256 | Status preserved |
|---|---|---|
| `B2-M1-DESIGN-AUTHORIZATION-REVIEW.md` | `ed816d7d02c237216ffb85678dc16b03fc07429eef19d75afd8d20a809fc30f4` | revision-1 `REQUEST_REVISION` |
| `B2-M1-DESIGN-AUTHORIZATION-REVIEW-R2.md` | `26e3fad6d524d2d88d39ec0eedb63a1f083109260b1160a45d6def827603a052` | revision-2 `REQUEST_REVISION` |
| `B2-M1-DESIGN-AUTHORIZATION-REVIEW-R3.md` | `09e994c8f7fa7e9df11f0b00d412d7304d523187568e61bce8a3c95483d085f1` | revision-3 final `PASS` |

The revision-4 authorization binds all three normalized hashes exactly and binds the current design
hash exactly. The design's revision history records the historical subject hashes, verdict sequence,
normalized evidence hashes, and that revision 4 changes no architecture, authority, implementation
inventory, or acceptance semantics.

## Byte and provenance validation

- Recomputed all five package hashes; every byte matches the exact subject/evidence table above.
- Scanned every line in all five files; none ends in a space or tab.
- Recomputed every authorization predecessor/read-only hash and both Git identities; all match.
- Confirmed all three required new implementation paths remain absent and all seven candidate
  predecessor paths remain byte-identical.
- Confirmed the authorization remains `PREPARED_ONLY`, single-use, assigned to
  `codex-subagent-b2-m1a-implementer`, requires explicit exact-hash owner activation, and expires no
  later than 24 hours after activation.
- No candidate edit, staging, commit, implementation, Alembic invocation/render, database access,
  Nix activation, service action, or deployment occurred.

## Semantic equivalence to the revision-3 PASS

The revision-4 subjects preserve every invariant accepted in the normalized R3 review:

1. The exact seven-file candidate remains within D0's maximum eight and includes both canonical
   migration callers.
2. The deployed caller selects only `aidb@head`; the canonical test retains two
   `upgrade aidb@head` calls and one branch-qualified one-step `downgrade aidb@-1`. Singular `head`,
   unqualified `-1`, full-base rollback, generic heads, and B2 selection remain prohibited.
3. The B2 root remains dormant, separately labelled, and inaccessible to the deployed Nix path.
4. The durable owner and runtime roles remain `NOLOGIN`; temporary database `CREATE` exists only on
   the disposable database for the fixture-created owner and is subject to exact preflight, success
   revocation/catalog proof, and failure finalizer revocation/proof/drop.
5. The bootstrap executor remains token-bound, disposable, non-owner, narrowly privileged, and
   removed after success or failure; `alembic_version` remains fixture-administrator-owned.
6. Writer direct table DML remains denied. Only the fixed-search-path owner `SECURITY DEFINER` CAS
   function may atomically advance snapshot, immutable outbox, and initial delivery control.
7. Runtime roles remain non-owners; outbox immutability, catalog drift checks, exact grants, rollback,
   resource ceilings, privacy restrictions, static non-connectivity, M1E separation, and legacy-JSON
   authority truth are unchanged.
8. M1A remains offline artifact authoring only. Database execution, DDL, M1E, runtime adoption,
   deployment, traffic, cutover, cleanup, rollback, and later B2 slices remain separately unauthorized.

## Per-subject conclusion

- **Design packet revision 4 — PASS.** It is semantically equivalent to the revision-3 accepted
  architecture and adds only an accurate normalized review history.
- **Implementation authorization revision 4 — PASS.** Its exact predecessor/review bindings are
  current, its semantic grant is unchanged, and it remains inactive pending explicit owner activation.

`VERDICT: PASS — the exact revision-4 design and PREPARED_ONLY authorization are semantically equivalent to the revision-3 PASS, bind all normalized evidence exactly, contain no trailing whitespace across the five-file package, and preserve every prior architecture, security, SRE, scope, and activation gate.`
