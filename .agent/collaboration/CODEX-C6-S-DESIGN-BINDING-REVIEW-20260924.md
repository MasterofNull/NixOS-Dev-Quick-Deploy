# Binding Review — C6-S Design (Shared launch-socket + principal topology)

- **Subject:** `factory/c6s-design` @ `093c4881108c30aa9eadc27b3310d9f123b66f3c`
- **File under review:** `.agents/plans/aqos-foundation-c/C6-S-DESIGN-AND-AUTHORIZATION.md` (only changed file; 390 insertions)
- **Baseline:** main `f1f409ef97f73fb6ae152a297ba0c0367e30bf22`
- **Role:** INDEPENDENT adversarial binding reviewer (did NOT author this design)
- **Reviewed:** 2026-09-25
- **Disposition:** **REQUEST_REVISION** — two narrowly-scoped, security-core tightenings (below). The mechanism is sound and verified; this is a wording/forward-condition correction, not a redesign.

## Reproduced diff digest

```
command git diff f1f409ef..factory/c6s-design | sha256sum
=> 6d8dce97ff4a36a582305ce1277e3b4865325894999af9756528d63331c8177a   [MATCHES requested digest]
```
`git diff --stat` confirms exactly one changed file (the design doc). **No subject drift.**

## Assessment

