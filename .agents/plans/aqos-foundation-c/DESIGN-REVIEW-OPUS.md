# Foundation C Design Packet — Independent Design Review

**Reviewer:** claude-opus-foundation-c-reviewer (independent; did NOT author — author is fable-5)
**Target:** `.agents/plans/aqos-foundation-c/DESIGN-PACKET.md`
**Date:** 2026-07-24
**Scope:** design-only review — no implementation, no edits. Grounded against F3 AGGREGATE,
keystone zero-trust plan, Q3–Q10 ratification, and the Q5 lane-eligibility registry + aq-role-route.

---

## VERDICT: REVISE

The packet is a **strong, faithful, and correctly-scoped** distillation of F3 + keystone into a
security spine. It **passes the highest-priority axis cleanly** — I found **no fail-open path** in
brokers (§3), profiles (§5), or the shadow→enforce transition (§8); every denial fails closed and
§9 states the non-fail-open invariant explicitly. Scope/ceiling is clean (no B1/B2/B3 re-open, no
Product-D convergence, no keys/providers). C0 is genuinely the lowest-risk entry. Every cited
integration seam exists and is materially correct.

It is **REVISE (not PASS)** for a bounded, additive-within-ceiling reason: it **silently weakens three
ratified elements** (F3 signed-A2A-envelope acceptance bar, the four F3 property tests, and the
keystone v2 *task-scoped monotonic* stickiness), and it contains **one internal contradiction**
between §8 (defers live revocation to C6) and §9 (requires per-slice revocability). None is a
security hole, but the prompt's bar — "doesn't silently drop a ratified element" — is not met. All
corrections below restore ratified content or fix an ordering seam; **none expands scope.**

---

## Verified (stated plainly, per anti-gaming)

- **Fail-open audit — PASS.** No capability/effect/egress is reachable when a lease is
  missing/expired/unverifiable/epoch-stale. §2 deny-by-default, §3 broker "denies fast", §5
  "Default profile = deny-all" + "No profile may fail open", §9 "missing/expired/unverifiable
  lease is a denial, never a bypass." Default-OFF flags are **not** fail-open because §9(b)
  sequences the refactor as *attenuators of an already-issued lease (additive) before removing old
  branches* — the correct anti-fail-open sequencing. This is the load-bearing property and it holds.
- **Agent-agnostic (Rule 18) — PASS.** No role/authority is hard-tied to one lane. The policy
  authority reads as infrastructure, not an agent. §6 delegate broker composes with the Q5 registry
  (roles are model-neutral). No SPOF-by-agent.
- **Q5 composition — coherent.** `config/lane-eligibility-registry.json` carries roles
  `[orchestrator, architect, implementer, reviewer, binding-acceptance, research]`; `aq-role-route`
  resolves routing-lane→registry-lane eligibility (hard-ineligible wins). The packet's claim ("delegate
  lease issued only to a principal whose lane is registry-eligible for the role") is a valid, direct
  composition.
- **Scope/ceiling — clean.** §1 non-goals correctly fence off B1/B2/B3, Product-D, keys/providers,
  and defer the 8-profile enumeration to the C threat pass. No creep detected.
- **Integration-seam anchors — all exist, materially correct:**
  - `switchboard.py:_resolve_tool_lease` — real at **line 1132** (packet "~1100"; within `~`).
  - `switchboard.py:_route_target` — real at **line 2399** (packet "~2367"; inherited from keystone; ~32 off).
  - `x-ai-route` route header — real at **line 53** (exact).
  - `a2a_guard.py::scan_secrets` — real at line 42; `audit` at 69; `a2a-audit.log` present.
  - `aq-capability-intake` — present.
  - `tool_security_auditor.py` — present at `ai-stack/mcp-servers/shared/` (packet omits path); commit
    `82b0d78a` exists and matches "tool-param injection + typo-squat + github token-scope gates" = "hardened".

---

## Findings

### BLOCKING
*(none — no fail-open, no SPOF-by-agent, no scope creep)*

### SHOULD-FIX

**S1 — §8 defers live epoch revocation to C6, but §9 requires per-slice revocability (internal
contradiction; weakens the ratified intervenability leg).**
§9 DoD says each enforcing slice must be *intervenable* ("operator can revoke a lease / bump the
epoch"). But §8 puts "Epoch revocation live" LAST at C6, so C2–C5 turn on lease enforcement with
**no live revocation** — an over-scoped/compromised lease is valid until `expires_at` with no
mid-flight revoke. This is fail-*closed* (expiry is still checked), not a hole, but the per-slice DoD
in §9 is **unsatisfiable as written** for C2–C5, and epoch revocation is a codex "decisive addition"
in F3 (AGGREGATE §1). **Correction (additive):** ship the executor `revocation_epoch` check *with the
first enforcement slice (C2)*; redefine C6 as "epoch revocation wired to the global scheduler / F2.5
seam + the policy/session-epoch bump control surface." Every slice that enforces a lease must be
revocable the moment it turns on.

**S2 — Signed A2A envelope + heartbeat (F3 ratified part 3 of 4) is folded implicitly and its
acceptance bar dropped.**
F3 AGGREGATE §3 + acceptance criteria: "Antigravity output accepted only when **signed + fresh +
schema-valid + written to the expected path**"; the envelope (deadline/idempotency/
expected_output_path/allowed_write_paths/heartbeat) is the *authority*, the folder is transport only.
The packet references "signed A2A envelope" only as a principal *attestation kind* (§2) and reuses
"a2a local signing" in C0; the **verify-before-write output contract and heartbeat liveness are not an
explicit slice or acceptance criterion.** Heartbeat appears only as a cell rollback trigger (§4).
**Correction (additive, within ceiling):** name the remote-lane principal attestation = signed-A2A-
envelope verification (signature + deadline + idempotency + allowed_write_paths + output schema BEFORE
write) as an explicit acceptance criterion of the **delegate broker** (C3), and carry the heartbeat
`pending-late`/`dead` contract forward. This is the exact lane that carried the F3 contributions;
dropping its hardening from the productionizing packet is the silent-drop the review is meant to catch.

