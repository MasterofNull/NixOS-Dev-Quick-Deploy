# Foundation C Revision 2 — Codex Binding Design Acceptance

**Date:** 2026-08-01 UTC  
**Reviewer:** `codex-subagent-foundation-c-rev2-reviewer (/root/tracker_am2_rebase_audit)`  
**Role:** independent flagship architecture, security, SRE, concurrency, durability,
identity/authority, privacy, rollback, inventory, and Service Coverage reviewer  
**Authority:** read-only design acceptance only; no implementation, freeze, staging,
commit, activation, deployment, provider, network, or live-traffic authority

## 1. Exact review binding

The exact subjects named by
`REV2-COLLABORATIVE-REVIEW-PACKET-20260801.md` were hashed from the shared
worktree before review. Every digest matched the packet exactly:

| Subject | Verified SHA-256 | Result | FREEZE_ELIGIBLE |
|---|---|---|---|
| `RUNNER-DEPLOYMENT-HARDENING.md` | `48cae30d1c93ff9e76fdff0e3866f885b54e544de95c978c8286a1c8065f0c63` | `PASS_DESIGN` | `no` |
| `RUNNER-DEPLOYMENT-HARDENING-FREEZE.md` | `4b5f9b4b4da272da7411f95cf2e6aeed1ac0783412dc434f66ce2748b8c2093f` | `REQUEST_REVISION` | `no` |
| `C6-DESIGN-AND-AUTHORIZATION.md` | `927374039c17abe0103a262b24346d61afc6dc38e7fe6396f74812c17203703c` | `REQUEST_REVISION` | `no` |
| `C4-DESIGN-AND-AUTHORIZATION.md` | `f535731e7fe1ad48c5c70d1f8ccc275ef9b61c731d35a265f876961ea5f14d5a` | `REQUEST_REVISION` | `no` |
| `C3A-2-DESIGN-AND-AUTHORIZATION.md` | `7792e8537ac48c95837e2aedfec6794120a0550f1d274c0a76f29cab36c6a290` | `REQUEST_REVISION` | `no` |

The four prior binding Codex depth reviews were also verified at:

- runner hardening: `52d2b53df69de929bc8bbb5bd7779b4e6486e0e21cf2f5af0a44abf67ce5abb0`;
- C6: `3853f534dc83dda91318beac1f2f80c14300b907c886939fa4073120e062ac10`;
- C4: `d8c18ce5a0cc8135dabe298169d8dc95e1e278b9562797a70144366a0dbc8b2d`; and
- C3a-2: `8ae15018840c653815a5fc866a8d2e3c275ef9f0ae40b4a77e5a38a49cfa21dd`.

All existing predecessor hashes listed across the revised packets matched the
reviewed worktree. Every path asserted `NEW`/absent by C6, C4, and C3a-2 was
verified absent. Those checks establish subject and inventory binding only;
they do not prove implementation behavior or grant authority.

## 2. Runner deployment-hardening design

**Result:** `PASS_DESIGN`  
**FREEZE_ELIGIBLE:** `no`

The revised design closes the three prior binding findings at design level:

- §§3.1-3.2 make activation parsing total, prohibit fallback whenever an
  activation claim exists, prohibit production self-bind, preserve any existing
  pathname, validate exactly one AF_UNIX stream listener at the configured path,
  close unexpected passed descriptors, and clear activation variables;
- §2 now freezes all four editable predecessor hashes plus the switchboard Nix
  no-edit anchor; and
- §4 fixes the previously missing client identity by resolving the configured
  primary user to the effective UID used by `SO_PEERCRED`, while correctly
  refusing to mistake supplementary-group membership for effective-GID identity.

The offline negative vectors cover manual start/restart, malformed/multiple/wrong
activation descriptors, existing-path preservation, standalone inode-safe cleanup,
client identity, and the pre-existing grant/peer denial invariants. The design also
truthfully retains the R5 rollback and separates default-OFF build from the later
live-cell exercise.

### Remaining freeze prerequisites

The companion freeze-status subject is not yet an exact freeze. It identifies the
successor only by path and does not bind the reviewed successor design digest
`48cae30d…` or this acceptance digest. A new freeze record must bind those exact
bytes, recheck the four editable predecessors and switchboard no-edit anchor at its
then-current HEAD, bind implementer/reviewer identities and validation commands,
and retain the repeated-connect/live-cell exercise as a later deployment/activation
gate. Until that additive exact freeze exists, the passing design is not itself
freeze or build authority.