I verified EVERY §1 anchor hash and file:line citation against HEAD `f1f409ef` (not the doc's self-report). All reproduce exactly:

- **Anchor hashes** — all five match §1 byte-for-byte: `revocation-epoch-authority.nix` `b539e5de…`, `revocation_epoch_transport.py` `066b30c3…`, `lease-signing-authority.nix` `2fb53e4c…`, `c2-scheduler-context-issuer.nix` `e14ce663…`, `default.nix` `7873bff5…`.
- **The Finding-2 defect is real and correctly diagnosed.** At `f1f409ef` the control-socket client group `aq-revocation-epoch-clients` has FOUR members, verified: authority-user (`revocation-epoch-authority.nix:102`), owner/`primaryUser` (`:111`), ALA (`lease-signing-authority.nix:76`), C2-SCI (`c2-scheduler-context-issuer.nix:114`). `c2:122` is a bare group DECLARATION (`users.groups.aq-revocation-epoch-clients = {};`), NOT a membership — rev5 mistook it for an editable shared-UID membership. `c2:123` adds `primaryUser` to `aq-c2-scheduler-context-clients`, NOT the revocation group. So rev5's proposed fix (delete `:111`) would have left ALA + C2-SCI reachable — the design's rejection of rev5's fix is correct.
- **SO_PEERCRED is log-only, verified:** `revocation_epoch_transport.py:69` (`get_peer_credentials` "NOT the authority — logged only"), and the `serve()` peer log at `:163-171` ("defense-in-depth log only, not authority"). The module docstring (`:1-19` of the `.nix`; transport `:9-10`) confirms "transport membership is NEVER sufficient authority." The design's reliance on kernel DAC rather than SO_PEERCRED is therefore well-founded.
- **serve() single-socket shape, verified:** `serve()` def `:128`, `bind` `:142`, `chmod 0o660` `:143`, chgrp `:148`, `listen(16)` `:158`, accept loop `:159-185`. `build_env_handler` `:246`; `read-epoch` op `:283`; `apply_bump` `:296`; `__main__` `:301-309` calling `serve(_sp, build_env_handler())`. All match §1.
- **Authority ships dormant, verified:** `config = mkIf cfg.enable`; `ownerKeysPath` is an all-zeros placeholder that "fails every real signature closed" (`:80` description). Hardening intact: `NoNewPrivileges` `:159`, `CapabilityBoundingSet=""` `:160`, `ProtectSystem="strict"` `:161`, `RestrictAddressFamilies=["AF_UNIX"]` `:166`. `Type="simple"` `:139` (C6d flips to notify). RuntimeDir declared `0755` at `:117`. Environment block `:146-152`.
- **Structural exclusion of ALA/C2-SCI/owner from launch.sock is genuine.** launch.sock is `0660` group `aq-revocation-launch-clients`; ALA/C2-SCI/owner hold only `aq-revocation-epoch-clients`, so `connect()` returns EACCES at the kernel — this is real DAC on a separate inode, not a log-only peer check. The `0755` traversable dir permits reaching the path but the `0660`/group socket gates the connection (same pattern the accepted control.sock uses). **The exact defect rev5 falsely claimed was already closed is now actually closed** for these three principals.
- **Owner kill-lever correctly severed from the launch surface.** `primaryUser` (`:111`) is in `aq-revocation-epoch-clients` only; C6-S adds no `primaryUser` membership to the launch group. Bump/kill stays on control.sock. Verified.
- **Control-socket least-privileged path preserved byte-for-byte.** C6-S makes no edit to `aq-revocation-epoch-clients` membership, no edit to the control socket, and does not touch `build_env_handler()`/`apply_bump`. Verified against the design's own §2.2 item 1.
- **C6d composition is consistent.** C6d (`factory/c6d-design-v2`) edits transport `__main__` to `recover() → serve()`, flips `Type=simple→notify` at `:139`, gates `sd_notify(READY=1)` on `recover()`, and reserves check id `0.10.51`. C6-S §3 composes: single `recover()` pass, then bind BOTH sockets, then READY=1 after both listen. No change to `recover()`/journal/two-index/`Type=notify`. `apply_bump` signature and `:296` preserved. No contradiction with C6d's recover-before-listen or `__main__`-only claim.
- **Harness id coordination, verified:** max check id at baseline is `0.10.50` in BOTH `phase0.py` and `_aq-qa-bash`; `0.10.51` is absent at baseline (C6d reserves it, unlanded). C6-S taking `0.10.52` avoids collision when both land. `_check_intent_classifier_coverage` template is at `phase0.py:1325`, wired via `results.extend(...)` at `:1985`. Registry templates `ala-service-coverage` `:1376` and `c2-sci-service-coverage` `:1398`, env-contract `AQ_REVOCATION_EPOCH_SOCKET_PATH` canonical `:1339`, aistack ALA `:2090` / C2-SCI `:2112` — all verified.
- **Dashboard scope-expansion premise is truthful:** `dashboard/backend/api/routes/aistack.py` has ZERO `revocation_epoch_authority` references at baseline (verified `grep -c` = 0), so the launch-vs-control topology is genuinely unobservable today. The faithful ground-truth note in §6 is accurate.

**Net:** the topology mechanism (mechanism B — dedicated launch.sock + new group; control socket untouched) is a real, kernel-enforced, verifiable fix that does not depend on SO_PEERCRED and does not rely on rev5's broken delete-`:111` approach. C6-S is design-only, default-safe, ships no reachable launch op (deny-all stub), and requires no owner activation. The two findings below are precision/forward-condition corrections in the security core.

## Findings

### Finding 1 (MEDIUM) — Exclusivity claim is imprecise; the authority-user IS a launch-group member, and the un-signed launch op means the group boundary is necessary-but-NOT-sufficient
- **Where:** design §2.3 vs §2.2 item 3; edited `revocation-epoch-authority.nix:102` (per §1/§2.2).
- **Defect:** §2.3 states "only members of `aq-revocation-launch-clients` can `connect()` to `launch.sock`, and **the only consumer ever added to that group is the TEG** (C6b)." This is contradicted by §2.2 item 3, which adds the **authority-user** to `aq-revocation-launch-clients` (for the chgrp requirement — real: `CapabilityBoundingSet=""` drops CAP_CHOWN, so chown-to-group needs membership, exactly as the accepted epoch-group pattern at `:102`/`:148`). So the launch group has TWO ever-added members: the TEG (C6b) and the authority-user. The design's own §2.2/§2.3 disagree on this sentence.
- **Failure scenario:** `authorize_launch` (C6a) is **un-signed** (rev5 §3.2 — minted under the authority's lock, no owner signature). The kernel group gate excludes ALA/C2-SCI/owner (correct), but does **NOT** exclude the authority-user, which is a launch-group member. Once C6a makes the op reachable, any code path executing as the authority UID that `connect()`s to launch.sock could reach an op with no signature gate — a latent self-launch surface on the fleet's launch authority. In C6-S this is inert (deny-all stub, no reachable op), so it is not exploitable at this freeze; but the closure doc for a HIGH false-exclusivity finding must not itself ship an imprecise exclusivity sentence — that is the exact class of error under repair.
- **Required change:**
  1. Correct §2.3 to state the launch group's ever-added members are `{authority-user (server/chgrp role), TEG (C6b)}` — not "only the TEG" — and that the three external principals (ALA, C2-SCI, owner) are the ones structurally excluded.
  2. Elevate the C6a op-specific TEG `SO_PEERCRED` peer check from a §2.3 "RECOMMENDS … belt-and-suspenders" to a **BINDING forward-condition recorded in the C6-S freeze that C6a must cite** — because for the un-signed launch op the group boundary alone does not exclude the server principal itself. (The design already identifies the peer check; it must be made mandatory, not advisory.)

### Finding 2 (LOW) — Transport edit-surface under-specified: "reuses transport:159-185" implies a serve() refactor beyond "`__main__` + a helper"
- **Where:** design §1 (transport row), §3 item 2; `revocation_epoch_transport.py:128-185`, `:301-309`.
- **Defect:** the design confines the transport change to "`__main__` + a bounded multi-listener helper" and says the "generic accept/`read_frame`/dispatch machinery at `transport:159-185` is reused per connection." At baseline that machinery is inline in `serve()`'s `while True: srv.accept()` loop (`:159-185`); `serve()` binds ONE socket and blocks forever. A `selectors`-based two-socket multiplexer that "reuses" `:159-185` most cleanly requires extracting that loop body out of `serve()` — an edit OUTSIDE `__main__`, and a modification to the function whose control-socket call path the design elsewhere claims to preserve byte-for-byte.
- **Impact:** low (design-level), but the freeze packet must pin (a) whether `serve()` itself is modified, and (b) that the control-socket connection path (`build_env_handler` dispatch, frame handling) stays byte-parity. Left implicit, the eventual build could quietly widen the transport edit surface and weaken C6d's `__main__`-only invariant.
- **Suggested change:** state explicitly in §1/§3 whether the helper is a new `serve_multi()` leaving `serve()` intact, or a refactor of `serve()`'s loop body, and assert the control-socket path parity as a freeze condition.

### Finding 3 (LOW / informational) — Dashboard scope expansion is JUSTIFIED, not creep, but the parent decomposition file list should be reconciled
- **Where:** design §6; adds `dashboard/backend/api/routes/aistack.py` + `assets/dashboard.js` beyond the decomposition §2 file list (which named only the `.nix`/transport/env-contract files).
- **Judgment:** **This is justified scope, correctly inventoried — not creep.** Rule-15 "observable" requires the frozen topology be dashboard-visible; ground truth confirms no `revocation_epoch_authority` section exists (verified). The addition is minimal (a compact section folded into the existing Foundation-C authority health block, **no new card**), live-backed (probes `/run`, no hard-coded healthy, no `--` placeholder — consistent with dashboard-parity principle), and honestly flagged. The added files ARE included in the new check's `trigger_paths` (§6 row 8), so the freeze's "reject all other changed paths" clause covers them.
- **Note only:** the decomposition §2 file list is the frozen parent scope contract; its coverage paragraph already calls for "extend the existing authority health row to show both sockets," so this is reconciliation, not conflict. Record the expanded file list against the decomposition so the parent scope and the C6-S freeze packet agree.

## rev5 Finding 2 closure verdict

**CLOSED (for C6-S's topology-freeze scope) — with one binding forward-condition on C6a (Finding 1.2).**

C6-S structurally and verifiably excludes the three principals rev5 falsely claimed were already excluded: ALA (`lease-signing:76`), C2-SCI (`c2:114`), and owner (`:111`) hold only `aq-revocation-epoch-clients` and cannot `connect()` to the separate `0660`/group `launch.sock` (kernel DAC, not SO_PEERCRED). The control socket + epoch group are untouched, preserving the least-privileged `read-epoch`/`bump` path exactly as Finding 2 required. C6-S correctly does NOT delete `:111` and does NOT edit the `c2:122` group declaration (rev5's two errors).

The residual — the authority-user is itself a launch-group member and `authorize_launch` is un-signed — does not reopen Finding 2 at this freeze (no reachable op in C6-S), but it means the group boundary alone is not sufficient to make the *op* TEG-exclusive once C6a lands. Hence the closure is conditioned on Finding 1.2: the C6a op-specific TEG peer check must be binding, and §2.3's "only the TEG" wording must be corrected. With those two tightenings, the closure is complete.

## Note on the dashboard scope-expansion

Justified and correctly inventoried (Finding 3). It satisfies Rule-15 observability against a truthfully-reported baseline gap (no existing `revocation_epoch_authority` section), stays minimal (folded, no new card, live-backed), and its files are captured in the new check's `trigger_paths`. Not scope-creep. Only ask: reconcile the expanded file list with the parent decomposition §2 list.

VERDICT: REQUEST_REVISION — (1) correct §2.3's "only the TEG" exclusivity sentence to acknowledge the authority-user is a launch-group member (server/chgrp role), and (2) elevate the C6a op-specific TEG SO_PEERCRED peer check from "recommended" to a BINDING forward-condition in the C6-S freeze that C6a must cite (the un-signed authorize_launch op is not made TEG-exclusive by the group boundary alone, which does not exclude the authority-user). Finding 2 (transport edit-surface) and Finding 3 (dashboard scope) are LOW/informational and need not block once (1) and (2) are made. The mechanism-B topology itself is sound, verified against ground truth, and default-safe.