**S3 — Keystone v2 "task-scoped MONOTONIC (raise-only)" stickiness is weakened to per-request.**
Keystone plan v2 (BINDING, ratified 3/3) §"Derivation (P0.1)": `task_sticky |= zt` — zero-trust is
*sticky across requests within a task, raise-only*, with a dedicated `sticky-after-prune` acceptance
test (defends against a later message pruning the secret to downgrade privilege). The packet §2 says
`zero_trust_behavior: strip` removes capabilities "**for that request**" — i.e. per-request only,
dropping the task-monotonic dimension. **Correction (additive):** state that when `zero_trust` is
collapsed into the lease behavior, the strip is **task-scoped monotonic** — once raised within a
task_id it cannot downgrade on a later (pruned) request. Preserve the `sticky-after-prune` property.

**S4 — Signer / policy-authority-unavailable posture is unspecified; risks fail-closed-to-total-DoS
vs. keystone's degrade-not-outage.**
"No lease ⇒ not usable" (§2) is correct, but the packet never says what happens when the **signer or
policy authority is itself down** (missing local key, authority service unreachable). Read literally,
deny-by-default then denies *all* capabilities including reads — a self-DoS. The keystone plan already
resolved this tension with "boot-safety (qwen): a broken `a2a_guard` **degrades + alerts, does NOT
block boot**" and fail-closed→`zero_trust=true` (strip privileged), not deny-everything.
**Correction (additive):** specify the authority-unavailable degraded posture — fail closed *toward a
minimal least-privilege lease* (deny privileged/write/network/delegate, allow safe read) + LOUD alert,
NOT fail closed toward total denial. Reconcile explicitly with keystone boot-safety. (Still zero
fail-*open* — this is the availability leg of "no fail-open".)

**S5 — Shadow (C1) must be explicitly additive and must NOT disable existing keystone enforcement
until C2 validates.**
C1 is "log-only (shadow) — enforce nothing." Correct intent, but the packet doesn't state that the
**pre-existing keystone `zero_trust` enforcement + capability-intake stay live underneath** during
C1→(pre-C2). If shadow silently replaces the current filter path, there's a window with neither the
new lease enforcement nor the old protection. **Correction (one line):** C1 issues+logs leases
*alongside* the existing live protections, which remain authoritative until C2's enforcement is
shadow-validated then flag-flipped.

**S6 — C3 bundles too much for one independently-reviewable, offline-first slice; and the network
broker in C3 has no profiles to consult until C4.**
C3 = five brokers (write/network/secret/delegate/exec) + bwrap kernel confinement + git-worktree
rollback executor. That is at least two reviewable concerns (policy attenuators vs. the sandbox+
rollback executor) and it front-runs C4: the **network broker** is in C3 but **network profiles** are
in C4, so the C3 network broker has nothing to evaluate against. **Correction (additive, no scope
change):** split C3 into C3a (write/secret/delegate/exec *policy* brokers as pure lease attenuators)
and C3b (bwrap⇄lease cell + `workspace.snapshot`/`workspace.rollback` executor); and state that the
network broker ships **deny-all** in C3 and gains its profile evaluators in C4 (keeps it fail-closed
in the interim).

**S7 — The four ratified F3 property tests are not carried forward as the acceptance bar.**
F3 AGGREGATE §1 names them as the implementation bar: (1) stripped-can't-reacquire, (2)
caller-`zero_trust=false`-can't-downgrade-inherited-stricter, (3) stale-lease-can't-revive-after-epoch,
(4) output-outside-allowed-paths-rejected-even-on-success. §9's DoD is generic and names none.
**Correction (additive):** attach these four as explicit per-slice acceptance (→ C2 strip/downgrade,
C2/C6 epoch, C3 allowed_output_paths). They are the ratified proof obligations; the packet should not
re-derive a weaker bar.

### NICE-TO-HAVE

**N1 — Refresh the seam anchors** to the current lines: `_resolve_tool_lease` **1132**, `_route_target`
**2399** (both drifted ~32 from the keystone-era "~1100/~2367"); add the file path
`ai-stack/switchboard/switchboard.py` and `ai-stack/mcp-servers/shared/tool_security_auditor.py`.

**N2 — Name the trust root.** §2/§3 rely on "a policy authority" + "local signer" but never name the
component (coordinator? switchboard? new service?) or its key-rotation/recovery story. C0 defines the
signer, so this can defer, but one sentence stating the authority is *infrastructure, not an agent*
(satisfies Rule 18 explicitly) and a pointer to key rotation/recovery would close the single-signing-
key SPOF question.

**N3 — Schema drift note.** F3 AGGREGATE §1 lists `revocation_rule`; the packet §2 schema uses
`revocation_epoch`. This is a *faithful consolidation* (epoch = codex's ratified mechanism, the impl
baseline), not a drop — but a half-line noting the rename would prevent a future reviewer re-flagging it.

---

## Bottom line
Fail-closed spine, faithful primitive, correct C0 entry, clean scope, coherent Q5 composition — but
REVISE: restore three silently-weakened ratified elements (signed-A2A acceptance S2, keystone
task-monotonic stickiness S3, the four F3 property tests S7), fix the §8/§9 revocation contradiction
(S1), and split the over-bundled C3 (S6); all corrections are additive within the existing ceiling.
