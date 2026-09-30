# C6 Decomposition v2 — Independent Binding Review

Subject: `factory/c6-decomposition-v2` @ `22e4b2b0`, relative to baseline `f1f409ef97f73fb6ae152a297ba0c0367e30bf22`
File under review: `.agents/plans/aqos-foundation-c/C6-DECOMPOSITION-20260924.md` (revision v2)
Review role: independent decomposition-plan reviewer (did NOT author v1 or v2)
Prior review closed by this subject: `.agent/collaboration/CODEX-C6-DECOMPOSITION-REVIEW-20260924.md` (REQUEST_REVISION — 3 HIGH)

Disposition: **FREEZE-ELIGIBLE — all three HIGH findings of the v1 decomposition review are genuinely closed; nothing the v1 review affirmed as sound was regressed.**

## Reproduced diff digest

```
command git diff f1f409ef..factory/c6-decomposition-v2 | sha256sum
16e02597d8330ddf452eef74914f970a1a77f35f5d9e1be0f8f070bcfdd0b366  -
```

Matches the requested digest exactly. Diffstat: one file, `+587` lines (the v2 body). No subject drift.

## Assessment

v2 is a substantive restructuring, not a keyword pass. The three v1 HIGH findings were structural
(topology decided too late; C4 contract fixed by a post-milestone doc-sync; coverage inventory absent),
and v2 addresses each with a concrete mechanism:

- A NEW foundation slice **C6-S** (§2) freezes the socket/principal topology (mechanism B) between C6d and
  the C6a/C6c fan-out, so neither builds on an unfrozen transport surface, and the C6c→"decided group
  model (C6b)" cross-dependency is removed at the root.
- A NEW **[AMEND-C4]** step (§7) makes the narrowed C4 prerequisite an explicitly gated, independently
  reviewed contract amendment that must be **accepted before C4 freeze**, replacing the v1 post-milestone
  doc-sync, and binds C4's own teardown as the revocability enforcement.
- A NEW Service-Coverage Contract template (§0.4) plus a per-slice inventory in every slice (§§1–6) closes
  the Nix-import / integration-check / dashboard gaps for every slice, C6b and C6c specifically.

I independently verified the landed-code facts the plan and the v1 review rely on, against `f1f409ef`
(current HEAD):

| Claim | Verified |
|---|---|
| CLI verbs are `build`/`submit`/`bump`, NOT `prepare` | `scripts/ai/aq-epoch-bump:225` `build`, `:238` `submit`, `:253` `bump`; `bump` sends `{"bump":request}` at `:204`. No `prepare`. ✓ |
| Transport handler recognizes only `read-epoch` + `bump`; no `authorize_launch` | `revocation_epoch_transport.py` handler `:283` `read-epoch`, `:290` `bump`; peer creds param is `_peer_creds` (unused/defense-only). No launch op. ✓ |
| `revocation-epoch-authority.nix:111` grants the shared owner-UID (`primaryUser`) membership | `:111` `users.users.${primaryUser}.extraGroups = mkAfter ["aq-revocation-epoch-clients"];`. ✓ |
| ALA + C2-SCI principals also hold `aq-revocation-epoch-clients` | `lease-signing-authority.nix:76` and `c2-scheduler-context-issuer.nix:114` both list it in `extraGroups`. ✓ |
| `c2-scheduler-context-issuer.nix:122` is a group **declaration** only (no shared-UID membership to remove) | `:122` `users.groups.aq-revocation-epoch-clients = {};`. ✓ |
| `revocation-epoch-authority.nix` is imported; `dispatch-gateway.nix` is NOT (must be added by C6b) | `nix/modules/services/default.nix:26` imports the authority; no `dispatch-gateway` import present. ✓ (C6b §5 explicitly adds it.) |
| C4's teardown behavior that Fix 2 binds as enforcement exists | `C4-DESIGN-AND-AUTHORIZATION.md:138-144` — broker "closes active channels, invalidates/makes unavailable their UDS endpoints, and requests affected-cell termination on epoch bump…". ✓ |
| C4 lever is a **freeze** prerequisite (not merely flag-on) | `C4-DESIGN:12`, activation matrix `:191-197` (C6 lever gates C4 flag), `C4-ACTIVATION-READINESS-20260806.md:27,§3` cite §8 "before C4 can freeze". ✓ |

All landed-code references in v2 §0.1 reproduce. No factual regression.

## Findings