## 3. Runner deployment-hardening freeze status

**Result:** `REQUEST_REVISION`  
**FREEZE_ELIGIBLE:** `no`

The file is honest that the prior freeze is lifted and that no authority exists,
but it does not satisfy the exact-subject freeze contract it describes. It names
the successor design only by pathname and therefore cannot prove which successor
bytes a later activation consumes.

**Required correction:** create a fresh exact freeze bound to design
`48cae30d1c93ff9e76fdff0e3866f885b54e544de95c978c8286a1c8065f0c63`,
this independent review's final digest, the exact current HEAD and predecessor/no-
edit hashes, explicit candidate inventory, validation commands/results, role
identities, single-use authority, and default-OFF/live-exercise separation. The
current PREPARED_ONLY status file must not be relabeled as that freeze.

## 4. C6 authenticated epoch authority and scheduler gate

**Result:** `REQUEST_REVISION`  
**FREEZE_ELIGIBLE:** `no`

The revision substantially closes R1-R3, R5, and R6 in design: it removes the
environment epoch override, makes `aq-event` projection-only, selects a dedicated
owner-signed UDS authority, re-anchors enforcement to verified ingress through
`dispatch.py` and the real `slot_queue` seam, enumerates exact paths/absences, and
requires same-release integration QA plus live-backed dashboard coverage.

One durability defect remains in §2.2. The described sequence durably replaces and
directory-fsyncs `epoch`, and only afterward records the idempotency/replay receipt.
A crash between those two durable operations advances enforcement state without a
recoverable request receipt. Retrying the same signed request then sees an
`expected_epoch` mismatch, while the claimed audit reconciler lacks the request
identity/digest needed to reconstruct the missing receipt. “Before releasing the
lock” does not make two filesystem commits atomic.

**Required correction:** add a recoverable transaction/WAL state written and
fsynced before epoch replacement, with explicit recovery states for
`prepared -> epoch_committed -> receipt_committed -> audit_projected`; bind the
request/idempotency digest and old/new epoch in that state; prove recovery for a
crash after epoch replace but before receipt, after receipt but before audit, and
on corrupt/divergent WAL/epoch/receipt combinations. Recovery must never double-
bump, lower epoch, invent success, or discard an ambiguous committed bump.

### Retained non-assumptive prerequisites

Even after that correction, C6 cannot freeze until §6 Q-C6-1 names and hash-binds
the actual C2 scheduler-context issuer and authenticated transport into
`dispatch.py`, and Q-C6-2 names the immutable owner public-key allowlist revision
and proves Nix state ownership/hardening. These are valid explicit prerequisites,
not grounds to pretend the current design is deployable.

## 5. C4 receiver-scoped connected profiles

**Result:** `REQUEST_REVISION`  
**FREEZE_ELIGIBLE:** `no`

The revision makes a strong and safer architectural correction: initial v2 has no
AF_INET/AF_INET6 path, raw Qdrant and whole-service listeners are forbidden,
OAuth/GitHub are deferred, execution-grant v1 stays network-denied, and the broker
mediates only authenticated per-cell AF_UNIX receiver actions. This closes the
remote DNS/TLS/proxy and ambient-host-egress findings by removing remote egress
from the initial scope rather than claiming an unenforceable TCP filter.

The packet nevertheless remains incomplete in three binding areas:

1. **§§1 and 8 — the “closed” profiles are not frozen.** The exact method/operation,
   request/response schema IDs, receiver identities, byte limits, deadline, and
   concurrency values for the three eligible actions are not enumerated. The
   exact receiver gateway APIs and authenticated identities remain open blockers,
   so the purported initial profile set is not yet implementable.
2. **§8 — the inventory is self-declared incomplete.** It says a future
   authorization must add fixture and schema-registration paths after ownership
   preflight. Prior finding 9 required a complete numbered path/hash inventory
   before freeze; a packet cannot be exact while reserving unnamed later paths.
3. **§§6-7 — backpressure and rollback bounds remain qualitative.** Audit
   saturation “cannot silently become success,” but the design does not say which
   operations deny, which active channels may continue, or how durable recovery
   works. Rollback requires a “frozen numeric teardown budget” but supplies no
   numeric budget or measurement boundary, leaving prior finding 11 unclosed.

