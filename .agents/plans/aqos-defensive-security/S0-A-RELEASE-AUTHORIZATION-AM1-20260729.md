# Track S S0-A — Commit-Train Release Authorization AM1

Status: **PREPARED_ONLY — OWNER ACTIVATION REQUIRED**
Prepared: 2026-07-29
Exact HEAD: `107f7e8ab2452b4d89ff737b28966e35bf4f9e24`
Parent release authorization:
`b6c2cfc3d7f07f740682994b5622c6766e94b4dc20d1d01a35daa58741f19315`
Parent release attempt: **STOPPED BEFORE COMMIT**

## Reason for amendment

The activated parent release passed every hash, HEAD, overlap, and focused-code
preflight. After exact staging, whole-subject `git diff --cached --check` reported
only Markdown trailing-space hard breaks and one final blank line in historical design,
authorization, and review evidence. Those bytes are part of the independently accepted
hashes. Rewriting them would invalidate the reviewed evidence; bypassing an undeclared
failure would violate the parent stop conditions. The index was therefore restored to
empty without changing working-tree bytes.

AM1 changes validation scope only. It changes no accepted subject byte and grants no
implementation, runtime, network, scanner, deployment, push, or later-slice authority.

## Exact release inventory

The exact 15 hashed subject paths and hashes in the parent authorization remain
unchanged. The release commit contains exactly:

1. those 15 paths;
2. `S0-A-RELEASE-AUTHORIZATION-20260729.md` at
   `b6c2cfc3d7f07f740682994b5622c6766e94b4dc20d1d01a35daa58741f19315`;
3. this AM1 authorization at its owner-activated SHA-256.

Total ceiling: **17 paths**.

## Amended validation contract

After owner activation:

1. verify HEAD and all parent hashes;
2. normalize the mixed index without changing working-tree bytes;
3. stage exactly the 17-path ceiling;
4. require `git diff --cached --check` to pass for the four executable/config
   implementation paths:
   - `config/schemas/agent-capability-intake-candidates.schema.json`;
   - `config/agent-capability-intake-candidates.json`;
   - `scripts/ai/aq-capability-intake`;
   - `scripts/testing/test-capability-intake.py`;
5. preserve historical Markdown evidence bytes exactly; their already-observed
   hard-break/EOF warnings are not implementation failures and receive no blanket
   whitespace waiver outside the 11 parent documentation/evidence paths;
6. run JSON parse, Python compilation, focused capability-intake tests, `list`, `audit`,
   documentation-link validation, and the Tier-0 pre-commit gate;
7. prove the staged set is exactly 17 paths, inspect the staged diff, and create one
   atomic evidence-rich commit.

Any whitespace warning in the four implementation paths, either release-authorization
document, or any unrelated path is a stop. Any content/hash drift remains a stop.

## Stop conditions

Stop on HEAD/hash drift, eighteenth path, overlapping writer, failed focused/Tier-0/doc
validation, changed registry semantics, working-tree byte loss during index
normalization, unrelated-file inclusion, runtime/provider/network/scanner/install
activity, deployment, push, or any attempt to generalize this Markdown exception.

The parent release activation is consumed by its stopped attempt and is non-replayable.
Only an exact owner activation of this AM1 hash may resume the release.
