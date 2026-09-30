# C6 Decomposition — Independent Review

Subject: `factory/c6-decomposition` relative to `f1f409ef97f73fb6ae152a297ba0c0367e30bf22`  
Review role: independent decomposition-plan reviewer  
Disposition: **REQUEST_REVISION — the finding seams are sound, but the dependency/order contract is not yet executable as written**

Requested digest reproduced from the raw Git diff:

`git diff f1f409ef..factory/c6-decomposition | sha256sum`  
`9834e29216005646e9ec11cc18b3fa4c04c49619658610a725383da798af8d7a  -`

## Assessment

The decomposition correctly maps C6a–e to rev5 Findings 1–5, and C6d-first is the right foundation. The retained rev5 work is not lost: C6a carries the same-lock launch/bump serialization proof; C6b carries in-principal provider execution; and C6d carries recover-before-listen plus the two-index recovery shape. The landed-code corrections are also accurate: the CLI verb is `build`; `c2-scheduler-context-issuer.nix:122` only declares the group; and removing `primaryUser` at `revocation-epoch-authority.nix:111` leaves the ALA and C2-SCI service principals in `aq-revocation-epoch-clients` through `lease-signing-authority.nix:76` and `c2-scheduler-context-issuer.nix:114`.

The following issues prevent the plan from being frozen in its current form.

1. **HIGH — C6c's declared dependency contradicts the ordered critical path.** C6c says its owner socket access must be decided relative to C6b's group model and explicitly says it requires “a decided group model (C6b)” (plan lines 198–211). The build sequence nevertheless freezes/builds C6c before C6b and declares `C6d → C6a → C6c` sufficient to unblock C4 (lines 343–361). A future or parallel “bounded input” is not a frozen dependency. Select and freeze the launch/control-socket topology before C6c. My preference is mechanism **B**, with a dedicated TEG-only launch socket/group and the existing control socket retaining separately authorized read/bump clients. That choice must be part of C6a's transport contract (or a small shared interface slice before C6a/C6c), because choosing B in C6b would otherwise revise the transport surface C6a just froze.

2. **HIGH — the C4↔C6 contradiction is logically solvable, but the plan does not yet perform the contract amendment needed to solve it.** The current C4 design requires an “accepted, activated C6 intervention lever,” says that lever makes C4 expansion revocable, and requires its accepted commit/activation hashes before C4 can freeze (`C4-DESIGN-AND-AUTHORIZATION.md:12,143-144,191-219`). The readiness document is stronger still: C4 cannot freeze until C6 is reviewed, accepted, and owner-activated (`C4-ACTIVATION-READINESS-20260806.md:27,43-63`). The current C6 design defines that lever as the durable epoch authority **plus** the live F2.5 scheduler gate (`C6-DESIGN-AND-AUTHORIZATION.md:86-90,221-236`). The decomposition instead redefines it as C6d+C6a+C6c while postponing C6b, even though C6a's launch authorization has no consumer until C6b. A follow-up doc sync in C6e, after the claimed C4-freeze milestone, cannot retroactively make C6c completion satisfy the existing prerequisite.

   The resolution can be made sound without a cycle: amend and independently review C4 **before C4 freeze** so its prerequisite is precisely an operational, owner-authorized signed epoch-bump path (C6d+C6c, with any genuinely required authority transport foundation), and explicitly bind C4's own epoch recheck/channel-teardown behavior as the enforcement that makes C4 egress revocable. Then C6b/C6e activation may correctly remain after C4. Do not count C6a as part of the kill lever merely because it shares authority machinery; state its actual dependency separately. Superseding rev5 §6 for TEG-egress activation is sound only after that pre-C4 contract amendment is accepted.

3. **HIGH — the “exact landed files” are not sufficient for independently shippable slices.** C6b creates `nix/modules/services/dispatch-gateway.nix` but inventories no module import/wiring surface and no registered AQ-QA/dashboard service coverage. C6c requires dashboard states `operational|none(revoked-only)|unavailable` (lines 213–216) but inventories no dashboard backend/UI or integration-check files. C6a adds a new authority operation but inventories only unit tests, despite the service-integration and visibility contract. Each slice's exact inventory must include its required Nix import/wiring, integration QA registration, and live-backed dashboard/API surfaces, or explicitly bind already-landed coverage that exercises the new path. Otherwise C6b/C6c in particular cannot be frozen and committed independently under the repository's Service Coverage Contract.

## Open decisions

- **Egress:** choose C4 as the hard pre-activation gate. There is no urgency, so the interim netns/nftables path should not be pre-authorized as a generic escape hatch. If later needed, it requires a separately reviewed exact mechanism; nftables alone cannot enforce a provider *URL* identity across DNS/address changes.
- **C6b isolation:** choose mechanism **B**, the dedicated launch socket/group. It preserves the existing least-privileged read/bump control path and makes TEG exclusivity structural. Freeze this topology before C6a/C6c rather than deferring it until C6b.
- **Order after correction:** C6d remains first. Next freeze the shared socket/principal contract, then C6a and C6c may fan out without an unresolved cross-dependency. C4 becomes freeze-eligible only after the amended C4 prerequisite is independently accepted and the C6d+C6c bump lever is operational. C6b→C6e remains the scheduler-egress activation path after C4.

VERDICT: REQUEST_REVISION — freeze the launch/control-socket topology before C6a/C6c, remove C6c's dependency/order contradiction, make the narrowed C4 prerequisite an accepted pre-C4 contract amendment, and complete each slice's Nix/QA/dashboard inventory
