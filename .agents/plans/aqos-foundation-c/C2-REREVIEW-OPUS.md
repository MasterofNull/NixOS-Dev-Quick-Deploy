# C2 Tool-Lease Enforcement — Independent RE-REVIEW (Opus)

**Reviewer:** claude-opus-foundation-c-c2-rereviewer (independent — did NOT author; did NOT
author the prior review either). Anti-gaming stance: verify the fixes actually close the holes,
not that the record *claims* they do.
**Reviewed record:** `.agents/plans/aqos-foundation-c/C2-DESIGN-AND-AUTHORIZATION.md` **rev2**
sha256 `313b723b4e1039f6b339a302056b14fc9b5c6cb5c922990d283fbee0ac4526eb` @ HEAD `4545e605`.
**Prior review:** `C2-REVIEW-OPUS.md` (REVISE — B1 + B2 BLOCKING, S-a..S-d SHOULD-FIX).
**Scope:** DESIGN + AUTHORIZATION record (PREPARED_ONLY). Reviewed the revised design against
live source: `switchboard.py` (`_execute_local_tool_calling` L1545, admission L1673, virtual-lease
L1679, executor `else` L1706, `execute_tool_call` L1735, `_TOOL_BUNDLES` L914–948, remote filter
L1240 / call site L2955); `capability_lease.py` (`resolve_key` L181, `verify` L272/L290,
`epoch_stale` L228).

---

## VERDICT: PASS

Both BLOCKING fail-opens are **genuinely closed**, verified against source — not rubber-stamped.
The four SHOULD-FIX items are adequately addressed, and the revision introduces **no new
fail-open**: the corrected `:1673` hook is byte-for-byte inert flag-OFF (behind the flag + parity
test), and every new leg (is_dev degrade, epoch-unresolvable degrade, strip, fail-closed wrapper)
is **subtractive** — no combination composes into an admit. The design is safe to freeze for owner
activation.

---

## B1 — CLOSED (chokepoint re-anchored, and it is the *only* local exec site)

The prior finding was correct: gating only `_resolve_tool_lease` (`:1690`, the voluntary
`lease_tools` re-lease) left the initial bundle-injected privileged tools ungated. rev2 re-anchors
the gate at the per-call admission `if tool_name not in allowed_names:` (`switchboard.py:1673`),
admitting for execution iff in `allowed_names` **AND** lease-admitted.

Verified this is the true and *complete* chokepoint:
- **Single local execution site.** `rg execute_tool_call` returns exactly one call —
  `registry.execute_tool_call` at **L1735**, inside the `else` branch (`:1706`) of the per-call
  dispatch. That branch is reached only after passing the `:1673` `allowed_names` check. There is
  no second path that runs a local tool. So gating admission at `:1673` covers 100% of local
  privileged-tool execution.
- **Premise confirmed.** `run_command` is in `_TOOL_BUNDLES` at L914 (`git`), L916 (`sys_ops`),
  L922/L932/L948 — so bundle-classified requests do seed `run_command` into the initial
  `allowed_names` at L1552. Under the old hook that executed ungated; under the `:1673` hook it is
  now checked before L1735 ever runs.
- **Re-lease path also covered.** After a `lease_tools` call, `allowed_names` is rebound at L1692
  and the *next* iteration re-enters L1673 — so leased-in tools pass the same gate. rev2 also
  routes the `_resolve_tool_lease` result through the gate; even absent that, the per-call L1673
  re-check is load-bearing. Belt and suspenders, correctly identified.

No remaining flag-ON path admits a local privileged tool without lease admission. **B1 closed.**

## B2 — CLOSED (is_dev consumed *before* any DEV-key verify)

`resolve_key()` (`capability_lease.py:181`) returns `(key_bytes, is_dev)` — `False` only when a
readable non-empty secret file resolves (L198), else `(DEV_SIGNING_KEY, True)` (L201). The signal
the prior review flagged as "the missing-authority condition the gate fails to consume" is real and
exposed. rev2 §"(B2)" now consumes it: `is_dev=True` → S4 authority-unavailable degrade (safe-read
allowlist only), and the gate **never verifies or admits under the public DEV key**.

Verified no residual DEV-key verify path:
- The degrade is ordered *before* verification/issuance. In dev (is_dev=True) the gate short-circuits
  to the safe-read allowlist, so `shadow_issue()` (which signs with `resolve_key()`) and
  `verify()` are never reached under the DEV key. In prod (is_dev=False) issuance and verify share
  the same real key — consistent trust root.
- Acceptance B2 drives the anti-gaming case directly: a DEV-key-signed lease that *would* "admit"
  is still dropped under degrade. That test fails if any code path verifies under the DEV key —
  exactly the regression guard needed.

**B2 closed.**

## SHOULD-FIX — all adequately addressed

