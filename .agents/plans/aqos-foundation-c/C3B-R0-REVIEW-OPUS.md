# Foundation C — C3b Rev3 (R0 design) Independent Review — VERDICT: PASS

**Reviewer:** Opus flagship (independent of the author). **Author:** codex (rev3, socket-
activated dedicated cell runner). **Scope:** R0 design only — this review authorizes NO build,
Nix change, service deployment, flag activation, or commit of runner code. **Subject:**
`C3B-DESIGN-AND-AUTHORIZATION.md` rev3. **Independence:** Rule 18 — codex authored, so codex may
not review; Opus is independent of that authorship.

## Method
Verified the packet's cited anchors against live code/config (not prose), traced every
effect/fail-open path, and tested the packet against the nine historical blocking obligations
(§10) rather than approving the architecture in the abstract.

## Anchor verification (all accurate — "verify even codex")
- `capability_lease_gate.py::resolve_current_epoch` (line 172) + `DEFAULT_EPOCH_PATH =
  config/capability-lease-epoch` (line 84) — EXIST. Epoch file absent (created by ops/issuance);
  the §7.5 "unreadable/unparseable epoch → fail closed" rule correctly covers the absent case.
- `nix/modules/services/default.nix` — EXISTS with an `imports` block (the §4 import point is real).
- switchboard hardening `NoNewPrivileges=true` / `CapabilityBoundingSet=""` / `RestrictNamespaces=true`
  (switchboard.nix:525/531/534) — CONFIRMED; the "keep byte-for-byte" invariant is anchored to real lines.
- C2 `enforce()` returns only `(admitted, decisions)` (lines 475/641) — CONFIRMED; the signed
  execution grant is honestly-scoped NEW R1 work (Q5 premise correct), not an overclaim.

## Nine obligations — assessment
1. in-process handlers can't be bwrap-confined → §2/§4 dedicated child-process runner; switchboard
   runs no effectful handler. CLOSED (design-level; see SF-3 on the handler→descriptor crux).
2. independently verifiable grant → §3.1 signed immutable grant, runner verifies with its own
   trusted verifier, UDS = transport only, SO_PEERCRED peer check. CLOSED (see SF-1 on signer model).
3. signed closed multi-effect classification → §3.2 closed `effect_set`, conservative
   ambiguous→deny, `unsandboxed-authorized` not honored. CLOSED.
4. caller-path rebasing → §6.2 logical→cell-root resolution, rejects abs/`..`/symlink/unicode;
   no caller selects bind target. CLOSED.
5. no live `.git` bind → §6.1 self-contained clone at verified base OID; live worktree + common
   `.git` never mounted. CLOSED (cleanly fixes the worktree pointer problem).
6. typed truthful clone/cleanup/quarantine/reconcile → §7.8 cleanup failure → quarantined +
   idempotent reconciler, never deleted-and-reported-success. CLOSED (fixes the WorkspaceManager flaw).
7. epoch revocation kills tree + final fence → §7.5–7.7 250ms epoch/liveness poll, runner-generated
   heartbeat (caller heartbeats never trusted), cgroup.kill + wait-for-death + quarantine-on-failure,
   epoch reread immediately before GREEN. CLOSED (strong).
8. numeric APU perf gate → §8 concrete limits (3.0s clone p95, 250ms spawn, 768MiB/cell, 5.0s
   teardown) + rigorous protocol (N=40/cohort, posix_fadvise/mincore cache validity, CLOCK_MONOTONIC_RAW,
   nearest-rank p95, cgroup-v2 memory, immutable JSONL). CLOSED (exceptionally rigorous).
9. Nix userns to runner only, switchboard monotonic → §4/§9 new execution-cell-runner.nix,
   runner-only RestrictNamespaces relaxation, switchboard hardening byte-for-byte unchanged.
   CLOSED at service level (see SF-2 on the global userns toggle).

No fail-open found: deny-closed throughout, `--unshare-all`/`--unshare-net`, no unsandboxed
fallback (§9), validator runs OUTSIDE the cell and ignores cell-controlled git config/hooks/
attributes/textconv (§6.4 — closes a real diff-poisoning vector), process tree contained via
`--unshare-all` (pid ns) + cgroup tracking.

## SHOULD-FIX (non-blocking — fold into R1; do not block R0 PASS)
- **SF-1 (grant signing model).** The grant is HMAC (symmetric, `capability_lease` signer): the
  runner and the gate share the key, so a component holding the key can mint grants the runner
  accepts. This is consistent with the C0–C2 local-trust model AND the UDS is client-group-scoped
  to the switchboard identity, so it is not a new fail-open — BUT the runner is a NEW privileged
  boundary (it alone holds userns). R1 should make an explicit, recorded decision: keep symmetric
  HMAC (documenting the runner as inside the gate's trust boundary) OR raise the bar with
  asymmetric signing (gate signs with a private key, runner verifies with a public key) so a
  compromised runner cannot forge its own grants. Reserved-question Q(new).
- **SF-2 (global userns toggle).** §4/Q4 correctly flags `security.unprivilegedUsernsClone=true`
  is a GLOBAL kernel setting (all unprivileged users), not per-service. Before R3, ground whether
  this host's kernel ALREADY permits unprivileged userns (making only the service-level
  `RestrictNamespaces` relaxation necessary and avoiding a global sysctl change). If a global
  change is genuinely required, keep it as the distinct owner-ratified threat item R0 already names.
- **SF-3 (handler→descriptor crux, obligation 1).** The load-bearing integration — translating the
  existing in-process Python tool handlers (`write_file`, `run_command`, …) into the runner's
  "bounded command descriptor" / proposed-bytes-write model — is deferred across R1–R5. R0 should
  name explicitly WHICH current tools become command-descriptors vs broker-mediated writes in R5 so
  the R3/R5 adapter scope is bounded before R3 freezes (ties to the deferred effect-broker manifest-
  accuracy issue in the backlog).

## Reserved questions (§11) — reviewer position
- Q1 persistent runner vs transient `systemd-run`: persistent socket-activated runner is the right
  R3 baseline (one observable identity, narrow surface); a transient-unit comparison is a fair
  SEPARATE later study, not a fallback — agree with the packet.
- Q2 budgets: the stated limits are appropriately conservative; freeze them as ceilings, allow R4
  to tighten only. Agree.
- Q3 clone source immutability: a dedicated bare mirror is preferable to reading the live `.git`
  even at a pinned OID (avoids any concurrent-gc/pack interaction) — recommend R2 evaluate it.
- Q4 exact Nix userns option: resolve via SF-2 grounding before R3.
- Q5 C2 grant fields: confirmed C2 exposes none today; R1 is pure schema/projection + signer — correct.

## Verdict
**PASS** for the R0 design against its scope and the nine obligations. No BLOCKING fail-open.
SF-1/SF-2/SF-3 are non-blocking and belong in R1. R0 PASS is NOT implementation authorization:
R1 requires its own hash-bound design + (for enforcement-tier stages) single-use owner activation,
per the packet's own R0–R6 discipline. Recommend the author fold SF-1/SF-2/SF-3 as R1 inputs and
proceed to the R1 pure-grant/classification design when the owner elects to continue.