**1. LOW — presentational ambiguity in the C6b build position (§8 numbered list vs prose).**
Section/lines: `C6-DECOMPOSITION-20260924.md` §8 numbered step 6 (lines ~525–527) lists C6b **after** step 5
`[C4 freeze eligible]`, while §5 (line ~394), §7.3 (lines ~484–489) and the §8 critical-path note
(line ~533) all state C6b/C6a **build** independently (default-OFF) and only their **gate-ON activation**
waits on C4. Failure scenario: a downstream implementer reading only the §8 numbered ladder could
sequence the C6b build after C4 freeze and idle it unnecessarily, or conversely treat "after C4" as a
build blocker. Not blocking — the prose is internally consistent and explicit ("C6a/C6b build
independently; only their activation waits on C4", line ~489); the numbered ladder is an
activation-ordered narrative. Recommend (non-blocking) a one-line note on step 6 that it is the
activation position, build being unblocked at C6a.

**2. LOW — C6-S "byte-parity inert while gate-OFF" is asserted for a slice that binds a second live socket.**
Section/lines: §2 acceptance (lines ~245–248) claims byte-parity inert while gate-OFF, but the slice binds
a second `launch.sock` listener in `revocation_epoch_transport.py serve()`. A newly-bound idle listener is
a runtime-behavior change even though it dispatches no op. This is correctly scoped as C6-S's own freeze
criterion (the launch socket "has no reachable op until C6a lands"), and §0.2's byte-parity rule is
defined over legacy request call-traces (which are unaffected). Flagged so C6-S's own binding review
proves legacy `read-epoch`/`bump` traces are unchanged and the idle socket cannot be driven pre-C6a. Not
a decomposition defect.

No HIGH or MEDIUM findings.

## Per-fix closure assessment

**Fix 1 — freeze launch/control-socket topology BEFORE C6a/C6c = CLOSED.**
v2 adds C6-S (§2) as a dedicated foundation slice that freezes mechanism B (dedicated TEG-only `launch.sock`
+ `aq-revocation-launch-clients` group; the existing control socket UNTOUCHED, keeping its
separately-authorized `aq-revocation-epoch-clients` read/bump clients). Order is `C6d → C6-S → {C6a ∥ C6c}`
(§8 lines ~511–517), so the topology is frozen before both C6a and C6c — exactly the "shared interface
slice before C6a/C6c" the v1 review offered as an acceptable option, and NOT deferred into C6b. The v1
contradiction is removed at the root: C6c §4 now "Requires C6d and C6-S … Does NOT require C6a" with no
dependency on C6b's group model; C6b §5 only **joins** the group C6-S already froze (§5 lines ~357–360);
§8 (lines ~535–537) states the C6c↔C6b cross-dependency is removed because the group/socket model is a
fixed C6-S input. Mechanism A is explicitly rejected (§2 lines ~202–204).

**Fix 2 — pre-C4 contract amendment BEFORE C4 freeze = CLOSED.**
v2 §7 replaces the v1 post-milestone C6e doc-sync with an explicit `[AMEND-C4]` step (§7.2, §8 step 4)
that: (a) amends `C4-DESIGN-AND-AUTHORIZATION.md` + both readiness docs so the prerequisite is *precisely*
"an operational, owner-authorized, signed epoch-bump path" = C6d + C6c (+ the C6-S transport foundation),
**removing** the F2.5 scheduler gate and `authorize_launch` from the C4 prerequisite; (b) binds C4's own
epoch-recheck / channel-teardown (grounded in the verified `C4-DESIGN:138-144`) as the enforcement making
C4-widened egress revocable; (c) states C6a's real dependency separately — required by **C6b**, its only
consumer, and explicitly NOT part of the kill-lever "merely because it shares the authority's lock/state
machinery" (§0.3 v2 correction lines ~110–114, §7.2 item 3, §3 header); (d) requires the amendment to
clear its OWN independent binding review and be **accepted before any C4 freeze** (§7.2 item 4). Egress is
a HARD pre-activation gate with no interim netns/nftables escape hatch pre-authorized (§6 lines ~411–418,
§0 adopted decisions), and the URL-is-not-an-OS-boundary point is retained. This is the decomposition-plan
structure the v1 finding demanded; execution of the amendment is correctly future, gated work (the whole
document is `PREPARED_ONLY`, authorizes nothing).

**Fix 3 — per-slice Service Coverage inventory = CLOSED.**
v2 adds the §0.4 Service Coverage Contract (8 rows, anchored to the real
`test-c2-sci-service-coverage.py` / `config/validation-check-registry.json` template) and a
"Service-Coverage inventory" in every slice. The two v1-cited gaps are specifically closed: **C6b** (§5)
now inventories `test-c6b-dispatch-gateway-service-coverage.py`, the **required `default.nix` import** of
`dispatch-gateway.nix` (verified absent today, so genuinely required), a registered
`c6b-dispatch-gateway-coverage` id, a dual-harness integration probe (`phase0.py` + `_aq-qa-bash`), and a
live-backed `aistack.py` `trusted_execution_gateway` + `dashboard.js` surface; **C6c** (§4) now inventories
the dashboard states it previously only required — `aistack.py result["owner_epoch_bump_lever"]` with the
exact `operational | none(revoked-only) | unavailable` states plus `dashboard.js` rows, a coverage test,
registry id, and dual-harness probe. **C6a** (§3) is upgraded from unit-tests-only to a coverage test +
authority-op integration probe in both harnesses + `revocation_launch_authorization` dashboard row. The
no-new-surface slices **C6d** (§1) and **C6-S** (§2) explicitly **bind an already-landed coverage path**
(the imported `revocation-epoch-authority.nix` at `default.nix:26` + existing authority dashboard row) and
each still adds a NEW named dual-harness integration check — the §0.4 exception is used correctly and the
bound path is named.

## Regression check (v1-affirmed-sound items)

- C6d-first foundation: preserved (§1, §8 step 1). ✓
- C6a same-lock `authorize_launch`/`apply_bump` serialization: retained, cites rev5 §3.3 and the single
  `epoch.lock` (§3 lines ~258–260). ✓
- C6b in-principal provider execution (caller receives only response bytes): retained, cites rev5 §3.2
  (§5 lines ~364–365). ✓
- Landed-file corrections carried forward and independently re-verified: CLI verb `build`;
  `c2-scheduler-context-issuer.nix:122` declares-group-only; `revocation-epoch-authority.nix:111` grants
  the shared-UID `primaryUser` membership; ALA/C2-SCI memberships at `lease-signing-authority.nix:76` /
  `c2-scheduler-context-issuer.nix:114` (§0.1 rows, §9 item 7). ✓
- Finding→slice seam mapping (C6a↔F1 … C6e↔F5) unchanged; C6-S is additive, not a re-seam (§9 item 1). ✓

No regression detected. The two LOW findings are presentational/for-own-slice-review and do not block a
decomposition freeze.

VERDICT: FREEZE-ELIGIBLE