- **S-a (epoch) — CLOSED.** Source named: `config/capability-lease-epoch` file / `AQ_LEASE_POLICY_EPOCH`
  env, default `0`, C2 read-only (bump surface = C6). `current_epoch` is ALWAYS resolved to an int
  and passed to `verify` — never `None` — so the `verify` L290 `current_epoch is not None` skip
  can't silently no-op the revocation leg. Present-but-unparseable → S4 degrade. The absent→`0`
  default is sound: epoch 0 is the legitimate no-revocations-yet baseline (all leases carry
  `revocation_epoch ≥ 0`, none stale), while *corruption* is treated as authority-unavailable.
  Correct distinction.
- **S-b (tool→lease mapping) — CLOSED.** Now specified and implementable: `enforce()` iterates
  candidate shadow leases once per request; a tool is admitted iff some admitted candidate's lease
  (`shadow_issue` `would_issue=True`, `verify`-passing, epoch-OK, not stripped) lists it in
  `permissions.actions`. Deny-closed for any tool with no admitting lease. Buildable from the
  primitives.
- **S-c (guarded import + fail-closed) — CLOSED.** Lazy import inside the enforcement branch
  (N1: `scripts/ai/lib` already on `sys.path`); `enforce()` wrapped so any internal exception FAILS
  CLOSED (tool dropped), never crashes resolution. Parity test asserts the gate module is not
  imported flag-OFF. Both legs stated.
- **S-d (remote path) — CLOSED as a sound written deferral.** Verified `:2955`
  `_filter_remote_tools_for_working_set` sits in the remote-proxy route (`_rewrite_model` + remote
  profiles); it shapes the payload `tools` for a *remote* upstream that does its own tool-calling —
  it does **not** invoke local `registry.execute_tool_call`. So deferring it to the named `C2-remote`
  follow-up leaves **no** path where a local privileged tool (`run_command`) executes ungated. The
  deferral rationale ("does not execute local privileged tools") is factually correct, not a
  hand-wave.

## New fail-opens from the revision? — NONE FOUND

I looked specifically for a degrade+strip+epoch-unresolvable combination that admits:
- All three new legs are **subtractive/restrictive**. Degrade *replaces* the admitted set with a
  fixed safe-read allowlist (non-write/network/exec); strip *removes* write/network/delegate/exec;
  epoch-unresolvable *routes to* degrade. There is no additive leg, so no two restrictions can
  compose into an admit — the admitted set is a deny-closed base intersected with per-tool lease
  proof. The only residual assumption is that the safe-read allowlist itself contains no privileged
  tool; the acceptance test "authority-unavailable → privileged dropped" pins that.
- **Off-is-inert at the hotter hook.** The hook moved to per-call `:1673` (runs every loop
  iteration vs only on voluntary re-lease). This does not weaken off-is-inert: the entire new path
  is behind `if CAPABILITY_LEASE_ENFORCEMENT`, flag-OFF preserves the exact existing
  `if tool_name not in allowed_names` semantics, and a parity test proves byte-for-byte identity at
  `:1673`. Moving to a per-call hook changes *how often the gate could run when ON*, not *whether it
  runs when OFF*.

## Governance / ceiling — unchanged and still sound

Single-use owner activation naming this rev2 SHA-256 + implementer + HEAD + ≤24h window is intact;
standing/broad auth explicitly rejected; flag-flip is a further owner act with the Nix option in the
same cycle (Rule 13). The 4-file ceiling still holds for the *larger* edit: the switchboard change
is now a multi-region single-file edit (the `:1673` admission + routing the `:1690` result through
the gate) — still ONE edited file + gate lib + test + schema = 4. The prior review's criterion-4
concern (the self-imposed "one function only" constraint had to yield) is resolved: rev2 drops that
constraint explicitly and scopes the edit to the tool-call admission region.

---

## NICE-TO-HAVE (non-blocking, do not gate freeze)

- **N-a — Safe-read allowlist membership.** rev2 describes the degrade allowlist by property
  ("non-write/network/exec") but does not enumerate it. Fine for a design record; the implementer
  should pin the concrete list and the "privileged dropped under degrade" test guards it. Consider
  naming it in the record for reviewer determinism.
- **N-b — Per-call enforce() cost.** Gating at `:1673` means `enforce()` (candidate iteration +
  `verify`) can run once per tool call per loop iteration. Correctness-neutral, but a per-request
  memoized tool→admission map (build once, reuse across the loop) would avoid repeat work. Purely a
  performance note.

---

## Bottom line

**PASS.** B1 and B2 are closed for the right reasons, confirmed against source: `:1673` is the sole
gate in front of the only local tool-execution site, and `is_dev` is consumed before any DEV-key
verification can occur. S-a..S-d are adequately folded, S-d's deferral is factually safe, and the
revision adds no new fail-open (all new legs subtractive; off-is-inert preserved behind the flag +
parity test). Governance and the 4-file ceiling remain sound. **The design is safe to freeze for
owner activation** — record the rev2 SHA-256
`313b723b4e1039f6b339a302056b14fc9b5c6cb5c922990d283fbee0ac4526eb` @ HEAD `4545e605` and present the
single-use owner activation line. codex confirmatory audit remains advisory per the catch-up queue.
