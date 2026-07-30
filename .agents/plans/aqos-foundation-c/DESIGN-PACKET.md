# Foundation C — Identity, Leases, Execution Cells (Design Packet)

**Status:** DESIGN-ONLY, **revision 2** (independent Opus review REVISE folded 2026-07-24 —
see §10 + `DESIGN-REVIEW-OPUS.md`). Implementation is **PREPARED_ONLY — NOT AUTHORIZED**;
each slice below requires its own hash-bound authorization + independent review +
single-use owner activation before any code lands.
**Author:** fable-5 (orchestrator/architect, analysis tier — per FABLE-5-ANALYSIS-CHARTER).
**Track:** AQ-OS Unified Program — Foundation C (ref-arch Cycle 2). Absorbs **F3**
(CapabilityLease + OTel + signed A2A, 4/4 RATIFIED — `.agents/plans/f3-capability-otel/AGGREGATE.md`)
and the **keystone zero_trust** primitive (`.agents/plans/phase0-keystone-zero-trust-plan.md`).
**Dependencies (both satisfied):** B1 chat/batch parity shadow oracle ACCEPTED 2026-07-23
(`auth-aqos-foundation-b1-parity-20260723` consumed); Q3 security direction RATIFIED
2026-07-23 (`Q3-Q10-OWNER-RATIFICATION-20260723.md`) — zero-trust, principal
attestations + CapabilityLease, **no fail-open modes**.

## 1. Goal & non-goals

**Goal.** Make *every* capability (tool, skill, MCP, RAG source, DB, cache, model,
remote lane, delegate target) usable ONLY through a signed, short-lived, attenuable
**CapabilityLease** issued by a policy authority to an attested **Principal**, executed
inside an isolated **cell**, with **OTel spans** as the operational source of truth.
Deny-by-default: nothing is usable until capability-intake admits it AND policy issues a
lease. This replaces the 5 ad-hoc auto-selection/policy layers with one primitive they
all become *evaluators* of.