**Required correction:** freeze every initial receiver action value and existing
authenticated gateway identity; complete the exact fixture/schema-registration
inventory; specify audit-saturation admission/active-channel behavior and durable
recovery; and set a numeric teardown/zero-active-channel SLO with a test oracle.
Accepted runner hardening/live-cell evidence and an accepted, active C6 lever remain
explicit prerequisites after those design defects close.

## 6. C3a-2 delegation and verified-import broker

**Result:** `REQUEST_REVISION`  
**FREEZE_ELIGIBLE:** `no`

The revised two-authority model, authenticated nonce-bound response contract,
descriptor-stable content-addressed intake, dedicated reservation SSOT, narrow
local import grant, R3/R5 confinement chokepoint, privacy taxonomy, and mandatory
Service Coverage correctly address the intended direction of the six prior
findings. Four concrete inconsistencies still prevent freeze:

1. **§§1 and 9 — inventory contradicts the authority model.** Section 1 says
   execution-grant v1 remains unchanged and neither new grant is a general
   `ExecutionGrant`, yet §9 marks `execution_grant.py` `MODIFY`. The immutable
   lane-eligibility snapshot is an input/authority pin, yet §9 marks its registry
   `MODIFY`. Remove those edits or specify the exact required semantic changes;
   the lane registry should be a no-edit, digest-bound authority input.
2. **§5 — reservation identity is available too late.** The reservation key
   includes `blob_digest`, which is unknown until after remote bytes are received.
   It therefore cannot reserve/deduplicate the dispatch session before accepting
   the blob. Split this into a pre-receive session/idempotency reservation and a
   monotonic post-receive CAS that binds the verified blob digest.
3. **§§5-6 — the import effect has no crash-linearization state.** The state machine
   jumps from `reserved` to `imported|failed` but does not define an `importing`/
   effect-receipt state bound to the R5/R3 import. A crash after the cell write but
   before terminal persistence can leave an ambiguous effect that a later recovery
   cannot safely retry or classify. Add an effect idempotency key, prepared/import-
   receipt transition, and deny/quarantine recovery that never duplicates a write
   or reports a false terminal.
4. **§9 — the exact inventory is self-declared incomplete.** Fixture,
   schema-registration, test, and Nix-import hashes are deferred to a future
   authorization. Finish that ownership inventory before asking for freeze.

The response-signing model also requires a concrete remote lane that can actually
sign the specified tuple with a hash-pinned response key. That is an explicit
freeze prerequisite; no existing Claude/Codex/Gemini provider capability may be
assumed. Runner hardening/live proof, accepted C4, accepted R5 attach, active C6,
and the exact eligible-principal revision remain mandatory later gates.

## 7. Evidence attribution correction

Commits `ec6fc69b80be4a213e8ad5d23fc1320cf3f2f2af` and
`17f899bf838973c755ab7a3e6095ec04a2e74220` are preservation/integration evidence,
not acceptance evidence. Their bodies credit Claude task
`claude-20260801-093407-umfyv7`/Claude model identities despite that task producing
zero review output. Those trailers must not be propagated as authorship or review
credit for these revised subjects.

Per the governing collaborative-review packet, the substantive revision work is
attributed to Codex subagents. The packet does not establish exact individual
Codex-subagent identities, so this review does not invent them. It records only
`codex-subagents (specific identities not established in reviewed evidence)` as
the revision source and credits this acceptance solely to the reviewer identity
declared above. Failed, stale, parked, outputless, or recused agents receive no
review credit.

## 8. Overall disposition

The runner design itself is directionally complete and independently passes at the
design level, but its exact freeze record has not been created. C6 retains a crash-
consistency hole between epoch commit and receipt durability. C4 still lacks a
closed executable receiver catalog, complete inventory, and bounded audit/rollback
contract. C3a-2 still has inventory/authority contradictions and pre-receive/import
linearization gaps. Every subject therefore remains PREPARED_ONLY, and no freeze,
build, activation, deployment, or traffic authority follows from this review.

VERDICT: REQUEST_REVISION — create an exact runner freeze; add C6 crash-recoverable epoch/receipt linearization; complete C4 receiver values, inventory, audit saturation, and numeric teardown bounds; and correct C3a-2 inventory plus reservation/import crash linearization