**Non-goals (explicit deferrals).**
- Not re-opening B1/B2/B3 contracts; C consumes them.
- Not the Product-D switchboard-sole-gateway convergence (that's Cycle 3) — C provides
  the lease/cell boundaries D will route through, but does not itself delete legacy paths.
- Not new remote providers or keys (NO API keys — OAuth/IDE session only; signed A2A
  uses **local** signing, no extracted secrets).
- The exact **eight network profiles** get their own dedicated threat pass at C planning
  (ratified sub-decision, Q3) — §5 fixes their *shape*, not the final enumeration.

## 2. The one primitive — Principal + CapabilityLease

Direct from the F3 unanimous design (claude+codex+local+antigravity converged, no dissent).

**Principal.** The attested identity a lease is issued to. Fields:
`principal_id / kind(agent|service|human|remote-lane) / attestation(how proven: OAuth
session ref, systemd unit cred, signed A2A envelope) / trust_tier / session_epoch`.
Callers are untrusted — a principal is *derived/verified at the boundary*, never taken
from the caller's own claim (mirrors keystone: `zero_trust` is derived per request).

**CapabilityLease.** Consensus schema:
`id/lease_id/version/source/owner/issued_to(principal)/issued_at/expires_at/
permissions{actions,resources,constraints}/input_schema/output_schema/trust_tier/
zero_trust_behavior/cost_class/observability_hooks/parent_lease_id/revocation_epoch/
signature`.

Load-bearing rules (all ratified):
- **Deny-by-default admission** — capability-intake admits a capability; policy then
  issues a lease. No lease ⇒ not usable.
- **Monotonic least-privilege / attenuation chain** — within a request permissions only
  ever SHRINK. A sub-delegation gets a child lease (`parent_lease_id`) that is ⊆ parent.
  Elevation requires a fresh top-level authority decision + new `lease_id` + span event.
- **The 5 layers become lease EVALUATORS, not parallel hints** — `a2a_guard`,
  action-policy, dispatch-budget, capability-intake, auto-selection/routing each only
  *attenuate or deny* a lease. (This is the concrete refactor surface, §6.)
- **`zero_trust` collapses into one lease behavior** — `zero_trust_behavior: strip`
  irreversibly removes write/network/secret_read/delegate/unsandboxed-exec. The strip is
  **task-scoped monotonic (raise-only)** — once raised within a `task_id` it CANNOT
  downgrade on a later (pruned) request (keystone v2 `task_sticky |= zt`; the
  `sticky-after-prune` property is preserved, defending against a later message pruning
  the secret to regain privilege). The keystone flag stops being a separate boolean.
- **Epoch-based revocation** (codex's decisive addition) — every executor checks
  `revocation_epoch` against the current policy/session epoch; a stale cached lease
  **cannot revive** after an epoch increment. (`revocation_epoch` is the faithful
  consolidation of F3's `revocation_rule` field — epoch is codex's ratified mechanism and
  the implementation baseline, not a dropped element.)
- **`allowed_output_paths` enforced even on tool SUCCESS** — a tool that writes outside
  its lease's allowed set is a violation regardless of exit code.

**Trust root.** The policy authority + local signer/verifier are **infrastructure, not an
agent** (no role/agent is the authority — Rule 18). C0 defines where they live (candidate:
a coordinator-adjacent signer service) and the local signing key's rotation/recovery story;
the key is the one SPOF to design out (rotatable, recoverable from SOPS `/run/secrets/`,
never tracked Nix).

## 3. Effect brokers

Every side-effect is a *brokered effect* gated by the issuing lease — the executor never
performs a raw effect. Brokers: **write** (path-scoped, `allowed_output_paths`),
**network** (host/profile-scoped — §5), **secret_read** (SOPS `/run/secrets/` only,
never tracked Nix), **delegate** (issues an attenuated child lease to another principal),
**exec** (sandboxed vs unsandboxed per lease + cell — §4). A broker denies fast with a
span event; `zero_trust_behavior: strip` removes the broker entirely for that request.

**Delegate broker — signed-A2A verify-before-write acceptance (F3 part 3/4).** When the
delegate broker issues a child lease to a *remote-lane* principal (e.g. the antigravity
IDE-OAuth node), returned work is accepted ONLY when its **signed A2A envelope** verifies:
signature valid + not past `deadline` + `idempotency` unseen + written to the declared
`expected_output_path` + within `allowed_write_paths` + output-schema-valid — **all
checked BEFORE any write is honored** (the envelope is the authority; the watched folder
is transport only, untrusted). The envelope carries a **heartbeat liveness** contract:
`pending-late` (heartbeat missed, still within deadline) vs `dead` (deadline blown /
heartbeat gap) → feeds the cell rollback trigger in §4. Signing is **local, no keys**.

## 4. Execution cells (isolation)

Write-capable execution runs in a **cell**: an isolated git worktree (preferred) or
scoped `git stash -u` fallback, under **bubblewrap (bwrap)** kernel-level confinement
whose allowed set == the lease's allowed set (**bwrap ⇄ lease agreement** — the lease
defines, bwrap enforces). Before the first write: `workspace.snapshot`. On GREEN
(tier0) → merge + retain for orchestrator review; on RED / timeout / heartbeat-miss /
revocation → drop the worktree (instant revert) + emit `workspace.rollback`. Rollback
never crosses the allowed set. This makes rollback an executor guarantee, not agent
discipline.

## 5. Network profiles (shape; enumeration deferred to C threat pass)

"Connected zero trust": network access is a *profile* attached to a lease, not ambient.
A profile = `{id, allowed_hosts[], allowed_ports[], direction, auth(OAuth/session ref
only), egress_logging:true}`. Default profile = **deny-all** (keystone: sandbox blocks
net by default). The eight profiles enumerate the *only* legitimate egress shapes
(local-inference, embed, coordinator, switchboard-remote-OAuth, MCP-github,
MCP-playwright-sandboxed, A2A-inbox, telemetry-export — indicative, NOT final). **The
final eight + their host/port sets are ratified inside C planning after a dedicated
threat pass** (Q3 sub-decision). No profile may fail open.

## 6. Integration seams (existing code → lease evaluators)

The refactor is *surgical* — these become evaluators/enforcement points, not rewrites
(anchors verified 2026-07-24 in `ai-stack/switchboard/switchboard.py`):
- `switchboard.py:_resolve_tool_lease` (line 1132) + tool-catalog builder → issue/attenuate
  the tool lease instead of ad-hoc filtering.
- `switchboard.py:_route_target` (line 2399) + `x-ai-route` (line 53) → network/delegate broker
  consults lease + profile; forced-remote paths honor lease, never silent OpenRouter
  reroute (existing security invariant preserved).
- `scripts/ai/lib/a2a_guard.py::scan_secrets` (line 42) + `.agent/collaboration/a2a-audit.log`
  → the secret_read/delegate broker + `zero_trust_behavior` derivation.
- `aq-capability-intake` + `ai-stack/mcp-servers/shared/tool_security_auditor.py`
  (hardened 82b0d78a) → the deny-by-default admission gate that precedes lease issuance.
- dispatch-budget / `config/model-coordinator.json` tiers + the **Q5 lane-eligibility
  registry** (shipped a12667c9) → the delegate broker's cost/eligibility attenuator.
  (Foundation C's delegate lease is issued only to a principal whose lane is
  registry-eligible for the role — C and Q5 compose directly.)

## 7. Observability (operational truth)

OTel spans (turn / tool / lease / validation / workspace) are the **source of truth**;
PULSE, a2a-audit, ACTIVATION-AUDIT, the parity matrix become *projections* of spans
(consistent with `aq-event` already being the projector, B3). Every lease
issue/attenuate/deny/revoke and every broker allow/deny emits a span with
`lease_id/parent_lease_id/revocation_epoch`. W3C Trace Context across A2A hops.

## 8. Slice decomposition (each hash-bound, offline-first, flag-gated default-OFF)

- **C0 — Lease + Principal schema & signer** (report-only). Define the JSON schema,
  local signer/verifier (no keys — reuse a2a local signing), `revocation_epoch` source +
  the policy/session-epoch counter. Ships schema + an `aq-lease` inspect/verify CLI +
  golden fixtures. No enforcement yet.
- **C1 — Deny-by-default admission → issuance** (shadow, **additive**). capability-intake
  admits → policy issues a lease; log-only — record what WOULD be denied, enforce nothing.
  The **pre-existing keystone `zero_trust` enforcement + capability-intake stay live and
  authoritative underneath** throughout C1→(pre-C2); C1 issues+logs leases *alongside*
  them, never replacing them, so there is no window with neither old nor new protection.
- **C2 — Tool lease enforcement at switchboard + live revocation** (flag-gated).
  `_resolve_tool_lease` honors the lease; `zero_trust_behavior: strip` collapses the
  keystone flag (task-scoped monotonic — §2). **The executor `revocation_epoch` check
  ships HERE** (not deferred) — the moment enforcement turns on it is revocable (an
  over-scoped/compromised lease can be killed mid-flight by bumping the epoch), satisfying
  the §9 per-slice intervenability DoD. Default off; flag-flip only after shadow-validated.
  F3 property tests (1) stripped-can't-reacquire + (2) caller-can't-downgrade-inherited-
  stricter + (3) stale-lease-can't-revive-after-epoch are the acceptance bar.
- **C3a — Policy effect brokers** (flag-gated). write/secret/delegate/exec brokers as pure
  lease attenuators; the **network broker ships deny-all** here (fail-closed) and gains its
  profile evaluators in C4. Delegate broker enforces the signed-A2A verify-before-write +
  heartbeat contract (§3). F3 property test (4) output-outside-allowed-paths-rejected-even-
  on-success is the acceptance bar.
- **C3b — Execution cells** (flag-gated). bwrap⇄lease kernel confinement +
  `workspace.snapshot`/`workspace.rollback` git-worktree executor (§4).
- **C4 — Network profiles** (after the C threat pass ratifies the eight). Turns the C3
  deny-all network broker into profile-scoped egress.
- **C5 — OTel spans as truth + projections** (make audit/PULSE/matrix span-derived).
- **C6 — Epoch revocation ↔ global scheduler / F2.5 seam** (the epoch bump *control
  surface* + wiring so leases gate the F2.5 scheduler; the executor epoch *check* already
  shipped in C2).

Ordering: C0→C1 provide the primitive in shadow (zero risk, old protections stay live);
C2→C3b turn on enforcement behind flags (each revocable the moment it enforces); C4→C6
complete. Each slice independently reviewable + offline-first + flag-gated default-off;
local (Qwen) engaged every slice per never-skip-local.

> **RESEQUENCE 2026-07-29 (owner-ratified).** The C3a effect-broker design went through 3 codex
> binding review rounds (`codex-20260729-171430/-172222/-173023`) which proved that **in-process
> effect-brokering cannot safely precede the confinement substrate**: nearly every current tool
> handler performs network (needs C4 profiles) or subprocess (needs C3b bwrap cells) effects, and
> `config/first-party-tools.json`'s effect classes are materially inaccurate vs the real handlers.
> New order: **C2 (done) → C3b (execution cells) → C4 (network profiles) → effect brokers
> (formerly C3a, now the capstone, on top of confinement + profiles) → C5 → C6.** The C3a design
> work is retained (`C3A-1-…`, `C3A-2-…`, superseded combined `C3A-…`) with all codex findings
> preserved; brokering resumes once cells + profiles exist and an accurate signed per-handler
> effect inventory replaces the manifest guesses.

## 9. Activation & risk (Rule 15)

- **Definition of done per slice:** integrated (live path consults the lease) + ON (flag
  enabled in the running profile) + real-world validated (a real request denied/allowed
  as designed, not just unit tests) + observable (span + dashboard surface + health-
  spider check) + intervenable (operator can revoke a lease / bump the epoch). Dormant =
  paused pending activation.
- **Top risks:** (a) enforcement-on breaking a live path — mitigated by shadow-first
  (C1) + default-off flags; (b) the 5-layer refactor touching hot switchboard code —
  mitigated by making them attenuators of an already-issued lease (additive) before
  removing the old branches; (c) network-profile over/under-scoping — mitigated by the
  dedicated threat pass gating C4; (d) cell/bwrap perf on the APU — measure in C3.
- **Explicit non-fail-open:** every broker and profile denies closed; a missing/expired/
  unverifiable lease is a denial, never a bypass (Q3 hard requirement).
- **Authority-unavailable posture (availability leg of "no fail-open"):** if the signer or
  policy authority is itself down (missing local key, authority unreachable), the system
  degrades to a **minimal least-privilege lease** — deny privileged/write/network/delegate,
  ALLOW safe read — plus a LOUD alert, NOT fail-closed-to-total-DoS. This reconciles with
  keystone boot-safety ("a broken `a2a_guard` degrades + alerts, does NOT block boot").
  Still zero fail-*open*: nothing privileged is reachable, but the system stays alive.
- **Ratified F3 proof obligations (per-slice acceptance, not a re-derived weaker bar):**
  (1) stripped-can't-reacquire → C2; (2) caller-`zero_trust=false`-can't-downgrade-
  inherited-stricter → C2; (3) stale-lease-can't-revive-after-epoch → C2 (check) + C6
  (scheduler seam); (4) output-outside-allowed-paths-rejected-even-on-success → C3a; plus
  keystone `sticky-after-prune` (task-monotonic zero_trust) → C2.

## 10. Status & immediate next step

**Independent review: COMPLETE.** Reviewed by an independent Opus reviewer 2026-07-24
(`DESIGN-REVIEW-OPUS.md`) — VERDICT REVISE (fail-open audit PASS, no SPOF-by-agent, no
scope creep). All 7 SHOULD-FIX + 3 NICE-TO-HAVE folded into this packet (revision 2):
S1 revocation ships at C2 (§8); S2 signed-A2A verify-before-write bar (§3, C3a); S3
task-monotonic zero_trust stickiness (§2); S4 authority-unavailable degrade posture (§9);
S5 C1 additive/old-protections-authoritative (§8); S6 C3 split into C3a/C3b + network
deny-all (§8); S7 four F3 property tests as per-slice acceptance (§8/§9); N1 anchors
refreshed (§6); N2 trust root named as infrastructure (§2); N3 `revocation_rule`→
`revocation_epoch` rename noted (§2). codex queued for a confirmatory catch-up audit on
cooldown-return (deepest F3 contributor).

**Next:** prepare the **C0** hash-bound implementation authorization (report-only: lease +
principal JSON schema + local signer/verifier + `aq-lease` inspect/verify CLI + golden
fixtures — the lowest-risk entry, zero enforcement) and, on owner activation, route to the
cheapest-eligible implementer per the Q5 registry. **Nothing here authorizes
implementation** — C0 remains PREPARED_ONLY until an explicit single-use owner activation.
